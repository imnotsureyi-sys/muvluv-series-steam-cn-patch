"""Reproduce the PM 7/9 admission failure using a synthetic host and artwork.

This exercises real production admission, selector initialization, native hook
installation, PNG authentication and surface transactions. It does not execute
the proprietary image decoder or launch a game.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "rUGP/runtime"


def fnv1a64(data: bytes) -> int:
    result = 14695981039346656037
    for byte in data:
        result = ((result ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return result


def run(zig: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    headers = output / "generated"
    shutil.copytree(RUNTIME / "generated", headers)
    payload = bytes(range(64))  # An identity token, not a compressed game image.
    identity = fnv1a64(payload)
    (output / "synthetic.record").write_bytes(bytes(41) + payload)
    width, height = 8, 6
    pixels = bytes(channel for y in range(height) for x in range(width)
                   for channel in (x * 29, y * 41, (x + y) * 17, 255))
    sidecar = output / "sidecars/PM" / f"{len(payload):010}_{identity:016X}.png"
    sidecar.parent.mkdir(parents=True)
    Image.frombytes("RGBA", (width, height), pixels).save(sidecar)
    def digest_bytes(data: bytes) -> str:
        return ",".join(f"0x{x:02X}" for x in hashlib.sha256(data).digest())
    header = (headers / "photon_v6_pm_exact_rgba_table.generated.h").read_text("utf-8")
    start = header.index("static const PhotonV6ExactRgbaEntry photon_v6_pm_exact_rgba[]")
    suffix = header.index("static const uint32_t", start)
    header = header[:start] + (
        "static const PhotonV6ExactRgbaEntry photon_v6_pm_exact_rgba[] = {\n"
        f"{{{len(payload)}U, UINT64_C(0x{identity:016X}), {width}U, {height}U,"
        "{" + digest_bytes(sidecar.read_bytes()) + "},{" + digest_bytes(pixels) + "}}\n};\n"
    ) + re.sub(r"UINT32_C\(\d+\)", "UINT32_C(1)", header[suffix:], count=1)
    (headers / "photon_v6_pm_exact_rgba_table.generated.h").write_text(header, "utf-8")
    production = (RUNTIME / "src/photon_v6_runtime_production.c").read_text("utf-8")
    current = "#define PHOTON_PRODUCTION_SELECTOR_HOOK_COUNT UINT32_C(1)\n#define PHOTON_PRODUCTION_NATIVE_HOOK_COUNT UINT32_C(9)"
    if current not in production:
        raise ValueError("PM production contract changed; review this regression fixture")
    previous = output / "previous_production.c"
    previous.write_text(production.replace(current, current.replace("UINT32_C(9)", "UINT32_C(7)")), "utf-8")
    sources = [
        "photon_v6_pm_native_runtime.c", "photon_v6_pm_native_runtime.S",
        "photon_v6_cpu_surface_rgba.c", "photon_v6_exact_rgba_sidecar_loader.c",
        "photon_pf_decoder_surface_view.c", "photon_v6_surface_transaction.c",
        "photon_v6_internal_route_gate.c", "photon_v6_exact_overlay_core.c",
        "photon_v6_special57_sidecar_loader.c", "photon_v6_pm_selector_adapter.c",
    ]
    common = [str(zig), "cc", "-target", "x86-windows-gnu", "-std=c11", "-O2",
              "-Wall", "-Wextra", "-Werror", "-municode", "-I", str(headers),
              "-I", str(RUNTIME / "include"), "-DPHOTON_BUILD_PM=1",
              "-DPHOTON_V6_NATIVE_TEST_HOOKS=1", "-DPHOTON_V6_PRODUCTION_PM=1",
              "-DPHOTON_V6_PM_SELECTOR_ADAPTER=1", "-DPHOTON_V6_PM_SELECTOR_TEST_HOOKS=1",
              "-DPHOTON_V6_PRODUCTION_AUTHORIZED=1",
              str(ROOT / "rUGP/tests/runtime/pm_image_production.c"),
              *[str(RUNTIME / "src" / name) for name in sources]]
    results = {}
    for name, source in [("previous", previous), ("fixed", RUNTIME / "src/photon_v6_runtime_production.c")]:
        exe = output / f"{name}.exe"
        built = subprocess.run(common + [str(source), "-o", str(exe), "-ladvapi32", "-luser32",
                                        "-lgdi32", "-lwindowscodecs", "-lole32"],
                               capture_output=True, text=True, encoding="utf-8", timeout=180)
        (output / f"{name}-build.log").write_text(built.stdout + built.stderr, "utf-8")
        if built.returncode:
            raise RuntimeError(f"{name} fixture compilation failed: {built.stderr[-2000:]}")
        result = subprocess.run([str(exe), str(output), str(output / "synthetic.record"),
                                 "0", str(len(payload)), str(width), str(height)],
                                capture_output=True, text=True, encoding="utf-8", timeout=30)
        results[name] = dict(exit_code=result.returncode, stdout=result.stdout.strip(), stderr=result.stderr.strip())
    if results["previous"]["exit_code"] != 70 or "native=9 expected=9 selector=1 gate_disabled=1" not in results["previous"]["stderr"]:
        raise RuntimeError("The previous production rejection was not reproduced")
    if results["fixed"]["exit_code"] or not json.loads(results["fixed"]["stdout"])["passed"]:
        raise RuntimeError("Current production/sidecar transaction check failed")
    ruo_exe = output / "ruo-base.exe"
    compiled = subprocess.run([str(zig), "cc", "-target", "x86-windows-gnu",
                               "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                               "-I", str(RUNTIME / "include"),
                               str(ROOT / "rUGP/tests/runtime/pm_ruo_base.c"), "-o", str(ruo_exe)],
                              capture_output=True, text=True, encoding="utf-8", timeout=180)
    if compiled.returncode:
        raise RuntimeError(f"RUO fixture compilation failed: {compiled.stderr[-2000:]}")
    checked = subprocess.run([str(ruo_exe)], capture_output=True, text=True,
                             encoding="utf-8", timeout=30)
    if checked.returncode:
        raise RuntimeError(f"RUO fixture failed: {checked.stderr}")
    report = dict(schema="photon-pm-production-regression-v1", results=results,
                  synthetic_art=True, proprietary_decoder_executed=False,
                  production_ready=True, game_started=False, native_status_mocked=False,
                  selector_bypassed=False)
    report["ruo_base"] = json.loads(checked.stdout)
    lifecycle_exe = output / "selector-lifecycle.exe"
    lifecycle_build = subprocess.run([
        str(zig), "cc", "-target", "x86-windows-gnu", "-std=c11", "-O2",
        "-Wall", "-Wextra", "-Werror", "-DPHOTON_V6_PRODUCTION_PM=1",
        "-DPHOTON_V6_PM_SELECTOR_ADAPTER=1", "-DPHOTON_V6_PM_SELECTOR_TEST_HOOKS=1",
        "-I", str(RUNTIME / "include"), "-I", str(RUNTIME / "generated"),
        str(ROOT / "rUGP/tests/runtime/pm_selector_lifecycle.c"),
        "-o", str(lifecycle_exe), "-ladvapi32", "-luser32"],
        capture_output=True, text=True, encoding="utf-8", timeout=180)
    if lifecycle_build.returncode:
        raise RuntimeError(f"Selector lifecycle build failed: {lifecycle_build.stderr[-2000:]}")
    lifecycle = subprocess.run([str(lifecycle_exe)], capture_output=True,
                               text=True, encoding="utf-8", timeout=30)
    if lifecycle.returncode:
        raise RuntimeError(f"Selector lifecycle failed: {lifecycle.stderr}")
    report["selector_lifecycle"] = json.loads(lifecycle.stdout)
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zig", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New local directory; never a game directory")
    args = parser.parse_args()
    print(json.dumps(run(args.zig.resolve(), args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
