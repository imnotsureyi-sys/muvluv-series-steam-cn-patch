# Photon speaker colours: Chinese name lookup and prefix repairs

Status: offline candidate, not approved for player release or live acceptance.

Integration boundary in this draft: the policy, aliases and probe sources are
included for review, but neither the default build source list nor proxy
initialization enables this policy. The DLL evidence below describes the
separate private candidate, not the default DLL built from this draft.

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

## Offline verification and remaining acceptance

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
The approved release hashes were not changed; new DLLs are not installed.
The earlier trial RIO/RUO changes were hash-checked and restored from their
pre-trial backups. All new fixes now remain in the candidate directory.

The user requested that live work stop. Still required before release: sample
colour restoration in PF and PM, old-save/new-scene behavior, backlog colours,
the repaired speaker prefixes, typography and PM error regression. The 28
subtitle PNGs are separately approved at `localized-v3` and are not part of
this runtime colour change.
