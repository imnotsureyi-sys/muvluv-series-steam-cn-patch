import pathlib
import struct
import sys
import zlib

from probe_fpd import load_base_keys, make_keys, parse_pack, xor_bytes


def safe_path(base: pathlib.Path, name: str) -> pathlib.Path:
    name = name.lstrip("/\\").replace("\\", "/")
    parts = [p for p in name.split("/") if p and p not in (".", "..")]
    return base.joinpath(*parts)


def main() -> int:
    if len(sys.argv) < 5:
        print("usage: python tools/fpd/extract_fpd_filtered.py <Scrambler.cs> <pack.bin> <out-dir> <filter>")
        return 2

    scrambler = pathlib.Path(sys.argv[1])
    pack = pathlib.Path(sys.argv[2])
    out_dir = pathlib.Path(sys.argv[3])
    needle = sys.argv[4].lower()

    keys = make_keys(load_base_keys(scrambler))
    _, data_start, entries = parse_pack(pack, keys)
    selected = [e for e in entries if needle in e[0].lower()]

    with pack.open("rb") as f:
        for name, data_off, data_len, full_len in selected:
            f.seek(data_start + data_off)
            data = xor_bytes(f.read(data_len), keys)
            if full_len:
                data = zlib.decompress(data)
            dest = safe_path(out_dir, name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            print(dest)

    print(f"extracted={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
