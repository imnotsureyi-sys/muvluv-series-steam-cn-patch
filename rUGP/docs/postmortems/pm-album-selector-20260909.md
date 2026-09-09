# PM Extra → Album terminates on a remembered CInt address

Two local user-triggered crashes on 2026-09-09 reported exception `0xC0000602`
at `Ages3ResT.dll+0xCEB0`. The installed DLL was
`2259884FF2CC52C3A94D917BCC5508D5951340FF8461612D89C270CE3FFC525E`,
reproducible from commit `6c0b790`. Disassembly identifies the return from
`RaiseFailFastException` in the PM selector's `relevant_setter_failure`, with
termination code `0xE0005841`.

The newer dump preserves a remembered CInt address and owner matching the current
call, previous value 1, requested value 0, and a metadata type of `0x16000001`.
The selector authenticates type `0x16000000`. The transition had drained and
entered the failure branch with `known_anomaly` set; the original store was
already called. The captured stack also contains the four known Options-action
parent RVAs. These observations do not establish whether the object was reused
or its metadata changed in place. A remembered address alone is insufficient to
continue treating this call as an authenticated image-language change.

The fix keeps the existing lease drain, then revokes the remembered object/owner,
purges surface bindings, advances the language generation, and sets language to
UNKNOWN before forwarding an unrecognized relevant setter call. This call does
not authorize any localized write. An exact later language action or existing
Translation-only payload witness must establish language again. A failed drain,
an owned lease, or an authenticated setter that fails to store its value retains
the failure behavior.

[`pm_selector_lifecycle.c`](../../tests/runtime/pm_selector_lifecycle.c) replays
the observed field shape using synthetic objects and a supplied stack fingerprint.
The old implementation fails at the drift call; the new implementation passes
that call, UNKNOWN/Japanese write rejection, exact rebinding and language changes,
failed-store rejection, and owned-lease rejection. The fixture is included in
[`verify_pm_production`](../../tools/images/verify_pm_production.py). It runs the
actual selector dispatcher but does not execute a real game action or prove that
all album images are translated. After installing the repaired DLL, the user
confirmed that the album-entry crash was fixed. Crash dumps remain local.

Separately, the user's PF festival screenshot shows a translated thumbnail and
Japanese signs during the animated presentation. The thumbnail G2498 is Cr6Ti
210×123; background G2018 is CRip008 800×600, and a partial G2019 variant also
exists. All three have installed sidecars. A separate
[PF padding/partial-frame fix](pf-festival-presentation-20260909.md) was installed
and confirmed by the user. File presence and gallery thumbnails alone did not
prove presentation coverage.
