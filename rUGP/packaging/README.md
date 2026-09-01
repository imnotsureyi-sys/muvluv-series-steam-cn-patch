# Photon packaging

`build_photon_cn_beta01.py` produces separate PF and PM full-patch ZIPs from explicitly supplied, hash-locked roots. It never discovers an installed game through a developer-specific path.

Required inputs are a sealed clean archive root, sealed runtime inputs, stock fixed-file root, and independently approved final PF/PM roots. The builder verifies exact archive/fixed-file identities, creates block deltas, binds every member in a manifest, rejects absolute paths, fixes ZIP timestamps, and refuses unexpected content.

One fixed file has a deliberately narrow two-identity policy. For
`Ages3ResT.dll` only, the approved final root may contain either the historical
Beta0.1 raw DLL or the clean-clone DLL produced by `../runtime/build.py` after
its PE/PDB provenance normalization:

- PF: historical `E886F746F937B53C712AB931BFB36889FEC5ADE7B426893EFE1E1EF44415C8DD`
  or normalized `01399562654A81C0458E269B143A9AB39B5F6892DE5B295DD0854B8A116AB1FA`
- PM: historical `84C20D878CD440950D55585A5B6D9575138CD043F157DC46D7A19F548AAE2C40`
  or normalized `73F5EC68A374042096CB4C900210F22537E5706E49B7EA9A8F249C583039E2CD`

The package manifest records `historical_raw_beta01` or
`clean_clone_normalized`, together with the actual byte count and SHA-256.
Unknown DLLs still fail closed. Every other archive, executable, DLL, font,
sidecar, and fixed file retains its existing single exact identity check.

```powershell
python rUGP/packaging/build_photon_cn_beta01.py `
  --clean-root "X:\authority\clean" `
  --sealed-runtime-root "X:\authority\runtime" `
  --stock-fixed-root "X:\authority\stock" `
  --final-pf-root "X:\approved\pf" `
  --final-pm-root "X:\approved\pm" `
  --source-date-epoch 1788220800 `
  --output "X:\release"
```

The checked-in PowerShell installer is a template consumed by the builder. This
script is a deterministic assembler for already prepared authorities, not a
complete text/image/font/runtime authoring or source-to-release workflow. A
package is not authorized for players merely because the script completed: both
generated archives require a second clean-root rebuild, manifest audit,
installation of the downloaded ZIP, and full game QA.

The epoch is mandatory (the environment variable `SOURCE_DATE_EPOCH` is an
equivalent input), and the same value must be reused for the independent
rebuild. Package manifests also record the Python implementation/version,
NumPy, and compile/runtime zlib versions. “Deterministic” here therefore means
the same sealed authorities, epoch, pinned dependencies, and recorded build
environment; it is not an unsupported promise that arbitrary Python/zlib
installations produce byte-identical DEFLATE streams.

## Steam locale preflight for a future installer

[`steam_locale_preflight.py`](steam_locale_preflight.py) is the public,
read-only gate for the two Photon routes this project has actually observed:
Photon Flowers (`pf`) and Photon Melodies (`pm`) must both be on Steam's
`english` route because the patch targets authenticated translation endpoints.
It validates the exact app ID plus both `UserConfig.language` and
`MountedConfig.language`, rejects malformed/duplicate KeyValues, and keeps an
in-memory file identity/hash seal that an installer must revalidate immediately
before its first write.

```powershell
python -m rUGP.packaging.steam_locale_preflight check `
  --game pf `
  --game-root "X:\Library\steamapps\common\Muv-Luv photonflowers" `
  --report ".\pf-locale-preflight.json"
```

The JSON report is path-redacted, atomic and create-only. A passing report is
not transferable write authorization: the same in-memory observation must pass
`revalidate_locale_observation()` at apply time. The tool never edits Steam
configuration. Muv-Luv and Muv-Luv Alternative deliberately fail closed because
their distinct routing policies have not been promoted into this component.

The historical packages were not retrofitted with this gate, and the current
Photon source tree is not a player release. Any future one-click Photon
installer must internalize the same checks without requiring end users to
install Python, then perform transaction/rollback validation separately.
