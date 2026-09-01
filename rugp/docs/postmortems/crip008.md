# How CRip008 was reverse engineered

CRip008 support was not guessed solely by comparing a compressed byte string with a finished PNG. It combined prior format context, executable/runtime behavior, strict sample structure, and controlled codec tests.

## Starting evidence

- GARbro/AFHook/rUGP work established the wider AGES resource model and related image semantics.
- Cr6Ti and CRip008 share the serialized-object prefix `00 04 45`, proving that the first three bytes are not a unique format magic.
- PF/PM official records supplied repeatable headers, payload extents, kinds, draw rectangles and decoded images.
- Native decoder/disassembly behavior supplied the MSB bit-reader, variable-length integer table, predictor flags, channel state and kind-specific alpha rules.

## Reconstruction sequence

1. Map stable header fields: canvas, signed offset, draw rectangle, kind/depth, flags, channel widths, and CRip008's payload length at `0x1D` with payload at `0x29`.
2. Implement a bounds-checked MSB reader and reproduce the 4,096-entry integer decode table.
3. Decode one official branch at a time, checking full draw-rectangle coverage and predictor state rather than accepting a visually plausible preview.
4. Convert native channel/alpha layouts to RGBA and compare hashes/dimensions across independent official samples.
5. Implement the inverse writer as a deliberately simple subset: literal rows, 8/8/8 channels, conservative runs.
6. Independently decode every generated stream and require exact native-pixel/RGBA readback.
7. Put the record through the real RUO/runtime route; a library round trip alone does not prove engine acceptance.

Kind 2 is the opaque path and uses native B,G,R plus opacity `0x80`. Kind 3 has a draw rectangle and native alpha codes (0, 1–31, 32/opaque) with its own channel ordering/predictor state. The current encoders favor correctness over compression because a RUO/runtime transport can carry a larger record.

## What a successful test proves

One successful CRip008 kind-3 image proves that image's header/flag profile and the encoder subset exercised by its pixel patterns. It does not automatically prove every kind-3 record: another record may use a different rectangle, partial alpha, predictor combination, channel precision, or unsupported flag. The test suite therefore includes transparent/opaque/partial-alpha and geometry cases, and production still validates each source template.

## Human workflow without AI

The same method applies without an AI agent: collect known samples, disassemble or trace the native decoder, name fields cautiously, implement a strict reader, create tiny synthetic patterns that isolate one branch, invert only proven operations, and run controlled game tests. AI shortens code/search iteration; it does not replace the experimental controls.
