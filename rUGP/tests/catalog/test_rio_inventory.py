from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rUGP.formats.rio.crypto import encode_extent_size
from rUGP.tools.catalog.rio_inventory import (
    ENCRYPTED_SIGNATURE,
    ICI_KEY,
    ICI_SIGNATURE,
    MAX_DECODED_CHUNK_BYTES,
    RIO_KEY,
    IciInfo,
    InventoryError,
    Node,
    RioArchive,
    _find_toc,
    build_inventory,
    decode_class_name,
    parse_args,
    parse_ici,
    render_csv,
    run_cli,
)


def u8(value: int) -> bytes:
    return bytes((value,))


def u16(value: int) -> bytes:
    return value.to_bytes(2, "little", signed=False)


def u32(value: int) -> bytes:
    return (value & 0xFFFFFFFF).to_bytes(4, "little", signed=False)


def i32(value: int) -> bytes:
    return value.to_bytes(4, "little", signed=True)


def i64(value: int) -> bytes:
    return value.to_bytes(8, "little", signed=True)


def short_string(value: str) -> bytes:
    encoded = value.encode("cp932")
    if len(encoded) >= 0xFF:
        raise AssertionError("fixture string is too long")
    return u8(len(encoded)) + encoded


def _pack_lsb_bits(bits: list[int]) -> bytes:
    result = bytearray((len(bits) + 7) // 8)
    for index, bit in enumerate(bits):
        result[index // 8] |= bit << (index % 8)
    return bytes(result)


def encoded_class_name(name: str) -> bytes:
    """Use GARbro's literal escape branch; compactness is irrelevant here."""

    bits: list[int] = []
    if name.startswith("C"):
        bits.append(0)
        name = name[1:]
    else:
        bits.append(1)
    for char in name:
        bits.extend((1, 0))
        bits.extend((0, 0, 0, 0))
        value = ord(char)
        bits.extend((value >> shift) & 1 for shift in range(8))
    bits.extend((1, 1))
    bits.extend((31 >> shift) & 1 for shift in range(5))
    encoded = _pack_lsb_bits(bits)
    if decode_class_name(encoded) != ("C" + name if bits[0] == 0 else name):
        raise AssertionError("synthetic class-name encoder is inconsistent")
    return encoded


def class_ref(name: str, schema: int = 1) -> bytes:
    encoded = encoded_class_name(name)
    return u16(0xFFFF) + u16(schema) + u8(len(encoded)) + encoded


def encrypt_stream(plain: bytes, key: int) -> bytes:
    header1 = ((~len(plain)) & 0xFFFFFFFF) ^ 0xC92E568B
    header2 = ((len(plain) << 3) & 0xFFFFFFFF) ^ 0xC92E568F
    result = bytearray(u32(header1) + u32(header2))
    position = 0
    while position < len(plain):
        portion = min(0x20, len(plain) - position)
        checksum = 0
        for index, value in enumerate(plain[position : position + portion]):
            result.append(value ^ (key & 0xFF))
            checksum = (checksum + value * (portion - index)) & 0xFFFF
            bit = (key >> 15) & 1
            key = (~(bit + ((key * 2) & 0xFFFFFFFF) + 0xA3B376C9)) & 0xFFFFFFFF
        position += portion
        if portion == 0x20:
            result.extend(u16(checksum))
    return bytes(result)


def _inverse_transpose(data: bytes, width: int) -> bytes:
    result = bytearray(len(data))
    chunks, tail = divmod(len(data), width)
    for row in range(chunks):
        for column in range(width):
            result[row + chunks * column] = data[row * width + column]
    if tail:
        result[-tail:] = data[-tail:]
    return bytes(result)


def encrypt_ici_plain(plain: bytes) -> bytes:
    """Inverse of the GARbro ICI permutation, then checksum-stream encode."""

    stage = bytearray(plain)
    chunks, _tail = divmod(len(stage), 3)
    xors = (0x18, 0x3F, 0xE2)
    for row in range(chunks):
        for column in range(3):
            stage[row * 3 + column] ^= xors[column]
    stage = bytearray(_inverse_transpose(stage, 3))

    previous = 0
    for index in range(len(stage) - 1, -1, -1):
        stage[index] = (stage[index] + previous) & 0xFF
        previous = stage[index]

    stage = bytearray(_inverse_transpose(stage, 5))
    previous = 0
    for index, encoded in enumerate(stage):
        delta = encoded ^ 0xA5
        stage[index] = (delta + previous) & 0xFF
        previous = stage[index]

    scrambled = _inverse_transpose(stage, 6)
    return encrypt_stream(scrambled, ICI_KEY)


def install_source(name: str, offset_units: int, size: int) -> bytes:
    value = bytearray()
    value += u16(7)
    value += i32(0) + i32(0) + u8(0) + short_string("")
    value += b"".join(short_string("") for _ in range(5))
    value += i64(0) + i64(size) + i32(0)
    value += short_string(name) + i64(offset_units) + i64(size)
    value += i32(0) + short_string("")
    value += b"".join(i32(0) for _ in range(5))
    value += short_string("") + u16(0)
    bitmap_length = ((((size + 0xFFFF) >> 16) + 7) >> 3)
    value += bytes(bitmap_length)
    return bytes(value)


def ici_plain(toc_offset: int, toc_size: int) -> bytes:
    value = bytearray()
    value += u32(ICI_SIGNATURE) + u16(0x11) + u16(0)
    root_name = b"CObjectArcMan"
    value += u16(0xFFFF) + u16(1) + u16(len(root_name)) + root_name
    value += u16(0)  # root class list
    value += i32(10) + i32(0) + u8(0) + u8(0)
    value += i32(0) + i32(0)
    value += i32(0) + i32(0) + i32(0)
    value += i32(toc_offset) + i32(toc_size) + i32(0)
    value += i32(0)
    value += short_string("Synthetic") + i32(0) + short_string("") + i32(0)
    value += short_string("") + short_string("") + short_string("")
    value += i32(0) + short_string("")
    value += u16(0) + i32(0)
    value += short_string("fixture.rio") + short_string("") + i32(0)
    value += u16(2)
    value += u8(1) + install_source("fixture.rio", 0, 0x200)
    value += u8(1) + install_source("fixture.rio.002", 0x200, 0x200)
    return bytes(value)


def encoded_node(class_name: str, offset_units: int, extent: int) -> bytes:
    encoded_offset = (offset_units + 0xA2FB6AD1) & 0xFFFFFFFF
    return (
        u16(8)
        + u16(0)
        + class_ref(class_name)
        + u32(encoded_offset)
        + u32(encode_extent_size(extent))
        + u16(0)
    )


def synthetic_toc() -> bytes:
    value = bytearray()
    value += u32(ENCRYPTED_SIGNATURE) + u16(0x11) + u16(0)
    value += class_ref("CrelicUnitedGameProject", schema=0x29)
    value += u16(2)
    value += encoded_node("CRsa", 0x100, 0x20)
    value += encoded_node("Cr6Ti", 0x220, 0x30)
    relic = i32(0x24) + u8(0) + (u16(0) * 6) + i32(0)
    value += encrypt_stream(relic, RIO_KEY)
    return bytes(value)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    toc = synthetic_toc()
    toc_offset = 0x20
    main = root / "fixture.rio"
    second = root / "fixture.rio.002"
    ici = root / "fixture.rio.ici"
    main.write_bytes(bytes(toc_offset) + toc + bytes(0x200 - toc_offset - len(toc)))
    second.write_bytes(bytes([0xCC]) * 0x200)
    ici.write_bytes(encrypt_ici_plain(ici_plain(toc_offset, len(toc))))
    return ici, main, second


class RioInventoryTests(unittest.TestCase):
    def test_rejects_unbounded_toc_and_nested_object_read_windows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            main = root / "oversized.rio"
            main.write_bytes(u32(ENCRYPTED_SIGNATURE))
            info = IciInfo(
                toc_offset=0,
                toc_size=MAX_DECODED_CHUNK_BYTES,
                rio_file_name=main.name,
            )
            with self.assertRaisesRegex(InventoryError, "TOC read window.*safety limit"):
                _find_toc(main, info)

            nested = root / "nested.rio"
            nested.write_bytes(bytes(0x1000))
            archive = RioArchive(b"")
            node = Node("oversized", "CBoxOcean", offset=0, size=MAX_DECODED_CHUNK_BYTES)
            with self.assertRaisesRegex(InventoryError, "object read window.*safety limit"):
                archive.read_object_from_file(node, nested)

    def test_parses_synthetic_ici_and_resolves_two_volumes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ici, main, second = write_fixture(root)
            before = {path.name: sha256(path) for path in (ici, main, second)}

            info = parse_ici(ici)
            self.assertEqual(info.toc_offset, 0x20)
            self.assertEqual([arc.rio_name for arc in info.arcs], ["fixture.rio", "fixture.rio.002"])

            report = build_inventory(
                ici=ici,
                main_rio=main,
                volumes=[second],
            )
            rows = {row["class"]: row for row in report["nodes"] if row["class"] in {"CRsa", "Cr6Ti"}}
            self.assertEqual(rows["CRsa"]["kind"], "script")
            self.assertEqual(rows["CRsa"]["volume"], "fixture.rio")
            self.assertEqual(rows["CRsa"]["volume_offset"], 0x100)
            self.assertEqual(rows["CRsa"]["extent"], 0x20)
            self.assertEqual(rows["Cr6Ti"]["kind"], "image")
            self.assertEqual(rows["Cr6Ti"]["volume"], "fixture.rio.002")
            self.assertEqual(rows["Cr6Ti"]["volume_offset"], 0x20)
            self.assertEqual(rows["Cr6Ti"]["global_offset"], 0x220)
            self.assertEqual(rows["Cr6Ti"]["extent"], 0x30)
            self.assertTrue(rows["Cr6Ti"]["within_declared_volume"])
            self.assertTrue(rows["Cr6Ti"]["within_provided_volume"])
            self.assertNotIn("CrelicUnitedGameProject/", rows["Cr6Ti"]["logical_path"])

            rendered = json.dumps(report, ensure_ascii=False)
            self.assertNotIn(str(root), rendered)
            self.assertEqual(before, {path.name: sha256(path) for path in (ici, main, second)})

    def test_cli_filters_csv_and_refuses_to_overwrite_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ici, main, second = write_fixture(root)
            args = parse_args(
                [
                    "--ici",
                    str(ici),
                    "--main-rio",
                    str(main),
                    "--volume",
                    str(second),
                    "--format",
                    "csv",
                    "--kind",
                    "image",
                ]
            )
            output = io.StringIO()
            result = run_cli(args, stdout=output)
            self.assertEqual(result["rows"], 1)
            csv_text = output.getvalue()
            self.assertIn("logical_path,logical_directory", csv_text)
            self.assertIn("Cr6Ti", csv_text)
            self.assertNotIn("CRsa", csv_text)

            collision = parse_args(
                [
                    "--ici",
                    str(ici),
                    "--main-rio",
                    str(main),
                    "--volume",
                    "fixture.rio.002=" + str(second),
                    "--output",
                    str(main),
                ]
            )
            original_hash = sha256(main)
            with self.assertRaisesRegex(InventoryError, "must not name"):
                run_cli(collision, stdout=io.StringIO())
            self.assertEqual(sha256(main), original_hash)

    def test_cli_writes_only_a_separate_portable_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ici, main, second = write_fixture(root)
            before = {path.name: sha256(path) for path in (ici, main, second)}
            report_path = root / "reports" / "inventory.json"
            args = parse_args(
                [
                    "--ici",
                    str(ici),
                    "--main-rio",
                    str(main),
                    "--volume",
                    str(second),
                    "--output",
                    str(report_path),
                ]
            )

            result = run_cli(args, stdout=io.StringIO())

            self.assertEqual(result["output"], "inventory.json")
            document = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(document["mode"], "read_only")
            self.assertEqual(document["source"]["ici_name"], "fixture.rio.ici")
            self.assertNotIn(str(root), report_path.read_text(encoding="utf-8"))
            self.assertEqual(before, {path.name: sha256(path) for path in (ici, main, second)})

            original_report = report_path.read_bytes()
            with self.assertRaisesRegex(InventoryError, "refusing to overwrite"):
                run_cli(args, stdout=io.StringIO())
            self.assertEqual(report_path.read_bytes(), original_report)
            self.assertEqual([], list(report_path.parent.glob(".inventory.json.*.tmp")))

    def test_csv_renderer_has_only_portable_catalog_fields(self) -> None:
        text = render_csv(
            [
                {
                    "logical_path": "ui/title",
                    "logical_directory": "ui",
                    "name": "title",
                    "class": "CRip008",
                    "kind": "image",
                    "volume": "fixture.rio",
                    "volume_offset": 16,
                    "global_offset": 16,
                    "extent": 32,
                    "flags": 8,
                    "schema": 1,
                    "volume_present": True,
                    "within_declared_volume": True,
                    "within_provided_volume": True,
                }
            ]
        )
        self.assertIn("ui/title", text)
        self.assertNotIn("C:\\", text)


if __name__ == "__main__":
    unittest.main()
