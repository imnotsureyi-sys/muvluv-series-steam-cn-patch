# CRip007: from compressed bytes to an exact grayscale replacement

## Reference and independent proof

GARbro's MIT-licensed `ArcFormats/rUGP/ImageRIP.cs` documents the CRip007
channel-bit fields and its no-alpha Bgr32 branch. That was a decoder reference,
not a repacker. This project implemented its own strict decoder and encoder,
then verified the production profile through a second, deliberately narrow
reference decoder.

Four audited PF/PM source records were byte-identical 800×600 black-background
white-text images. Their structure was exactly:

```text
0x28-byte header + uint32-sized payload
```

There was no trailer. The native high byte `0x80` in the Bgr32 path represents
fully opaque output; exported review PNGs must map it to alpha 255.

## Why the encoder changed the channel profile

The localized antialiased grayscale candidate used all 256 gray levels.
Keeping the original 6/6/6 channel widths would quantize those edges. The
reviewed encoder therefore preserved the structural header template, changed
only the three channel-bit fields to 8/8/8, and updated payload length. It did
not append a fake trailer or count placement padding as payload.

## Verification

Both the complete audited CRip007 decoder and an independent 8-bit/no-residual
grayscale decoder consumed the replacement payload exactly and produced RGBA
bytes identical to the approved candidate: zero channel error, zero changed
pixels and zero alpha error. Header bounds and PF/PM unit-4 redirect keys were
checked separately.

The public decoder/encoder and synthetic tests are in
[`rUGP/formats/images/`](../../formats/images/README.md). The result establishes
this 8-bit grayscale profile, not every theoretical CRip007 flag combination;
final cumulative-RUO and in-game smoke tests remain release gates.
