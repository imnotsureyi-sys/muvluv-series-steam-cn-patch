# PM BETA 0.1.1 special-text correction

PM BETA 0.1 could display Japanese text, duplicate lines, or missing glyphs in
special monologues despite the Chinese translation being present in the target
language slot. The reported scene was reproduced in 憧憬, including messages
254–256 of `photonmelodies11.rio.003:1519248208`.

The original display prefix contains U+0010 followed by a numeric font argument
and a colon. The text had been converted for ordinary-font layout, but the final
writer restored only U+0010 from the original field. This left a malformed
command. Restoring its complete original argument removed the observed duplicate
Japanese, but selected a special font that lacked some Chinese glyphs.

At the maintainer's request, the final correction removes the leading U+0010
from 297 affected Chinese fields across seven CRsa records and uses the ordinary
font. It preserves the translated body, line breaks, original Japanese slots,
annotations, and action/directive fields. Record extents remain unchanged. The
private delivery writer no longer restores this prefix for PM and rejects
U+0010 in its Chinese target text. PF had no affected prefix and is unchanged.

The seven replacement records were verified against the previously released
records, encoded, read back, and installed. In-game checks covered the reported
three lines, surrounding special monologues, the later startled interjection,
backlog text, Return to Game, and reloading the new check save. The maintainer
confirmed the result. The follow-up static audit compared both games' current
text with the reviewed tables and verified final image and animation payloads.
This is not an exhaustive playthrough or a fresh manual review of every line.

The player update is **PM BETA 0.1.1**, internal build `2026.09.11-r4`. It is a
complete standalone ZIP, with direct installation over the known public BETA
0.1 state. PF remains BETA 0.1. The installer, image assets, and animation
replacements retain their r3 identities. No backup or uninstaller is added.
