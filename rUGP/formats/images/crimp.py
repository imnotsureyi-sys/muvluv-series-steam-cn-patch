"""Sequential, lossless reader for the observed schema-4 CRimp property map.

CRimp is metadata, not a raster image. Four-byte values use the native tagged
variant representation; they must not be divided by 65536 as if they were raw
fixed-point scalars. Named Point32/Vector32 structures retain signed components
without asserting their scene-specific units or interpreting packed integers.

Supported scope: the PF/PM 121-record reachable union, with short Unicode names,
tagged integers, and the observed inline Point32/Vector32 descriptor. Other
profiles fail closed. The five post-map bytes are preserved, not interpreted.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

UNICODE_MARKER = b"\xff\xfe\xff"
INLINE_DESCRIPTOR = bytes.fromhex("1a 2f 00 00")
STRUCT_COUNTS = {"_CPoint32": 2, "_CVector32": 3}


class CrimpDecodeError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CrimpDecodeError(message)


@dataclass(frozen=True)
class CrimpValue:
    kind: str
    integer: int | None = None
    struct_name: str | None = None
    components_i32: tuple[int, ...] = ()

    def to_bytes(self) -> bytes:
        if self.kind == "tagged_integer":
            _require(type(self.integer) is int and -(1 << 29) <= self.integer < (1 << 29),
                     "integer does not fit the signed 30-bit tagged representation")
            _require(self.struct_name is None and not self.components_i32, "integer has struct fields")
            return struct.pack("<I", ((self.integer << 2) | 2) & 0xFFFFFFFF)
        _require(self.kind == "inline_struct" and self.struct_name in STRUCT_COUNTS,
                 "unsupported CRimp value kind")
        _require(self.integer is None, "struct has an integer field")
        count = STRUCT_COUNTS[self.struct_name]
        _require(len(self.components_i32) == count and all(type(x) is int and -(1 << 31) <= x < (1 << 31)
                 for x in self.components_i32), "invalid raw struct components")
        name = self.struct_name.encode("ascii")
        return (struct.pack("<I", 4) + INLINE_DESCRIPTOR + struct.pack("<H", len(name)) + name
                + struct.pack("<" + "i" * count, *self.components_i32))

    def as_dict(self) -> dict:
        if self.kind == "tagged_integer":
            return {"type": self.kind, "tag_word_hex": "0x" + self.to_bytes()[::-1].hex().upper(),
                    "value": self.integer, "semantic_units": "not_established"}
        return {"type": self.kind, "struct_name": self.struct_name,
                "components_i32": list(self.components_i32),
                "component_units": "not_established", "descriptor_hex": INLINE_DESCRIPTOR.hex(" ")}


def decode_value(data: bytes, offset: int = 0) -> tuple[CrimpValue, int]:
    """Decode exactly one value, returning its end without scanning for markers."""
    _require(0 <= offset and offset + 4 <= len(data), "truncated CRimp value tag")
    tag = struct.unpack_from("<I", data, offset)[0]
    if tag & 3 == 2:
        value = struct.unpack_from("<i", data, offset)[0] >> 2
        return CrimpValue("tagged_integer", integer=value), offset + 4
    _require(tag == 4, f"unsupported CRimp value tag 0x{tag:08X}")
    _require(offset + 10 <= len(data), "truncated inline descriptor")
    _require(data[offset + 4:offset + 8] == INLINE_DESCRIPTOR, "unsupported inline descriptor profile")
    name_length = struct.unpack_from("<H", data, offset + 8)[0]
    _require(0 < name_length <= 64 and offset + 10 + name_length <= len(data), "invalid inline type name length")
    try:
        name = data[offset + 10:offset + 10 + name_length].decode("ascii")
    except UnicodeDecodeError as exc:
        raise CrimpDecodeError("non-ASCII inline type name") from exc
    _require(name in STRUCT_COUNTS, "unsupported inline struct type")
    count = STRUCT_COUNTS[name]
    body = offset + 10 + name_length
    end = body + count * 4
    _require(end <= len(data), "truncated inline struct body")
    components = struct.unpack_from("<" + "i" * count, data, body)
    return CrimpValue("inline_struct", struct_name=name, components_i32=components), end


def _decode_name(data: bytes, offset: int) -> tuple[str, int]:
    _require(offset + 4 <= len(data) and data[offset:offset + 3] == UNICODE_MARKER,
             "missing short Unicode property name")
    count = data[offset + 3]
    _require(count != 0xFF, "extended property-name length is outside this profile")
    end = offset + 4 + count * 2
    _require(end <= len(data), "truncated Unicode property name")
    try:
        return data[offset + 4:end].decode("utf-16le", errors="strict"), end
    except UnicodeDecodeError as exc:
        raise CrimpDecodeError("invalid UTF-16 property name") from exc


def _encode_name(name: str) -> bytes:
    try:
        raw = name.encode("utf-16le", errors="strict")
    except UnicodeEncodeError as exc:
        raise CrimpDecodeError("invalid Unicode property name") from exc
    count = len(raw) // 2
    _require(count < 0xFF, "extended property-name length is outside this profile")
    return UNICODE_MARKER + bytes((count,)) + raw


@dataclass(frozen=True)
class CrimpProperty:
    name: str
    value: CrimpValue
    name_offset: int
    value_offset: int
    end_offset: int


@dataclass(frozen=True)
class CrimpRecord:
    properties: tuple[CrimpProperty, ...]
    post_map_bytes: bytes

    def to_bytes(self) -> bytes:
        _require(len(self.properties) <= 4096 and len(self.post_map_bytes) == 5, "unsupported CRimp record profile")
        parts = [b"\x00\x04", struct.pack("<H", len(self.properties))]
        seen = set()
        for prop in self.properties:
            _require(bool(prop.name) and prop.name not in seen, "empty or duplicate property name")
            seen.add(prop.name)
            parts.extend((_encode_name(prop.name), prop.value.to_bytes()))
        return b"".join(parts) + self.post_map_bytes + _encode_name("")


def parse_crimp(data: bytes) -> CrimpRecord:
    _require(13 <= len(data) <= 1024 * 1024, "CRimp record size outside supported bounds")
    _require(data[:2] == b"\x00\x04", "unsupported CRimp header profile")
    count = struct.unpack_from("<H", data, 2)[0]
    _require(count <= 4096 and count * 10 <= len(data) - 13, "property count exceeds remaining bytes")
    properties, seen, cursor = [], set(), 4
    for _ in range(count):
        name_offset = cursor
        name, cursor = _decode_name(data, cursor)
        _require(bool(name) and name not in seen, "empty or duplicate property name")
        seen.add(name)
        value_offset = cursor
        value, cursor = decode_value(data, cursor)
        properties.append(CrimpProperty(name, value, name_offset, value_offset, cursor))
    _require(cursor + 9 == len(data), "unexpected post-map extent or trailing data")
    post_map = data[cursor:cursor + 5]
    terminal, end = _decode_name(data, cursor + 5)
    _require(terminal == "" and end == len(data), "nonempty or invalid terminal name")
    record = CrimpRecord(tuple(properties), post_map)
    _require(record.to_bytes() == data, "CRimp lossless readback mismatch")
    return record


__all__ = ["CrimpDecodeError", "CrimpValue", "CrimpProperty", "CrimpRecord", "decode_value", "parse_crimp"]
