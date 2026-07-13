import pathlib
import struct
import sys
import zlib

from probe_fpd import ENTRY_SIZE, HEADER_SIZE, load_base_keys, make_keys, xor_bytes


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python tools/fpd/diagnose_fpd_keys.py <Scrambler.cs> <pack.bin>")
        return 2

    scrambler = pathlib.Path(sys.argv[1])
    pack = pathlib.Path(sys.argv[2])
    base = load_base_keys(scrambler)

    with pack.open("rb") as f:
        h = f.read(HEADER_SIZE)
        count = struct.unpack(">Q", h[8:16])[0]
        data_start = struct.unpack(">Q", h[16:24])[0]
        f.seek(HEADER_SIZE)
        enc = f.read(data_start - HEADER_SIZE)

    names_start = ENTRY_SIZE * count
    print(f"count={count} data_start=0x{data_start:X} index_len=0x{len(enc):X} names_start=0x{names_start:X}")

    for mode in ["zlib", "internal", "plain"]:
        keys = make_keys(base, mode)
        for off in [0, -HEADER_SIZE, HEADER_SIZE, 1, 8, 16, 32, 56]:
            dec = xor_bytes(enc[: names_start + 32], keys, off)
            row = dec[:ENTRY_SIZE]
            vals = struct.unpack(">QQQQ", row)
            zhead = dec[names_start : names_start + 8]
            ok = False
            err = ""
            try:
                zlib.decompress(xor_bytes(enc[names_start:], keys, off + names_start))
                ok = True
            except Exception as e:
                err = str(e).splitlines()[0]
            print(f"mode={mode:8} off={off:4} row={vals} zhead={zhead.hex(' ')} zlib={ok} {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
