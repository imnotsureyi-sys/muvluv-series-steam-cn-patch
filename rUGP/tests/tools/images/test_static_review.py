from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageFont
from rUGP.tools.images.build_static_review import build, validate, StreamPNG
from rUGP.tools.provenance.export_static_review import export


class StaticReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / "synthetic.png"
        Image.new("RGBA", (8, 6), (30, 100, 200, 255)).save(self.image)
        self.item = dict(path=str(self.image), size=[8, 6],
                         sha256=hashlib.sha256(self.image.read_bytes()).hexdigest().upper())
        self.row = dict(id=1, category="Example", title='<script>alert("x")</script>',
                        collection="Synthetic", section="Card", status="Review only",
                        placeholder=False, shared_native=True,
                        official=dict(jp=self.item, en=self.item), candidate=self.item)
        self.manifest = dict(categories=["Example"], rows=[self.row])
        self.resources = dict(assets=[dict(id=1, refs=["pm:rio000:0x123:cbg2d/cr6ti"])])

    def projection(self):
        return export(self.manifest, self.resources)

    def test_projection_removes_private_fields_and_authenticates(self):
        self.manifest["private_path"] = str(self.root)
        self.row["private_note"] = str(self.root)
        catalog, assets = self.projection()
        self.assertNotIn(str(self.root), json.dumps(catalog))
        self.assertNotIn("private_note", json.dumps(catalog))
        self.assertEqual(len(validate(catalog, assets, self.root)), 1)
        self.assertEqual(catalog["counts"]["pictured"], 1)

    def test_export_rejects_source_drift(self):
        self.item["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash drift"):
            self.projection()

    def test_export_rejects_dimensions_and_private_labels(self):
        self.item["size"] = [9, 6]
        with self.assertRaisesRegex(ValueError, "dimensions drift"):
            self.projection()
        self.item["size"] = [8, 6]
        self.row["status"] = "C:/private/work"
        with self.assertRaisesRegex(ValueError, "filesystem paths"):
            self.projection()

    def test_duplicate_ids_and_unknown_categories_fail(self):
        self.manifest["rows"].append(deepcopy(self.row))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.projection()
        self.manifest["rows"].pop()
        self.row["category"] = "Missing"
        with self.assertRaisesRegex(ValueError, "category"):
            self.projection()

    def test_status_only_rows_cannot_leak_images(self):
        self.row["placeholder"] = True
        catalog, assets = self.projection()
        self.assertEqual(assets, {})
        self.assertIsNone(catalog["rows"][0]["candidate"])
        self.assertEqual(validate(catalog, {}, self.root), {})
        catalog["rows"][0]["official"] = dict(jp=self.item)
        with self.assertRaisesRegex(ValueError, "Status-only"):
            validate(catalog, {}, self.root)

    def test_reader_rejects_file_and_shared_language_drift(self):
        catalog, assets = self.projection()
        self.image.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate(catalog, assets, self.root)
        Image.new("RGB", (8, 6), "red").save(self.image)
        changed = dict(size=[8, 6], sha256=hashlib.sha256(self.image.read_bytes()).hexdigest().upper())
        other = self.root / "other.png"
        Image.new("RGB", (8, 6), "blue").save(other)
        blue = dict(size=[8, 6], sha256=hashlib.sha256(other.read_bytes()).hexdigest().upper())
        catalog["rows"][0].update(official=dict(jp=changed, en=blue), candidate=changed)
        assets = {changed["sha256"]: str(self.image), blue["sha256"]: str(other)}
        with self.assertRaisesRegex(ValueError, "images differ"):
            validate(catalog, assets, self.root)

    def test_build_outputs_readable_atlas_and_escaped_html_without_overwrite(self):
        catalog, assets = self.projection()
        font = self.root / "synthetic-font"
        font.write_bytes(b"font identity for mocked renderer")
        default_font = ImageFont.load_default()
        output = self.root / "review"
        with patch("rUGP.tools.images.build_static_review.ImageFont.truetype", return_value=default_font):
            report = build(catalog, assets, self.root, output, font, atlas=True, columns=1)
        with Image.open(output / "atlas.png") as image:
            image.load()
            self.assertEqual(image.size, (992, 584))
        page = (output / "index.html").read_text("utf-8")
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertEqual(report["locations"], [dict(id=1, x=0, y=260)])
        with self.assertRaisesRegex(ValueError, "already exists"):
            build(catalog, assets, self.root, output, font)

    def test_stream_refuses_incomplete_output(self):
        stream = StreamPNG(self.root / "partial.png", 2, 2)
        stream.append(Image.new("RGB", (2, 1)))
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            stream.close()
        self.assertTrue(stream.file.closed)


if __name__ == "__main__":
    unittest.main()
