from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
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
LANGUAGE_SLOTS = tuple(field for field in FIELD_ORDER if field != "id")
FIELD_KEYS = {
    field: (zlib.crc32(field.encode("ascii")) & 0xFFFFFFFF).to_bytes(4, "little")
    for field in FIELD_ORDER
}
KEY_FIELDS = {key: field for field, key in FIELD_KEYS.items()}
CONTROL_RE = re.compile(r"\\[A-Za-z]+")


class EgpackFormatError(ValueError):
    pass


@dataclass(frozen=True)
class EgpackField:
    slot: str
    crc32_hex: str
    field_offset: int
    value_offset: int
    value_length: int
    text: str


@dataclass(frozen=True)
class EgpackRecord:
    index: int
    text_id: str
    id_offset: int
    slots: dict[str, EgpackField]


@dataclass(frozen=True)
class EgpackDocument:
    source: str
    data: bytes
    declared_size: int
    records: tuple[EgpackRecord, ...]


def _fail(source: str, message: str) -> EgpackFormatError:
    return EgpackFormatError(f"{source}: {message}")


def _scan_fields(data: bytes, source: str) -> list[EgpackField]:
    fields: list[EgpackField] = []
    offset = 0
    while offset + 6 <= len(data):
        if data[offset] != 0x87 or data[offset + 5] != 0xA6:
            offset += 1
            continue

        key = data[offset + 1 : offset + 5]
        slot = KEY_FIELDS.get(key)
        if slot is None:
            offset += 1
            continue

        value_offset = offset + 6
        value_end = data.find(b"\0", value_offset)
        if value_end < 0:
            raise _fail(source, f"unterminated {slot} field at offset 0x{offset:X}")
        raw = data[value_offset:value_end]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            bad_offset = value_offset + exc.start
            raise _fail(source, f"invalid UTF-8 at offset 0x{bad_offset:X} in {slot} field") from exc

        fields.append(
            EgpackField(
                slot=slot,
                crc32_hex=key.hex(),
                field_offset=offset,
                value_offset=value_offset,
                value_length=len(raw),
                text=text,
            )
        )
        offset = value_end + 1
    return fields


def parse_egpack_bytes(data: bytes, source: str = "<memory>") -> EgpackDocument:
    if len(data) < 12:
        raise _fail(source, "file is shorter than the 12-byte EPK header")
    if not data.startswith(b"EPK\0"):
        raise _fail(source, "invalid EPK magic")

    declared_size = int.from_bytes(data[8:12], "little")
    if declared_size != len(data):
        raise _fail(source, f"declared size {declared_size} does not match actual size {len(data)}")

    fields = _scan_fields(data, source)
    width = len(FIELD_ORDER)
    if not fields or len(fields) % width:
        raise _fail(source, f"field count {len(fields)} is not divisible by {width}")

    records: list[EgpackRecord] = []
    seen_ids: set[str] = set()
    for index in range(0, len(fields), width):
        chunk = fields[index : index + width]
        actual_order = tuple(field.slot for field in chunk)
        if actual_order != FIELD_ORDER:
            record_number = index // width
            start = chunk[0].field_offset if chunk else 0
            raise _fail(
                source,
                f"record {record_number} has unsupported field layout at offset 0x{start:X}: "
                f"{actual_order!r}",
            )

        by_slot = {field.slot: field for field in chunk}
        id_field = by_slot["id"]
        if not id_field.text:
            raise _fail(source, f"record {index // width} has an empty id at offset 0x{id_field.value_offset:X}")
        if id_field.text in seen_ids:
            raise _fail(source, f"duplicate id {id_field.text!r} at offset 0x{id_field.value_offset:X}")
        seen_ids.add(id_field.text)

        records.append(
            EgpackRecord(
                index=index // width,
                text_id=id_field.text,
                id_offset=id_field.value_offset,
                slots={slot: by_slot[slot] for slot in LANGUAGE_SLOTS},
            )
        )

    return EgpackDocument(
        source=source,
        data=data,
        declared_size=declared_size,
        records=tuple(records),
    )


def parse_egpack(path: Path) -> EgpackDocument:
    return parse_egpack_bytes(path.read_bytes(), source=str(path))


def classify_resource(path: str, text_id: str) -> str:
    filename = Path(path.replace("\\", "/")).name
    if text_id.endswith("_ruby"):
        return "ruby"
    if filename == "__speakers__.egpack" or re.fullmatch(r"(?:game|tda\d+)_s\d+", text_id):
        return "speaker"
    if (
        filename == "__staffroll__.egpack"
        or text_id == "staff90000"
        or re.fullmatch(r"(?:game|tda\d+)_staff\d+", text_id)
    ):
        return "staffroll"
    if re.fullmatch(r"(?:game|tda\d+)_t\d+", text_id):
        return "scene"
    return "unknown"


def extract_control_codes(text: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in CONTROL_RE.finditer(text))


def is_control_only(text: str) -> bool:
    if not text:
        return False
    visible = CONTROL_RE.sub("", text).strip()
    return not visible
