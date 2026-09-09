"""Read the standalone schema-1 CRmti records reached by PF/PM CRmt references.

These are not CRmt containers and have no four-byte inline-child wrapper:
``00 01`` is followed by the existing 18-byte CRmti header and its exact blob.
Only the observed 0x0707070F profile is accepted. Framing validation is separate
from pixel decoding; neither proves that the game displayed the image.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import struct

from .crmti_decode import CrmtiLevel, DecodeResult, MAX_PIXELS, decode_level


STANDALONE_PREFIX = b"\x00\x01"
STANDALONE_HEADER_BYTES = 20
STANDALONE_META = 0x0707070F
MAX_RECORD_BYTES = 256 * 1024 * 1024


class StandaloneCrmtiError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StandaloneCrmtiError(message)


@dataclass(frozen=True)
class StandaloneCrmtiHeader:
    width: int
    height: int
    meta: int
    blob_length: int
    decoded_size_hint: int
    active_row_count: int

    def to_bytes(self) -> bytes:
        return STANDALONE_PREFIX + struct.pack(
            "<HHIIIH", self.width, self.height, self.meta, self.blob_length,
            self.decoded_size_hint, self.active_row_count,
        )


@dataclass(frozen=True)
class StandaloneCrmtiRecord:
    header: StandaloneCrmtiHeader
    blob: bytes = field(repr=False)

    def to_bytes(self) -> bytes:
        raw_header = self.header.to_bytes()
        parse_standalone_header(raw_header, len(raw_header) + len(self.blob))
        return raw_header + self.blob

    def as_level(self) -> CrmtiLevel:
        """Adapt to the pixel codec; wrapper_offset=-1 means no inline wrapper."""
        raw_header = self.header.to_bytes()
        header = parse_standalone_header(raw_header, len(raw_header) + len(self.blob))
        return CrmtiLevel(
            index=0, width=header.width, height=header.height, meta=header.meta,
            blob_length=header.blob_length, decoded_size_hint=header.decoded_size_hint,
            active_row_count=header.active_row_count, wrapper_offset=-1,
            header_offset=2, blob_offset=STANDALONE_HEADER_BYTES,
            blob_end=STANDALONE_HEADER_BYTES + len(self.blob), blob=self.blob,
        )


def parse_standalone_header(header: bytes, record_extent: int) -> StandaloneCrmtiHeader:
    """Validate a bounded header against the externally established full extent.

This does not read or validate the compressed pixels. The decoded-size hint is
preserved, not treated as RGBA allocation size or required to equal width*height*4.
"""
    _require(type(record_extent) is int and STANDALONE_HEADER_BYTES < record_extent <= MAX_RECORD_BYTES,
             "standalone CRmti extent outside supported bounds")
    _require(len(header) == STANDALONE_HEADER_BYTES, "standalone CRmti header must be exactly 20 bytes")
    _require(header[:2] == STANDALONE_PREFIX, "unsupported standalone CRmti compact header")
    result = StandaloneCrmtiHeader(*struct.unpack("<HHIIIH", header[2:]))
    _require(result.width > 0 and result.height > 0, "invalid standalone CRmti dimensions")
    _require(result.width * result.height <= MAX_PIXELS, "standalone CRmti canvas exceeds pixel safety limit")
    _require(result.meta == STANDALONE_META, "unsupported standalone CRmti channel profile")
    _require(result.active_row_count <= result.height, "standalone CRmti active row count exceeds height")
    _require(result.blob_length > 0, "standalone CRmti blob is empty")
    _require(STANDALONE_HEADER_BYTES + result.blob_length == record_extent,
             "standalone CRmti declared blob does not exactly fill the record extent")
    return result


def parse_standalone_crmti(record: bytes) -> StandaloneCrmtiRecord:
    header = parse_standalone_header(record[:STANDALONE_HEADER_BYTES], len(record))
    result = StandaloneCrmtiRecord(header, bytes(record[STANDALONE_HEADER_BYTES:]))
    _require(result.to_bytes() == record, "standalone CRmti framing readback differs")
    return result


def decode_standalone_crmti(record: bytes) -> DecodeResult:
    return decode_level(parse_standalone_crmti(record).as_level())


__all__ = [
    "StandaloneCrmtiError", "StandaloneCrmtiHeader", "StandaloneCrmtiRecord",
    "parse_standalone_header", "parse_standalone_crmti", "decode_standalone_crmti",
]
