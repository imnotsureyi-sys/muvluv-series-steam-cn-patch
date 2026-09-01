from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rUGP.tools.provenance.verify_photon_images_v6 import write_new_report


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "rUGP/tools/provenance/verify_photon_images_v6.py"


class PhotonImageVerifierCliTests(unittest.TestCase):
    def test_help_entrypoint_runs_from_clean_checkout(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("downloaded V6 ZIP", completed.stdout)

    def test_report_is_new_complete_and_cannot_alias_an_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "images.zip"
            archive.write_bytes(b"synthetic archive identity")
            output = root / "reports" / "verification.json"
            report = {"schema": "synthetic", "status": "PASS"}

            write_new_report(output, report, inputs=(archive,))
            self.assertIn('\"status\": \"PASS\"', output.read_text(encoding="utf-8"))
            self.assertEqual([], list(output.parent.glob(f".{output.name}.*.tmp")))
            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                write_new_report(output, report, inputs=(archive,))
            with self.assertRaisesRegex(FileExistsError, "must not alias"):
                write_new_report(archive, report, inputs=(archive,))
            self.assertEqual(archive.read_bytes(), b"synthetic archive identity")


if __name__ == "__main__":
    unittest.main()
