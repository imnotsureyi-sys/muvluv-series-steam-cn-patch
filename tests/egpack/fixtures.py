from __future__ import annotations

import zlib


FIELD_ORDER = (
    "zh_hans",
    "pt",
    "pt_br",
    "de",
    "jp",
    "zh_hant",
    "es",
    "it",
    "id",
    "fr",
    "en",
)

LANGUAGE_SLOTS = tuple(slot for slot in FIELD_ORDER if slot != "id")
HEADER = (
    b"EPK\0\x03\x02\x40\0\0\0\0\0"
    b"\0de\0en\0es\0fr\0id\0it\0jp\0pt\0pt_br\0zh_hans\0zh_hant\0"
)


def field_key(slot: str) -> bytes:
    return (zlib.crc32(slot.encode("ascii")) & 0xFFFFFFFF).to_bytes(4, "little")


def encode_field(slot: str, value: str | bytes) -> bytes:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return b"\x87" + field_key(slot) + b"\xa6" + raw + b"\0"


def finalize_egpack(body: bytes) -> bytes:
    data = HEADER + body
    return data[:8] + len(data).to_bytes(4, "little") + data[12:]


def build_egpack(records: list[dict[str, str | bytes]]) -> bytes:
    body = b"".join(
        encode_field(slot, record.get(slot, ""))
        for record in records
        for slot in FIELD_ORDER
    )
    return finalize_egpack(body)

