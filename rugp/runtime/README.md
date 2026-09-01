# Photon PF/PM runtime

This is a fail-closed 32-bit Windows proxy/runtime for the exact reviewed Steam builds. It forwards the original `Ages3ResT` plugin surface to a hash-locked private DLL, installs a local PhotonR2 font route, rewrites the host's single `CreateFontIndirectW` import, and optionally starts the exact-image runtime.

`DllMain` performs no file, registry, font, hook, thread, or loader work. Initialization begins on the first official plugin export call. The runtime verifies the host executable, private DLL, font, generated tables, and game-specific configuration; optional image initialization is shut down on a contract failure.

## Build

Install Zig 0.16.0, then build PF and PM separately:

```powershell
python rugp/runtime/build.py --game pf --zig "X:\zig\zig.exe" `
  --output "X:\build\pf\Ages3ResT.dll" `
  --authorize-pinned-build --verify-release-code

python rugp/runtime/build.py --game pm --zig "X:\zig\zig.exe" `
  --output "X:\build\pm\Ages3ResT.dll" `
  --authorize-pinned-build --verify-release-code
```

Without `--authorize-pinned-build`, the binary is intentionally unable to install production routes. Authorization only enables checked-in identities; it does not make an arbitrary game version compatible.

The builder compiles twice and normalizes only non-runtime PE/PDB provenance:
the PE file-header timestamp, every debug-directory timestamp, and the single
CodeView `RSDS` GUID. The CodeView signature, PDB age/path, executable code, and
runtime data are preserved. Normalization is idempotent and the release does not
ship a matching PDB.

The reviewed historical-to-normalized identities are:

- PF historical raw: `E886F746F937B53C712AB931BFB36889FEC5ADE7B426893EFE1E1EF44415C8DD`
  -> normalized: `01399562654A81C0458E269B143A9AB39B5F6892DE5B295DD0854B8A116AB1FA`
- PM historical raw: `84C20D878CD440950D55585A5B6D9575138CD043F157DC46D7A19F548AAE2C40`
  -> normalized: `73F5EC68A374042096CB4C900210F22537E5706E49B7EA9A8F249C583039E2CD`

For both reviewed games, applying this normalization to the historical raw DLL
produces bytes identical to the clean-clone normalized build. The packaging
assembler therefore accepts exactly either named identity for `Ages3ResT.dll`
and records which one it copied. This does not turn the runtime builder into a
complete source-to-player-release pipeline; packaging still requires the other
sealed and approved authorities described in `../packaging/README.md`.

Generated headers are [sealed reviewed configuration](generated/README.md),
not publicly regenerable source. Updating their identities requires repeating
the executable/runtime audit, not merely editing a hash until the build passes.

Each build also writes a `*.build.json` manifest (or the path supplied with
`--manifest`). Schema `photon-runtime-build-v2` records the Zig version and
executable hash, target, flags, defines, link libraries, a portable command
description, all command-line `.c`/`.S` inputs, the PM source-level `.c`
dependency, the module `.def`, the complete local header root, and every
authorization-adjusted generated header. Manifest paths are repository-relative
or explicit placeholders; temporary directories and the caller's Zig path are
never embedded. Generated-header hashes therefore describe the exact staged
bytes seen by the compiler, after `--authorize-pinned-build` is applied.
The manifest marks this repository-controlled input closure with
`sources_complete: true`; it does not claim to snapshot Zig's own internal
toolchain files. DLL and manifest paths must be different, and the builder
refuses to overwrite either existing artifact. Each file is fsynced under a
same-directory temporary name and atomically published only after its bytes are
complete; the DLL is then read back and compared with the twice-compiled,
normalized candidate before its manifest can be written. Use a new staging
directory for every build and promote only the reviewed hashes.
