#!/usr/bin/env python3
#
# The rUGP object-directory decoding in this file is a Python port of:
#   GARbro/ArcFormats/rUGP/ArcRIO.cs
#   https://github.com/morkt/GARbro/blob/b09ee4570ccb1daf6ac56710ee8934dc0b8baeb0/ArcFormats/rUGP/ArcRIO.cs
#
# Copyright (C) 2016 by morkt
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
"""Export a read-only logical inventory from an rUGP ``.ici`` and RIO volumes.

Only object-directory metadata is decoded.  This module never extracts,
decrypts, rewrites, or repacks resource payloads, and every game input is
opened read-only.  JSON is written to stdout by default; ``--output`` may be
used for a separate report file.

The directory decoder is a maintained Python port of GARbro's MIT-licensed
``ArcFormats/rUGP/ArcRIO.cs``.  Project-specific additions include newer image
class labels, multi-volume resolution, portable report fields, and stricter
bounds/error checks.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence, TextIO


ICI_KEY = 0xB29D5A0C
RIO_KEY = 0x7E6B8CE2

ICI_SIGNATURE = 0x673CE92A
ENCRYPTED_SIGNATURE = 0x1EDB927C
RIO_SIGNATURE = 0x596E32CD
OBJECT_SIGNATURE = 0x29F6CBA4

MAX_ICI_FILE_BYTES = 128 * 1024 * 1024
MAX_DECODED_CHUNK_BYTES = 128 * 1024 * 1024
MAX_CLASS_LIST_DEPTH = 40

SUPPORTED_CLASSES = {
    "CRip007": "image",
    "CRip008": "image",
    "CRip": "image",
    "Cr6Ti": "image",
    "CS5i": "image",
    "CIcon": "image",
    "CBg2d": "image",
    "CRsa": "script",
    "CVmFunc": "script",
    "CWaveAudio": "audio",
    "CrelicHicompAudio": "audio",
}

CSV_COLUMNS = (
    "logical_path",
    "logical_directory",
    "name",
    "class",
    "kind",
    "volume",
    "volume_offset",
    "global_offset",
    "extent",
    "flags",
    "schema",
    "volume_present",
    "within_declared_volume",
    "within_provided_volume",
)


class InventoryError(ValueError):
    """The supplied archive metadata is unsupported, invalid, or incomplete."""


def _read_exact(stream: TextIO | Any, count: int) -> bytes:
    data = stream.read(count)
    if len(data) != count:
        raise EOFError(f"unexpected EOF: needed {count} bytes, got {len(data)}")
    return data


def decoded_size_from_header(header: bytes) -> int:
    """Return the plaintext size encoded in an rUGP encrypted-stream header."""

    if len(header) != 8:
        raise EOFError("encrypted chunk header is truncated")
    size1 = int.from_bytes(header[:4], "little") ^ 0xC92E568B
    size2 = int.from_bytes(header[4:8], "little") ^ 0xC92E568F
    size2 >>= 3
    size1 = (~size1) & 0xFFFFFFFF
    if size1 != size2:
        raise InventoryError(f"invalid encrypted chunk size: {size1=} {size2=}")
    if size1 > MAX_DECODED_CHUNK_BYTES:
        raise InventoryError(
            f"encrypted chunk expands to {size1} bytes; safety limit is "
            f"{MAX_DECODED_CHUNK_BYTES}"
        )
    return size1


def read_encrypted_from_bytes(data: bytes, key: int, offset: int = 0) -> tuple[bytes, int]:
    """Decode one checksum-framed rUGP stream without modifying ``data``."""

    if offset < 0 or offset + 8 > len(data):
        raise EOFError("encrypted chunk offset is outside the input")
    size = decoded_size_from_header(data[offset : offset + 8])
    pos = offset + 8
    out = bytearray(size)
    dst = 0
    while dst < size:
        checksum = 0
        portion = min(0x20, size - dst)
        if pos + portion > len(data):
            raise EOFError("unexpected EOF in encrypted payload")
        chunk = data[pos : pos + portion]
        pos += portion
        for index, encrypted_byte in enumerate(chunk):
            weight = portion - index
            plain_byte = encrypted_byte ^ (key & 0xFF)
            out[dst] = plain_byte
            dst += 1
            checksum = (checksum + plain_byte * weight) & 0xFFFF
            bit = (key >> 15) & 1
            key = (~(bit + ((key * 2) & 0xFFFFFFFF) + 0xA3B376C9)) & 0xFFFFFFFF
        if portion < 0x20:
            break
        if pos + 2 > len(data):
            raise EOFError("encrypted chunk checksum is truncated")
        stored = int.from_bytes(data[pos : pos + 2], "little")
        pos += 2
        if stored != checksum:
            raise InventoryError("encrypted chunk checksum mismatch")
    return bytes(out), pos


def read_encrypted_file(path: Path, key: int) -> bytes:
    """Read and decrypt a small metadata stream from ``path``."""

    file_size = path.stat().st_size
    if file_size > MAX_ICI_FILE_BYTES:
        raise InventoryError(
            f"ICI file is unexpectedly large ({file_size} bytes); safety limit is "
            f"{MAX_ICI_FILE_BYTES}"
        )
    with path.open("rb") as stream:
        data = stream.read()
    plain, _end = read_encrypted_from_bytes(data, key)
    return plain


def decrypt_ici(data: bytes) -> bytes:
    """Apply the CObjectArcMan permutation used after ICI stream decryption."""

    inp = bytearray(data)
    out = bytearray(len(inp))

    src = dst = 0
    chunk_count, tail_size = divmod(len(inp), 6)
    for _ in range(chunk_count):
        for index in range(6):
            out[dst + index] = inp[src + chunk_count * index]
        src += 1
        dst += 6
    if tail_size:
        out[dst:] = inp[len(inp) - tail_size :]

    accumulator = 0
    for index, value in enumerate(out):
        value = (value - accumulator) & 0xFF
        accumulator = (accumulator + value) & 0xFF
        out[index] = value ^ 0xA5

    inp = bytearray(len(out))
    src = dst = 0
    chunk_count, tail_size = divmod(len(out), 5)
    for _ in range(chunk_count):
        for index in range(5):
            inp[dst + index] = out[src + chunk_count * index]
        src += 1
        dst += 5
    if tail_size:
        inp[dst:] = out[len(out) - tail_size :]

    accumulator = 0
    for index in range(len(inp) - 1, -1, -1):
        value = (inp[index] - accumulator) & 0xFF
        inp[index] = value
        accumulator = (accumulator + value) & 0xFF

    out = bytearray(len(inp))
    src = dst = 0
    chunk_count, tail_size = divmod(len(inp), 3)
    xors = (0x18, 0x3F, 0xE2)
    for _ in range(chunk_count):
        for index in range(3):
            out[dst + index] = inp[src + chunk_count * index] ^ xors[index]
        src += 1
        dst += 3
    if tail_size:
        out[dst:] = inp[len(inp) - tail_size :]
    return bytes(out)


class Reader:
    """Little-endian, bounds-checked reader for decoded rUGP metadata."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def seek(self, pos: int) -> None:
        if not 0 <= pos <= len(self.data):
            raise EOFError(f"seek outside input: {pos}")
        self.pos = pos

    def _take(self, count: int) -> bytes:
        if count < 0 or self.pos + count > len(self.data):
            raise EOFError(
                f"unexpected EOF at {self.pos}: needed {count} bytes, "
                f"have {len(self.data) - self.pos}"
            )
        value = self.data[self.pos : self.pos + count]
        self.pos += count
        return value

    def u8(self) -> int:
        return self._take(1)[0]

    def u16(self) -> int:
        return int.from_bytes(self._take(2), "little")

    def i32(self) -> int:
        return int.from_bytes(self._take(4), "little", signed=True)

    def u32(self) -> int:
        return int.from_bytes(self._take(4), "little")

    def i64(self) -> int:
        return int.from_bytes(self._take(8), "little", signed=True)

    def bytes(self, count: int) -> bytes:
        return self._take(count)

    def string(self) -> str:
        length = self.u8()
        if length < 0xFF:
            return self.bytes(length).decode("cp932", "replace") if length else ""

        length2 = self.u16()
        if length2 == 0xFFFE:
            char_count = self.u8()
            if char_count == 0xFF:
                char_count = self.u16()
            return (
                self.bytes(char_count * 2).decode("utf-16le", "replace")
                if char_count
                else ""
            )

        if length2 < 0xFFFF:
            return self.bytes(length2).decode("cp932", "replace") if length2 else ""

        length4 = self.i32()
        if length4 < 0:
            raise InventoryError(f"negative string length: {length4}")
        return self.bytes(length4).decode("cp932", "replace") if length4 else ""

    def count(self) -> int:
        count = self.u16()
        count = count if count != 0xFFFF else self.i32()
        if count < 0:
            raise InventoryError(f"negative collection count: {count}")
        return count

    def short_count(self) -> int:
        count = self.u8()
        return count if count != 0xFF else self.u16()


class LsbBits:
    def __init__(self, data: bytes):
        self.data = data
        self.bit = 0

    def get(self, count: int = 1) -> int:
        value = 0
        for index in range(count):
            if self.bit >= len(self.data) * 8:
                return -1
            value |= ((self.data[self.bit // 8] >> (self.bit % 8)) & 1) << index
            self.bit += 1
        return value


CHAR_MAP1 = tuple("eaitrosducmnSglR")
CHAR_MAP2 = ("\x01", "C", "O", "F", "L", "f", "B", "M", "x", "p", "h", "y", "A", "V", "b", "I")
CHAR_MAP3 = tuple("EHTDPWXkqvNjwGz02U_K15JQZ467839\x00")


def decode_class_name(encoded: bytes) -> str:
    bits = LsbBits(encoded)
    out: list[str] = []
    if bits.get() == 0:
        out.append("C")
    while True:
        bit = bits.get()
        if bit == -1:
            break
        if bit == 0:
            index = bits.get(4)
            if index == -1:
                break
            char = CHAR_MAP1[index]
        elif bits.get() != 0:
            index = bits.get(5)
            if index == -1:
                break
            char = CHAR_MAP3[index]
        else:
            index = bits.get(4)
            if index == -1:
                break
            if index:
                char = CHAR_MAP2[index]
            else:
                value = bits.get(8)
                if value == -1:
                    break
                char = chr(value)
        if char == "\x00":
            break
        out.append(char)
    return "".join(out)


@dataclass
class Node:
    name: str
    class_name: str | None = None
    parent: "Node | None" = None
    flags: int = 0
    offset: int = 0
    size: int = 0
    schema: int = -1
    decoded: bool = False
    is_root: bool = False

    def path(self) -> str:
        parts: list[str] = []
        node: Node | None = self
        while node is not None and not node.is_root and node.class_name and node.name:
            parts.append(node.name)
            node = node.parent
        return "/".join(reversed(parts))


@dataclass(frozen=True)
class ArcInfo:
    rio_name: str
    rio_offset: int
    rio_size: int


@dataclass
class IciInfo:
    toc_offset: int
    toc_size: int
    rio_file_name: str
    arcs: list[ArcInfo] = field(default_factory=list)


class RioArchive:
    def __init__(self, data: bytes, shift: int = 0, encrypted: bool = False):
        self.reader = Reader(data)
        self.shift = shift
        self.field_4c = 4 if encrypted else 0
        self.field_54 = 0
        self.field_60 = False
        self.load_array: list[Any] = [None, self]
        self.ocean_map: dict[int, Node] = {}
        self.nodes: list[Node] = []
        self.object_schema = -1
        self._class_list_depth = 0

    @property
    def is_encrypted(self) -> bool:
        return bool(self.field_4c & 4)

    def map_object(self, obj: Any) -> None:
        self.load_array.append(obj)

    def load_type_core(self) -> tuple[int, int, int | None, str]:
        signature = self.reader.u32()
        if signature not in {
            ICI_SIGNATURE,
            ENCRYPTED_SIGNATURE,
            RIO_SIGNATURE,
            OBJECT_SIGNATURE,
        }:
            raise InventoryError(
                f"invalid RIO signature {signature:08x} at {self.reader.pos - 4}"
            )
        version = self.reader.u16()
        flags = None
        if 0x10 <= version <= 0x3FFF:
            if version >= 0x11:
                flags = self.reader.u16()
                self.field_4c = (self.field_4c & 0xFFFF) | (flags << 16)
        else:
            self.reader.seek(self.reader.pos - 2)
        if signature == ENCRYPTED_SIGNATURE:
            self.field_4c |= 0x0C
        return signature, version, flags, self.read_class_ref()

    def read_class_ref(self) -> str:
        class_ref, tag = self.read_class()
        if class_ref is None:
            raise InventoryError(f"expected class ref, got tag {tag}")
        return class_ref

    def read_class(self) -> tuple[str | None, int]:
        word_tag = self.reader.u16()
        if word_tag == 0x7FFF:
            object_tag = self.reader.i32()
        else:
            object_tag = ((word_tag & 0x8000) << 16) | (word_tag & ~0x8000)
        if not (object_tag & -0x80000000):
            return None, object_tag
        if word_tag == 0xFFFF:
            if self.field_4c & 8:
                schema = self.reader.u16()
                length = self.reader.u8()
                if length == 0xFF:
                    length = self.reader.u16()
                class_ref = decode_class_name(self.reader.bytes(length))
            else:
                schema = self.reader.u16()
                length = self.reader.u16()
                class_ref = self.reader.bytes(length).decode("ascii", "replace")
            self.object_schema = int(schema)
            self.load_array.append(class_ref)
            return class_ref, object_tag
        object_tag &= 0x7FFFFFFF
        if object_tag == 0 or object_tag >= len(self.load_array):
            return None, object_tag
        value = self.load_array[object_tag]
        if not isinstance(value, str):
            return None, object_tag
        return value, object_tag

    def deserialize_root(self) -> str:
        self.load_array = [None, self]
        signature, _version, _flags, class_ref = self.load_type_core()
        root = Node("", class_ref, is_root=True)
        if signature == RIO_SIGNATURE:
            root.flags |= 0x80
        elif signature == ENCRYPTED_SIGNATURE:
            root.flags |= 0x180
        self.map_object(root)
        self.deserialize_class_list(root)
        if class_ref != "CrelicUnitedGameProject":
            raise InventoryError(f"root class not supported: {class_ref}")
        self.deserialize_relic()
        return class_ref

    def deserialize_class_list(self, root: Node) -> None:
        if self.is_encrypted and root.flags & 0x200:
            return
        self._class_list_depth += 1
        try:
            if self._class_list_depth > MAX_CLASS_LIST_DEPTH:
                raise InventoryError("RIO class-list recursion limit exceeded")
            count = self.reader.count()
            for _ in range(count):
                if not self.is_encrypted:
                    raise NotImplementedError(
                        "unencrypted class lists are outside the supported ICI workflow"
                    )
                node = Node("unrefix")
                self.deserialize_node(node)
                node.parent = root
                self.nodes.append(node)
        finally:
            self._class_list_depth -= 1

    def deserialize_node(self, node: Node, store_to_map: bool = True) -> None:
        flags = self.reader.u16()
        if flags & 7 == 0:
            if flags & 0x8000:
                self.reader.u8()
            else:
                self.reader.u16()
            class_ref = self.read_class_ref()
        elif flags & 7 == 1:
            self.reader.i32()
            class_ref = self.read_ctype()
        else:
            raise InventoryError(f"unsupported node flags {flags:04x}")
        node.class_name = class_ref
        node.schema = self.object_schema
        if store_to_map:
            node.flags = flags
        if flags & 8:
            id1 = self.reader.i32()
            id2 = self.reader.i32()
            if self.is_encrypted and store_to_map:
                node.flags |= 0x100
                self.ocean_map.setdefault(id1, node)
            node.offset = id1 & 0xFFFFFFFF
            node.size = id2 & 0xFFFFFFFF
        self.deserialize_class_list(node)

    def read_ctype(self) -> str:
        code = self.reader.u16()
        if code == 0x1E57:
            return self.read_class_ref()
        if code in {0x2D6B, 0x2F1A}:
            self.reader.u16()
            length = self.reader.u16()
            return self.reader.bytes(length).decode("cp932", "replace")
        raise NotImplementedError(f"ctype {code:04x} not implemented")

    def read_object_from_file(
        self,
        node: Node,
        rio_path: Path,
        *,
        physical_offset: int | None = None,
        extent: int | None = None,
    ) -> None:
        physical = node.offset << self.shift if physical_offset is None else physical_offset
        file_size = rio_path.stat().st_size
        if physical < 0 or physical >= file_size:
            raise InventoryError(
                f"object offset 0x{physical:X} is outside volume {rio_path.name}"
            )
        # A decoded RIO size is already a byte extent.  The allocation shift
        # applies only to offsets; applying it to the extent a second time is
        # a subtle but common source of over-reads.
        object_extent = node.size if extent is None else extent
        if object_extent <= 0:
            raise InventoryError(f"invalid object extent {object_extent}")
        requested = max(object_extent + 0x100, 0x1000)
        if requested > MAX_DECODED_CHUNK_BYTES:
            raise InventoryError(
                f"object read window {requested} exceeds safety limit "
                f"{MAX_DECODED_CHUNK_BYTES}"
            )
        read_size = min(requested, file_size - physical)
        with rio_path.open("rb") as handle:
            handle.seek(physical)
            data = handle.read(read_size)

        saved_reader = self.reader
        saved_load_array = self.load_array
        saved_field_60 = self.field_60
        self.reader = Reader(data)
        self.load_array = [None, self]
        self.field_60 = True
        try:
            first = self.reader.u8() & 3
            second = self.reader.u8()
            self.reader.u8()
            if second >> 6 in {2, 3}:
                self.reader.u8()
            self.object_schema = node.schema
            obj = Node(
                node.name,
                node.class_name,
                node.parent,
                node.flags,
                node.offset,
                node.size,
                node.schema,
            )
            obj.decoded = node.decoded
            self.map_object(obj)
            if first == 2:
                flags = self.reader.u16()
                self.field_4c = (self.field_4c & 0xFFFF) | (flags << 16)
            elif first == 3:
                self.object_schema = self.reader.u16()
                flags = self.reader.u16()
                self.field_4c = (self.field_4c & 0xFFFF) | (flags << 16)

            if node.class_name == "CBoxOcean":
                self.deserialize_box_ocean()
            elif node.class_name == "CStdb":
                self.reader.string()
            elif node.class_name == "CObjectOcean":
                pass
            else:
                raise NotImplementedError(f"object class not supported: {node.class_name}")
            for loaded in self.load_array:
                if isinstance(loaded, Node) and loaded not in self.nodes:
                    self.nodes.append(loaded)
        finally:
            self.reader = saved_reader
            self.load_array = saved_load_array
            self.field_60 = saved_field_60

    def deserialize_box_ocean(self) -> None:
        self.read_rio_reference("CFrameBuffer")
        schema = self.object_schema
        if schema >= 17:
            self.reader.bytes(16)
        if schema < 3:
            for _ in range(32):
                self.read_rio_reference("CBox")
        if schema >= 2:
            self.read_rio_reference("CSbm")
            if schema < 6:
                self.read_rio_reference("CSbm")
            else:
                ref_count = 15
                string_count = 0
                if schema >= 7:
                    ref_count = 32
                    string_count = 32
                for _ in range(ref_count):
                    self.read_rio_reference("CSbm")
                for _ in range(string_count):
                    self.reader.string()
            self.read_rio_reference("CUnitedMenu")
            if schema >= 4:
                self.read_cui_list()
                if schema >= 5:
                    self.read_rio_reference("CUI")
                    self.read_cui_list()

    def read_cui_list(self) -> None:
        while self.reader.u8() != 0:
            self.read_rio_reference("CUI")

    def deserialize_relic(self) -> None:
        data, _end = read_encrypted_from_bytes(self.reader.data, RIO_KEY, self.reader.pos)
        saved = self.reader
        self.reader = Reader(data)
        try:
            version = self.reader.i32()
            if version >= 0x24:
                self.read_rio_reference("CDatabaseBase")
                self.read_rio_reference("CDatabaseBase")
                self.read_rio_reference("CBoxOcean")
                self.read_rio_reference("CObjectOcean")
                self.read_rio_reference("CObjectOcean")
                self.read_rio_reference("CProcessOcean")
                if version >= 0x25:
                    self.read_rio_reference("CStdb")
                if version >= 0x26:
                    self.read_rio_reference("CRio")
                if version >= 0x27:
                    self.read_rio_reference("CRio")
                if version >= 0x29:
                    self.read_rio_reference("CRio")
                self.skip_unknown1()
                if version >= 0x28:
                    self.read_rio_reference("CRio")
            elif version >= 0x20:
                self.read_rio_reference("CProcessOcean")
                self.read_rio_reference("CBoxOcean")
                self.read_rio_reference("CObjectOcean")
                self.read_rio_reference("CObjectOcean")
                self.read_rio_reference("CSoundManEx")
                if version >= 0x23:
                    self.read_rio_reference("CDatabaseBase")
                if version >= 0x22:
                    self.read_rio_reference("CDatabaseBase")
                if version >= 0x21:
                    self.skip_unknown1()
            else:
                raise NotImplementedError(f"rUGP schema {version} not supported")
        finally:
            self.reader = saved

    def skip_unknown1(self) -> None:
        version = self.reader.i32()
        if version >= 0x1C:
            self.reader.string()
        if version >= 0x1D:
            self.reader.string()
            self.reader.string()
        if version >= 0x1E:
            self.reader.i32()
            self.reader.i32()

    def read_rio_reference(self, base_ref: str) -> Node | None:
        if not self.field_60:
            self.field_60 = True
            if self.is_encrypted:
                for _ in range(self.reader.short_count()):
                    self.map_object(None)
        class_ref, tag = self.read_class()
        if class_ref is None:
            if tag < 0 or tag >= len(self.load_array):
                return None
            value = self.load_array[tag]
            return value if isinstance(value, Node) else None

        flags = self.reader.u16()
        if flags & 0x40:
            raise NotImplementedError("anonymous RIO reference not implemented")
        if not self.is_encrypted:
            raise NotImplementedError("unencrypted RIO reference is outside this workflow")
        id1 = self.reader.i32()
        id2 = self.reader.i32()
        self.read_rio_reference("CRio")
        if flags & 7:
            self.reader.i32()
        elif flags & 0x8000:
            self.reader.u8()
        else:
            self.reader.u16()
        node = self.read_encrypted_object(class_ref, id1, id2)
        if node is not None:
            node.name = base_ref
        self.map_object(node)
        return node

    def read_encrypted_object(self, class_ref: str, id1: int, id2: int) -> Node | None:
        del class_ref  # GARbro resolves by encoded object identity, not this label.
        node = self.ocean_map.get(id1)
        if node is None:
            return None
        node.offset = decode_offset(id1)
        node.size = decode_size(id2)
        node.decoded = True
        return node


def decode_offset(offset: int) -> int:
    return ((offset & 0xFFFFFFFF) - 0xA2FB6AD1) & 0xFFFFFFFF


def decode_size(size: int) -> int:
    value = ((size & 0xFFFFFFFF) - 0xE7B5D9F8) & 0xFFFFFFFF
    high = value >> 13
    return (((value - (high & 0xFFF)) << 19) | high) & 0xFFFFFFFF


def parse_ici(path: Path) -> IciInfo:
    """Decode only the ICI directory metadata from ``path``."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    plain = decrypt_ici(read_encrypted_file(path, ICI_KEY))
    reader = Reader(plain)
    signature = reader.u32()
    if signature != ICI_SIGNATURE:
        raise InventoryError(f"unexpected ICI signature: {signature:08x}")
    version = reader.u16()
    if 0x10 <= version <= 0x3FFF and version >= 0x11:
        reader.u16()
    elif not (0x10 <= version <= 0x3FFF):
        reader.seek(reader.pos - 2)
    word_tag = reader.u16()
    if word_tag != 0xFFFF:
        raise InventoryError("unexpected ICI root class tag")
    reader.u16()
    class_length = reader.u16()
    class_name = reader.bytes(class_length).decode("ascii", "replace")
    if class_name != "CObjectArcMan":
        raise InventoryError(f"unexpected ICI root class: {class_name}")
    if reader.count() != 0:
        raise InventoryError("unexpected ICI class list")

    object_version = reader.i32()
    reader.i32()
    reader.u8()
    reader.u8()
    if object_version >= 10:
        reader.i32()
        reader.i32()
    reader.i32()
    reader.i32()
    reader.i32()
    toc_offset = toc_size = 0
    if object_version >= 6:
        toc_offset = reader.i32()
        toc_size = reader.i32()
        reader.i32()
    if object_version >= 8:
        reader.i32()
    reader.string()
    reader.i32()
    reader.string()
    reader.i32()
    reader.string()
    reader.string()
    reader.string()
    reader.i32()
    reader.string()
    for _ in range(reader.count()):
        reader.string()
    reader.i32()
    rio_file_name = reader.string() if object_version >= 9 else ""
    if object_version >= 7:
        reader.string()
    if object_version >= 5:
        reader.i32()
    arcs: list[ArcInfo] = []
    for _ in range(reader.count()):
        if reader.u8():
            arcs.append(parse_install_source(reader))
    return IciInfo(
        toc_offset=toc_offset,
        toc_size=toc_size,
        rio_file_name=rio_file_name,
        arcs=arcs,
    )


def parse_install_source(reader: Reader) -> ArcInfo:
    version = reader.u16()
    if version >= 7:
        reader.i32()
        reader.i32()
        reader.u8()
        reader.string()
    reader.string()
    reader.string()
    reader.string()
    reader.string()
    reader.string()
    reader.i64()
    reader.i64()
    if version < 6:
        reader.i32()
        reader.i32()
    else:
        reader.i32()
    rio_name = reader.string()
    rio_offset = reader.i64()
    rio_size = reader.i64()
    if rio_offset < 0 or rio_size < 0:
        raise InventoryError("ICI declares a negative RIO volume offset or size")
    if version < 6:
        reader.i64()
    reader.i32()
    reader.string()
    for _ in range(5):
        reader.i32()
    reader.string()
    count = reader.count()
    reader.bytes(count * 4)
    block_count = (rio_size + 0xFFFF) >> 16
    bitmap_length = (block_count + 7) >> 3
    reader.bytes(bitmap_length)
    return ArcInfo(rio_name=rio_name, rio_offset=rio_offset, rio_size=rio_size)


def _normal_name(value: str) -> str:
    return value.replace("\\", "/").rsplit("/", 1)[-1].casefold()


def _bind_volume_paths(
    ici_info: IciInfo,
    main_rio: Path,
    volumes: Sequence[Path] | Mapping[str, Path],
) -> dict[str, Path]:
    """Bind declared ICI volume names to caller-supplied paths without scanning."""

    bindings: dict[str, Path] = {}
    if ici_info.arcs:
        bindings[ici_info.arcs[0].rio_name] = main_rio

    if isinstance(volumes, Mapping):
        declared_by_normal = {_normal_name(arc.rio_name): arc.rio_name for arc in ici_info.arcs}
        for name, path in volumes.items():
            declared = declared_by_normal.get(_normal_name(name), name)
            bindings[declared] = Path(path)
    else:
        declared_by_normal = {_normal_name(arc.rio_name): arc.rio_name for arc in ici_info.arcs}
        for path_value in volumes:
            path = Path(path_value)
            declared = declared_by_normal.get(_normal_name(path.name))
            if declared is None:
                raise InventoryError(
                    f"volume {path.name!r} does not match a filename declared by the ICI; "
                    "use an explicit name=path binding"
                )
            bindings[declared] = path
    return bindings


def _locate_volume(
    ici_info: IciInfo,
    shift: int,
    global_offset: int,
    extent: int,
    volume_sizes: Mapping[str, int],
) -> dict[str, Any]:
    for arc in ici_info.arcs:
        start = arc.rio_offset << shift
        end = start + arc.rio_size
        if start <= global_offset < end:
            local_offset = global_offset - start
            actual_size = volume_sizes.get(arc.rio_name)
            return {
                "volume": arc.rio_name,
                "volume_offset": local_offset,
                "volume_present": actual_size is not None,
                "within_declared_volume": local_offset + extent <= arc.rio_size,
                "within_provided_volume": (
                    local_offset + extent <= actual_size if actual_size is not None else None
                ),
            }
    return {
        "volume": None,
        "volume_offset": None,
        "volume_present": False,
        "within_declared_volume": False,
        "within_provided_volume": None,
    }


def _node_offsets(node: Node, shift: int) -> tuple[int, int]:
    offset_units = node.offset
    extent = node.size
    if node.flags & 0x100 and not node.decoded:
        offset_units = decode_offset(node.offset)
        extent = decode_size(node.size)
    return offset_units << shift, extent


def _find_toc(main_rio: Path, ici_info: IciInfo) -> tuple[bytes, int, int]:
    file_size = main_rio.stat().st_size
    with main_rio.open("rb") as handle:
        toc_physical = scale = None
        for candidate_scale in (1, 2, 4, 8):
            candidate = ici_info.toc_offset * candidate_scale
            if candidate < 0 or candidate + 4 > file_size:
                continue
            handle.seek(candidate)
            if int.from_bytes(_read_exact(handle, 4), "little") == ENCRYPTED_SIGNATURE:
                toc_physical = candidate
                scale = candidate_scale
                break
        if toc_physical is None or scale is None:
            raise InventoryError("could not locate the encrypted RIO TOC signature")
        if ici_info.toc_size <= 0:
            raise InventoryError(f"invalid ICI TOC size {ici_info.toc_size}")
        requested = max(
            ici_info.toc_size * scale,
            ici_info.toc_size + 0x10000,
        )
        if requested > MAX_DECODED_CHUNK_BYTES:
            raise InventoryError(
                f"RIO TOC read window {requested} exceeds safety limit "
                f"{MAX_DECODED_CHUNK_BYTES}"
            )
        read_size = min(file_size - toc_physical, requested)
        handle.seek(toc_physical)
        data = handle.read(read_size)
    return data, toc_physical, scale


def _expand_box_if_needed(
    archive: RioArchive,
    ici_info: IciInfo,
    bindings: Mapping[str, Path],
    volume_sizes: Mapping[str, int],
) -> str | None:
    referenced = [obj for obj in archive.load_array if isinstance(obj, Node)]
    if any((node.class_name or "") in SUPPORTED_CLASSES for node in referenced):
        return None
    box = next((node for node in referenced if node.class_name == "CBoxOcean"), None)
    if box is None:
        return None
    global_offset, extent = _node_offsets(box, archive.shift)
    location = _locate_volume(ici_info, archive.shift, global_offset, extent, volume_sizes)
    volume_name = location["volume"]
    path = bindings.get(volume_name) if volume_name else None
    if path is None or not path.is_file():
        return (
            f"CBoxOcean is in unavailable volume {volume_name!r}; nested UI entries "
            "were not expanded"
        )
    archive.read_object_from_file(
        box,
        path,
        physical_offset=int(location["volume_offset"]),
        extent=extent,
    )
    return None


def build_inventory(
    *,
    ici: Path,
    main_rio: Path,
    volumes: Sequence[Path] | Mapping[str, Path] = (),
) -> dict[str, Any]:
    """Build a portable inventory without writing to any archive.

    ``main_rio`` is the volume containing the encrypted TOC.  Additional
    volumes may be supplied as paths (matched by filename) or as an explicit
    ``{declared_name: path}`` mapping.  Absolute source paths are deliberately
    omitted from the returned report.
    """

    ici = Path(ici)
    main_rio = Path(main_rio)
    if not ici.is_file():
        raise FileNotFoundError(ici)
    if not main_rio.is_file():
        raise FileNotFoundError(main_rio)

    ici_info = parse_ici(ici)
    bindings = _bind_volume_paths(ici_info, main_rio, volumes)
    for name, path in bindings.items():
        if not path.is_file():
            raise FileNotFoundError(f"RIO volume {name!r}: {path}")
    volume_sizes = {name: path.stat().st_size for name, path in bindings.items()}

    data, toc_physical, scale = _find_toc(main_rio, ici_info)
    shift = int(math.log2(scale))
    archive = RioArchive(data, shift=shift, encrypted=True)
    root_class = archive.deserialize_root()
    warnings: list[str] = []
    warning = _expand_box_if_needed(archive, ici_info, bindings, volume_sizes)
    if warning:
        warnings.append(warning)

    seen: set[int] = set()
    decoded_nodes: list[Node] = []
    for obj in archive.load_array + archive.nodes:
        if not isinstance(obj, Node):
            continue
        identity = id(obj)
        if identity in seen:
            continue
        seen.add(identity)
        decoded_nodes.append(obj)

    rows: list[dict[str, Any]] = []
    for node in decoded_nodes:
        global_offset, extent = _node_offsets(node, archive.shift)
        logical_path = node.path()
        directory = str(PurePosixPath(logical_path).parent)
        if directory == ".":
            directory = ""
        location = _locate_volume(
            ici_info,
            archive.shift,
            global_offset,
            extent,
            volume_sizes,
        )
        rows.append(
            {
                "logical_path": logical_path,
                "logical_directory": directory,
                "name": node.name,
                "class": node.class_name,
                "kind": SUPPORTED_CLASSES.get(node.class_name or "", "other"),
                **location,
                "global_offset": global_offset,
                "extent": extent,
                "flags": node.flags,
                "schema": node.schema,
            }
        )

    rows.sort(key=lambda row: (int(row["global_offset"]), str(row["logical_path"])))
    declared_volumes = []
    for arc in ici_info.arcs:
        actual_size = volume_sizes.get(arc.rio_name)
        declared_volumes.append(
            {
                "name": arc.rio_name,
                "global_offset": arc.rio_offset << archive.shift,
                "offset_units": arc.rio_offset,
                "declared_size": arc.rio_size,
                "provided": actual_size is not None,
                "actual_size": actual_size,
            }
        )

    if ici_info.arcs and _normal_name(ici_info.arcs[0].rio_name) != _normal_name(main_rio.name):
        warnings.append(
            "main RIO filename differs from the first ICI volume name; it was bound "
            "by its explicit --main-rio role"
        )

    return {
        "schema": "muvluv-rugp-rio-inventory/v1",
        "mode": "read_only",
        "source": {
            "ici_name": ici.name,
            "main_rio_name": main_rio.name,
        },
        "toc": {
            "offset_units": ici_info.toc_offset,
            "extent_raw": ici_info.toc_size,
            "physical_offset": toc_physical,
            "allocation_unit_bytes": scale,
            "shift": archive.shift,
        },
        "root_class": root_class,
        "volumes": declared_volumes,
        "nodes": rows,
        "warnings": warnings,
    }


def load_inventory(
    main_rio: Path,
    ici: Path,
    volumes: Sequence[Path] | Mapping[str, Path] = (),
) -> dict[str, Any]:
    """Compatibility wrapper with the historical helper's argument order."""

    return build_inventory(ici=ici, main_rio=main_rio, volumes=volumes)


def filter_nodes(
    rows: Iterable[Mapping[str, Any]],
    *,
    kind: str = "all",
    class_name: str | None = None,
    near_global_offset: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    selected = [dict(row) for row in rows]
    if kind != "all":
        selected = [row for row in selected if row["kind"] == kind]
    if class_name:
        selected = [row for row in selected if row["class"] == class_name]
    if near_global_offset is not None:
        selected.sort(
            key=lambda row: (
                abs(int(row["global_offset"]) - near_global_offset),
                int(row["global_offset"]),
                str(row["logical_path"]),
            )
        )
    else:
        selected.sort(key=lambda row: (int(row["global_offset"]), str(row["logical_path"])))
    if limit is not None:
        selected = selected[:limit]
    return selected


def render_json(inventory: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    document = dict(inventory)
    document["nodes"] = list(rows)
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_csv(rows: Sequence[Mapping[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name) for name in CSV_COLUMNS})
    return stream.getvalue()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise InventoryError(f"refusing to overwrite existing output: {path}") from error
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _parse_volume_arguments(values: Sequence[str]) -> tuple[list[Path], dict[str, Path]]:
    unnamed: list[Path] = []
    named: dict[str, Path] = {}
    for value in values:
        if "=" in value:
            name, raw_path = value.split("=", 1)
            if not name or not raw_path:
                raise InventoryError(f"invalid --volume binding: {value!r}")
            named[name] = Path(raw_path)
        else:
            unnamed.append(Path(value))
    if unnamed and named:
        raise InventoryError("do not mix PATH and DECLARED_NAME=PATH --volume forms")
    return unnamed, named


def _integer(value: str) -> int:
    try:
        result = int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"not an integer or 0x-prefixed integer: {value}") from error
    if result < 0:
        raise argparse.ArgumentTypeError("offset must be non-negative")
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ici", type=Path, required=True, help="path to the matching .ici directory")
    parser.add_argument(
        "--main-rio",
        type=Path,
        required=True,
        help="RIO volume that contains the encrypted object-directory TOC",
    )
    parser.add_argument(
        "--volume",
        action="append",
        default=[],
        metavar="[DECLARED_NAME=]PATH",
        help="additional RIO volume; repeat for split archives",
    )
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", type=Path, help="separate report path; stdout when omitted")
    parser.add_argument(
        "--kind",
        choices=("all", "image", "script", "audio", "other"),
        default="all",
    )
    parser.add_argument("--class-name", help="exact rUGP class filter, for example CRsa")
    parser.add_argument(
        "--near-global-offset",
        type=_integer,
        help="sort by distance to a byte offset; accepts decimal or 0x-prefixed hex",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="maximum exported rows after filtering; omitted means all rows",
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be non-negative")
    return args


def run_cli(args: argparse.Namespace, *, stdout: TextIO = sys.stdout) -> dict[str, Any]:
    unnamed, named = _parse_volume_arguments(args.volume)
    volume_bindings: Sequence[Path] | Mapping[str, Path] = named if named else unnamed
    inventory = build_inventory(
        ici=args.ici,
        main_rio=args.main_rio,
        volumes=volume_bindings,
    )
    rows = filter_nodes(
        inventory["nodes"],
        kind=args.kind,
        class_name=args.class_name,
        near_global_offset=args.near_global_offset,
        limit=args.limit,
    )
    output_text = render_json(inventory, rows) if args.format == "json" else render_csv(rows)
    if args.output:
        output = args.output.resolve()
        inputs = {args.ici.resolve(), args.main_rio.resolve()}
        inputs.update(path.resolve() for path in unnamed)
        inputs.update(path.resolve() for path in named.values())
        if output in inputs:
            raise InventoryError("--output must not name an ICI or RIO input file")
        _atomic_write_text(output, output_text)
    else:
        stdout.write(output_text)
    return {
        "status": "PASS",
        "mode": "read_only",
        "rows": len(rows),
        "format": args.format,
        "output": args.output.name if args.output else "stdout",
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        run_cli(args)
    except (EOFError, FileNotFoundError, InventoryError, NotImplementedError) as error:
        print(f"rio_inventory: error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
