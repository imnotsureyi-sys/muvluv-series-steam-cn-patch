# Photon speaker colours: Chinese name lookup and prefix repairs

Status (2026-09-07): opt-in candidate with user-reported PF/PM live sample pass;
not enabled in the default player build.

Original 2026-09-06 integration boundary: the policy, aliases and probe sources were
included for review without default initialization. The dated offline evidence
below describes that earlier candidate, not the 2026-09-07 installed DLLs.

Local sampling build, 2026-09-07: `--speaker-color-candidate` explicitly adds
the policy source and guarded initialization after host/private-DLL/font checks.
It requires `--authorize-pinned-build` and cannot be combined with
`--verify-release-code`. The default build remains unchanged. Candidate hook
installation failure reports an error instead of silently appearing to pass.

The tightened native probe now also checks that a source name with no matching
style remains unmatched. Against the latest 57,503 body records, the local run
covers 134 PF and 221 PM unique source/Chinese pairs, plus original-alias and
negative regressions: 236 PF / 327 PM total pairs, zero failures. There are no
unparsed target names or missing source-name references after recognizing native
numeric prefixes such as `3:` and `10:`. This is offline coverage, not live QA.

One explicit input discrepancy is retained: PM `.004`, block `655753292`,
command offset `31180` (parser order 157) has JP speaker Takeru but EN speaker
Kasumi; current Chinese is Kasumi and follows the English dialogue. The colour
check uses the original English display speaker for this one binding; no text
is rewritten and the JP/EN discrepancy is not claimed to be resolved.

## 2026-09-07 installed sample acceptance

At the user's request, the two opt-in DLLs were installed after verifying and
backing up each pre-existing DLL. No RIO, RUO, EXE, font or save file was changed
by that installation. The user subsequently reported that the requested
PF/PM colour samples were all OK. This is sample acceptance, not a claim that
every scene, old-save transition or backlog state was individually verified.

| Game | Installed candidate SHA-256 |
| --- | --- |
| PF | `4C58F6EC31E73E81222DB25859451B05037B36D0E0BD10A350F6A5B451392158` |
| PM | `BD95F8480DD8CEA094E05B0DEBC453EE7F756F77BD71D7DA80072DE88329BBAC` |

Both candidates reproduced across two builds. The default non-candidate builds
were separately checked against their existing approved hashes and remained
unchanged. This PR exposes the tested opt-in build and records acceptance; it
does not silently enable the hook in release builds or change approved hashes.

Chinese speaker names were translated without extending the engine's name
lookup. For example `千鶴` became `千鹤`, `純夏` became `纯夏`, and `みちる`
became `美知留`. Existing names such as `武` and `尊人` continued to match.
The current native-message census covers PF 13,163 and PM 44,848 messages.

The initial experiment added 31 PF and 32 PM Chinese aliases to the root
`CBoxOcean/CStdb` setting through RUO. A PF live sample still showed white
`千鹤`. That experiment did **not** prove that the edited default table replaced
the active game's table. Its loading/restoration cause remains unconfirmed.
The table-only experiment is not the final fix and should not be promoted.

## Final lookup boundary

Both pinned executables use the same 217-byte UTF-16 name matcher. It accepts
the displayed name in ECX and a colon-separated alias list in EDX, returns a
boolean in EAX, and has one direct caller in the speaker-style lookup loop.

| Game | Matcher RVA | CALL RVA | Original CALL bytes |
| --- | --- | --- | --- |
| PF | `0xB4E80` | `0xB4FEA` | `E8 91 FE FF FF` |
| PM | `0xB6B30` | `0xB6C8A` | `E8 A1 FE FF FF` |

Matcher SHA-256:
`2C9D152FA5885E8EBD76CB6595D99DC1EA2FA2783FE29CD0E85EE5FDCBD4DF97`.

`photon_speaker_policy.c` replaces only that CALL destination after the existing
proxy verifies the host SHA-256. It also validates the instruction context and
original destination. Original matching wins. On failure, an exact reviewed
Chinese name is retried using its Japanese counterpart against the **current**
native alias list. The original style entry supplies its own colour and effects.
Names, displayed text, font, palette values, table ordering and save files are
not rewritten by this runtime hook.

This avoids relying on root-table replacement or growing the native 32-WCHAR
alias-list storage. It works with the original alias lists in the offline
probe; active-state restoration still requires later live acceptance.

## Native message repairs and merging layout work

PF has 53 malformed `姓名【正文】` fields. Restore `【姓名】「正文」`.
PM has one field whose entire `【武】「…」` wrapper was omitted. The reviewed
increments keep every body word and existing control sequence. All four edited
CRsa blocks retain their pool and encoded record sizes in the local candidate.
The PM `.004` record uses a fixed-extent edit, not a later-volume RUO redirect.

The native writer now allows a longer primary message to use a proven unused
zero run. Any pool growth still requires its existing explicit storage contract.
No auxiliary-bearing primary is accepted without the existing combined contract.

For integration, use `rebase_speaker_prefix_repairs.rebind_entries` on the
destination's effective plaintext before calling `edit_native_fields`. It
rebinds native indexes/hashes, preserves destination U+0003/U+000A decisions,
and refuses wording or other-control drift. Already repaired fields are no-ops.
Do not copy an old complete RIO/RUO over newer layout work. Future runtime
integration must preserve the current image/timer changes and obtain live
acceptance before changing the approved build.

## Historical 2026-09-06 offline verification

The local 32-bit probe executes the original machine-code matcher outside the
game and passes it to the new policy. It checks the census's unique speaker
pairs plus the existing Japanese/English aliases against original style lists.
PF: 229 pairs, 32 recovered pairs, zero failures. PM: 320 pairs, 32 recovered
pairs, zero failures. All source-name matching remained unchanged. Pair counts
include multiple Japanese aliases for one Chinese name and are not unique
translation or scene counts.

Both candidate DLLs were built twice with Zig 0.16.0 and have reproducible
normalized outputs. Their identities are recorded in
`../../evidence/photon/text/speaker-colors-offline-20260906.json`.
At that time the approved release hashes were not changed and those DLLs were not installed.
The earlier trial RIO/RUO changes were hash-checked and restored from their
pre-trial backups. All new fixes now remain in the candidate directory.

At that time the user requested that live work stop. The acceptance plan listed sample
colour restoration in PF and PM, old-save/new-scene behavior, backlog colours,
the repaired speaker prefixes, typography and PM error regression. The 28
subtitle PNGs were separately approved at `localized-v3` and are not part of
this runtime colour change.

The dated 2026-09-07 section above supersedes the earlier installation/sample
status, but does not claim exhaustive coverage of the other acceptance states.
