# PF festival thumbnail translated, animated presentation missed

The user observed Chinese in the album thumbnail G2498 (Cr6Ti, 210×123), but
Japanese festival signs inside the animated presentation. The full background
G2018 and partial frame G2019 (both CRip008, 800×600 canvas) already had correctly
installed and authenticated Chinese sidecars. Thumbnail success did not exercise
the same decoder family or geometry.

A local diagnostic build using the existing native trace captured:

| Resource | Archive payload | Decoder extent | Archive FNV-1a | Live FNV-1a | Result before fix |
| --- | ---: | ---: | --- | --- | --- |
| G2018 | 698581 | 698584 | `F65147B1D6AFBA5A` | `EA340C47517CC61E` | Identity not targeted |
| G2019 | 88785 | 88788 | `A3CEF04B988F1823` | `87F23A5C351CD961` | Surface rejected |

Extending each archive FNV with exactly three zero bytes produces the observed
live FNV. The full image was missed three times. The partial call's target and
clip both equal `(74,114)–(306,367)`, matching the archive's 232×253 draw extent.
Both use pitch 3200 and an 800×600 destination canvas. Native tracing was removed
from the installed runtime after the capture; logs and game data remain local.

The existing padding retry was restricted to 120–130 KB date-card payloads. PF
now retries exactly two/three trailing bytes for the same 800×600 canvas family,
only accepting a complete remaining length/FNV identity in the sealed table. It
does not scan for arbitrary prefixes. PM's prior extent policy is unchanged.

For the observed G2019 identity and exact rectangle only, preparation authenticates
the complete 800×600 sidecar and derives the canvas view, then retains only its
232×253 rectangle for transactional commit. No pixels outside that rectangle are
written. Other nonzero-origin/clip shapes remain rejected pending evidence.
The entire caller buffer, including padding, is still hashed before and after
the original decoder, preserving mutation detection.

[`pf_festival_route.c`](../../tests/runtime/pf_festival_route.c) accepts a local
bundle root and PF archive as arguments. It exercises the production preparation
and commit against the two actual archive payloads and installed sidecars, with
zero/two/three padding bytes (including nonzero padding), both pitch signs,
pre-commit no-write and outside-rectangle byte checks. Four-byte padding, changed
payloads and a shifted partial rectangle are rejected. It does not execute the
proprietary decoder; private inputs are not shipped in Git or run in CI.

The installed normal build is recorded in the current runtime sync evidence.
PM rebuilt byte-for-byte identical to the user's already accepted album fix.
The user replayed the same presentation after installation and confirmed that
both the background and animated signs are now correct. This closes these two
observed resources' live acceptance, not every CRip008 partial format.
