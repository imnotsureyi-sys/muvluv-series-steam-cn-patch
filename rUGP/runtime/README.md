# Photon PF/PM runtime

This is a fail-closed 32-bit Windows proxy/runtime for the exact reviewed Steam builds. It forwards the original `Ages3ResT` plugin surface to a hash-locked private DLL, installs a local PhotonR2 font route, rewrites the host's single `CreateFontIndirectW` import, and optionally starts the exact-image runtime.

`DllMain` performs no file, registry, font, hook, thread, or loader work. Initialization begins on the first official plugin export call. The runtime verifies the host executable, private DLL, font, generated tables, and game-specific configuration; optional image initialization is shut down on a contract failure.

## Build

Install Zig 0.16.0, then build PF and PM separately:

```powershell
python rUGP/runtime/build.py --game pf --zig "X:\zig\zig.exe" `
  --output "X:\build\pf\Ages3ResT.dll" `
  --authorize-pinned-build --verify-release-code

python rUGP/runtime/build.py --game pm --zig "X:\zig\zig.exe" `
  --output "X:\build\pm\Ages3ResT.dll" `
  --authorize-pinned-build --verify-release-code
```

Without `--authorize-pinned-build`, the binary is intentionally unable to install production routes. Authorization only enables checked-in identities; it does not make an arbitrary game version compatible.

For the reviewed PM U+73E5 font candidate only, add `--pm-font-candidate`
alongside `--authorize-pinned-build` and, for the Latin-name review,
`--speaker-color-candidate`. This pins the isolated build to font hash
`3D1CDF9B8C3CA71D09ECBF5A380FA7F6E9D2F2EE4BB020805711B42FA4322F3B`.
It is PM-only, cannot be combined with `--verify-release-code`, and does not
modify sealed headers or default release identities. See the
[font repair contract](../../localization/fonts/pm-er-20260909.md).

The builder compiles twice and normalizes only non-runtime PE/PDB provenance:
the PE file-header timestamp, every debug-directory timestamp, and the single
CodeView `RSDS` GUID. The CodeView signature, PDB age/path, executable code, and
runtime data are preserved. Normalization is idempotent and the release does not
ship a matching PDB.

The reviewed historical-to-normalized Beta0.1 identities are:

- PF historical raw: `E886F746F937B53C712AB931BFB36889FEC5ADE7B426893EFE1E1EF44415C8DD`
  -> normalized: `01399562654A81C0458E269B143A9AB39B5F6892DE5B295DD0854B8A116AB1FA`
- PM historical raw: `84C20D878CD440950D55585A5B6D9575138CD043F157DC46D7A19F548AAE2C40`
  -> normalized: `73F5EC68A374042096CB4C900210F22537E5706E49B7EA9A8F249C583039E2CD`

Applying the normalization to either historical raw DLL produces its listed
historical normalized identity. The currently approved reproducible outputs are
PF `9CCD76162F20316AF3E6BFA4FE6CC2F3590596D7A7D6AB78B0E8F2CC22909B8E`
and PM `F4AF72BA6DFC87D8B3478F63135A44A281C8DCA464070B9C69ED4402620DE666`.
PM includes the tutorial-timer and selector repair plus the CRip008 direct
image hooks, matching nine-hook production admission, and the exact-host RUO
base repair. Both games include the installed image-table snapshots. The
packaging assembler accepts only its named hash-locked identities and records
which one it copied. This does not turn the runtime builder into a complete
source-to-player-release pipeline; packaging still requires the other sealed
and approved authorities described in `../packaging/README.md`.

The Beta0.1 assembler's allowlist is unchanged: it rejects both new default
identities until a separate release review approves them. The 2026-09-09 local
installations use the existing `--speaker-color-candidate` profile. Building
with `--authorize-pinned-build --speaker-color-candidate` (without
`--verify-release-code`) reproduces both installed DLLs byte for byte:
PF `B3C43B2000BE0C286B140D900C081B3AECC771BEF7F7F69A79DE624ACC3875B0`,
PM `2259884FF2CC52C3A94D917BCC5508D5951340FF8461612D89C270CE3FFC525E`.
This preserves the profile's candidate status, not an automatic player release.
Portable build manifests and readback evidence are linked from
[current review status](../evidence/photon/images/static-review-20260909/README.md)
and the [PM admission regression](../docs/postmortems/pm-image-admission-20260909.md).

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
