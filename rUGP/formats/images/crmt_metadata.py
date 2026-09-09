"""Read the five observed PF/PM CRmt parent-metadata profiles.

Unlike a search for an adjacent CRimp extent, this reader replays the compact
record header, two dependency references, the intervening archive-object slot,
and three class registrations before resolving the actual ImageMP field.
It does not decode pixels, execute a scene, or modify a resource.

The cache ordering and origin calculation are tied to the retail PF/PM native
profiles documented in ``crmt-imagemp-links.json``. Other archive layouts,
versions, class names, inline dependencies and recursive external parents are
deliberately rejected, not assigned guessed cache slots.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct

from .crimp import CrimpRecord
from .crmti_decode import CRMT_LAYOUTS


class CrmtMetadataError(ValueError):
    pass


def _require(value: bool, message: str) -> None:
    if not value:
        raise CrmtMetadataError(message)


@dataclass(frozen=True)
class ResourceExtent:
    class_name: str
    schema: int
    flags: int
    raw_key: int
    raw_size: int
    global_offset: int
    extent: int
    class_cache_index: int
    object_cache_index: int
    parent_cache_index: int
    reference_start: int
    reference_end: int


@dataclass(frozen=True)
class ResourceReference:
    kind: str
    start: int
    end: int
    cache_index: int
    resource: ResourceExtent | None = None


@dataclass(frozen=True)
class CrmtMetadata:
    schema: int
    version: int
    width: int
    height: int
    scale_i32: tuple[int, int]
    base_offset_i32: tuple[int, int]
    field_33_u8: int
    field_34_u16: int
    field_40_u32: int
    ancestor_count: int
    dependencies: tuple[ResourceReference, ResourceReference]
    post_dependency_cache_index: int
    registered_classes: tuple[tuple[str, int, int], ...]
    image_mp: ResourceReference
    mip_count: int
    count_offset: int
    first_mip_class_index: int
    preamble: bytes

    def as_dict(self) -> dict:
        result = asdict(self)
        result.pop("preamble")
        for name in ("scale_i32", "base_offset_i32", "dependencies"):
            result[name] = list(result[name])
        result["registered_classes"] = [list(row) for row in self.registered_classes]
        result["preamble_bytes"] = len(self.preamble)
        result["preamble_sha256"] = hashlib.sha256(self.preamble).hexdigest().upper()
        result["effective_scale_i32"] = [self.scale_i32[0], self.scale_i32[1] or self.scale_i32[0]]
        return result


class _Reader:
    # These are the two compressed declarations present in the audited parent
    # headers. They are not a general compressed-class-name implementation.
    NAMES = {bytes.fromhex("3c a1 e5"): ("CRimp", 4),
             bytes.fromhex("3c 35 e4"): ("CRmti", 1)}

    def __init__(self, data: bytes):
        self.data, self.pos = data, 3
        # Native: null, archive seed object, owner class, owner object.
        # Ancestor identities and the seed object's scene identity remain opaque.
        self.cache: list[tuple[str, object]] = [
            ("null", None), ("opaque", "archive_seed"),
            ("class", ("owner_class", 4)), ("opaque", "owner_object")]
        self.preloaded = False
        self.ancestor_count = 0

    def take(self, size: int) -> bytes:
        _require(size >= 0 and self.pos + size <= len(self.data), "truncated CRmt metadata")
        result = self.data[self.pos:self.pos + size]
        self.pos += size
        return result

    def number(self, fmt: str) -> int:
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))[0]

    def append(self, kind: str, value: object) -> int:
        _require(len(self.cache) < 128, "metadata cache exceeds supported bounds")
        index = len(self.cache)
        self.cache.append((kind, value))
        return index

    def slot(self, index: int) -> tuple[str, object]:
        _require(0 <= index < len(self.cache), "metadata alias is outside the established cache")
        return self.cache[index]

    def class_tag(self, word: int) -> tuple[int, str, int]:
        if word == 0xFFFF:
            schema, size = self.number("H"), self.number("B")
            _require(0 < size <= 64, "unsupported compressed class-name size")
            name = self.NAMES.get(self.take(size))
            _require(name is not None and name[1] == schema, "unsupported dependency class/schema")
            index = self.append("class", name)
            return index, name[0], schema
        _require(bool(word & 0x8000), "expected a cached class tag")
        index = word & 0x7FFF
        kind, value = self.slot(index)
        _require(kind == "class", "class alias addresses a non-class slot")
        name, schema = value
        return index, name, schema

    def reference(self) -> ResourceReference:
        if not self.preloaded:
            count = self.number("B")
            count = self.number("H") if count == 0xFF else count
            _require(count in (5, 6), "unsupported CRmt ancestor count")
            self.ancestor_count, self.preloaded = count, True
            for _ in range(count):
                self.append("opaque", "ancestor")
        start, word = self.pos, self.number("H")
        _require(word != 0x7FFF, "extended reference tags are outside this metadata profile")
        if not word & 0x8000:
            kind, value = self.slot(word)
            _require(kind != "class", "object alias addresses a class slot")
            _require(kind in ("null", "resource"), "resource alias has an opaque identity")
            return ResourceReference("null" if kind == "null" else "object_alias",
                                     start, self.pos, word, value)
        class_index, name, schema = self.class_tag(word)
        flags, raw_key, raw_size = self.number("H"), self.number("I"), self.number("I")
        _require(flags in (0xC108, 0xC308), "unsupported external dependency flags")
        parent = self.number("H")
        _require(parent != 0x7FFF and not parent & 0x8000,
                 "recursive or extended external parents are outside this metadata profile")
        parent_kind, _ = self.slot(parent)
        _require(parent_kind != "class", "external parent alias addresses a class slot")
        _require(self.take(1) == b"\0", "unsupported external dependency tail")
        offset = ((raw_key - 0xA2FB6AD1) & 0xFFFFFFFF) * 4
        size_word = (raw_size - 0xE7B5D9F8) & 0xFFFFFFFF
        high = size_word >> 13
        extent = (((size_word - (high & 0xFFF)) << 19) | high) & 0xFFFFFFFF
        _require(extent > 0, "empty external dependency extent")
        value = ResourceExtent(name, schema, flags, raw_key, raw_size, offset, extent,
                               class_index, len(self.cache), parent, start, self.pos)
        index = self.append("resource", value)
        return ResourceReference("external", start, self.pos, index, value)


def parse_crmt_metadata(record: bytes) -> CrmtMetadata:
    """Read a parent preamble and validate its first mip wrapper, without pixels.

The input may be an entire CRmt record or a bounded header window ending at or
after its first four-byte mip wrapper. Use ``parse_crmt`` separately to validate
every child/blob extent. Source width/height are unsigned serialized words;
``crmt_origin`` reproduces the signed-word reads of the native origin fallback.
"""
    layouts = CRMT_LAYOUTS.get(record[:4])
    _require(layouts is not None, "unsupported CRmt compact-header profile")
    reader = _Reader(record)
    dependencies = (reader.reference(), reader.reference())
    for ref, expected in zip(dependencies, (("CRimp", 4), ("CRmti", 1)), strict=True):
        _require(ref.resource is None or (ref.resource.class_name, ref.resource.schema) == expected,
                 "dependency has an unexpected type")
    # The generic native loader maps archive field +D4 here, AFTER dependencies
    # and BEFORE the CRmt serializer. Omitting it shifts the mip class by one.
    extra_index = reader.append("opaque", "post_dependency_archive_object")
    registrations = []
    for name, expected in (("CRmti", 1), ("CRimp", 4), ("Cr6Ti", 4)):
        schema = reader.number("H")
        _require(schema == expected, "unsupported registered class schema")
        registrations.append((name, schema, reader.append("class", (name, schema))))
    version, width, height = reader.number("H"), reader.number("H"), reader.number("H")
    _require(version == 10 and width > 0 and height > 0, "unsupported CRmt version or dimensions")
    scale = (reader.number("i"), reader.number("i"))
    base_offset = (reader.number("i"), reader.number("i"))
    field_33, field_34, field_40 = reader.number("B"), reader.number("H"), reader.number("I")
    image_mp = reader.reference()
    _require(image_mp.resource is None or
             (image_mp.resource.class_name, image_mp.resource.schema) == ("CRimp", 4),
             "ImageMP does not address a CRimp")
    count_offset, mip_count = reader.pos, reader.number("B")
    _require(1 <= mip_count <= 6, "mip count is outside the audited native CRmt profile")
    wrapper = reader.take(4)
    _require((count_offset, wrapper) in layouts, "metadata does not end at an audited mip table")
    word, flags = struct.unpack("<HH", wrapper)
    class_index, name, schema = reader.class_tag(word)
    _require((name, schema, flags) == ("CRmti", 1, 0xC040),
             "first mip wrapper does not address registered inline CRmti")
    return CrmtMetadata(4, version, width, height, scale, base_offset, field_33, field_34,
                        field_40, reader.ancestor_count, dependencies, extra_index,
                        tuple(registrations), image_mp, mip_count, count_offset,
                        class_index, bytes(record[:count_offset + 1]))


def _i32(value: int) -> int:
    return ((value + (1 << 31)) & 0xFFFFFFFF) - (1 << 31)


def _i16(value: int) -> int:
    return ((value + (1 << 15)) & 0xFFFF) - (1 << 15)


def crmt_origin(metadata: CrmtMetadata, image_mp: CrimpRecord | None) -> dict:
    """Reproduce an uncached retail CRmt origin query from serialized values.

This is a static projection, not a scene position or a runtime observation.
The caller must provide the CRimp at ``metadata.image_mp``; passing ``None``
for a non-null ImageMP fails. The native function does not read 標準視点 here.
"""
    _require((metadata.image_mp.resource is None) == (image_mp is None),
             "ImageMP record presence does not match the resolved reference")
    props = {} if image_mp is None else {p.name: p.value for p in image_mp.properties}
    origin = props.get("原点")
    if origin is not None and origin.kind == "inline_struct" and origin.struct_name == "_CPoint32":
        result = tuple(_i32(a - b) for a, b in zip(origin.components_i32,
                                                  metadata.base_offset_i32, strict=True))
        branch = "point32_origin_minus_base_offset"
    elif origin is not None and origin.kind == "tagged_integer":
        value = origin.integer
        result = (_i32(_i16(value) << 16), _i32(_i16(value >> 16) << 16))
        branch = "packed_integer_origin"
    else:
        fallback = props.get("基準立ち位置Y")
        if fallback is not None and fallback.kind == "tagged_integer":
            value = fallback.integer
            result = tuple(_i32(a + b) for a, b in zip(
                (_i16(value) << 16, _i16(value >> 16) << 16), metadata.base_offset_i32, strict=True))
            branch = "packed_baseline_plus_base_offset"
        else:
            result = (_i16(metadata.width) * 32768, _i16(metadata.height) << 16)
            branch = "default_bottom_center"
    return {"branch": branch, "components_i32": list(result),
            "coordinate_format": "signed_16.16_in_CRmt_origin_query",
            "pixel_projection": [x / 65536 for x in result],
            "runtime_observed": False, "scene_position_established": False}


__all__ = ["CrmtMetadataError", "ResourceExtent", "ResourceReference", "CrmtMetadata",
           "parse_crmt_metadata", "crmt_origin"]
