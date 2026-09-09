# rUGP image formats

| Format | Public support |
| --- | --- |
| Cr6Ti | strict standard decoder; reviewed kind 2/3 encoder profiles |
| CRip007 | narrow q=0 legacy RGB decoder/encoder for the four audited PF/PM records |
| CRip008 | bounded kind 2 and kind 3 decode for the documented header/flag profiles; simple literal-run encoders intended for RUO/runtime transport |
| CRmt / CRmti | five observed parent layouts; 5/6/7-bit RGB profiles and both observed bit orders; bounded inline and standalone framing, capacity-aware encoding and independent readback |
| CRimp | strict typed property map reader/writer; not a raster codec |

The raster codecs store compressed channel/prediction commands, not a human-readable list of colors. Decoding executes those commands into a pixel buffer, then converts native channel/alpha conventions into review RGBA. Encoding chooses a valid command stream whose independent decode reproduces the intended buffer. CRimp instead stores typed metadata.

## CRmt family

Start with the [family guide](../../docs/crmt-family.md) and [current review catalog](../../evidence/photon/crmt/README.md).
[`crmti_decode.py`](crmti_decode.py) and [`crmti_encode.py`](crmti_encode.py) preserve bounded parent framing;
[`crmti_capacity.py`](crmti_capacity.py) checks the native allocation constraints;
[`crmti_record.py`](crmti_record.py) handles independently stored CRmti without an inline wrapper.
[`crmt_metadata.py`](crmt_metadata.py) replays the observed compact metadata/cache layouts;
[`crimp.py`](crimp.py) preserves type tags and lossless property values.

The external image and ImageMP are separate references. A declared CRip007 base class does not select the CRip007 pixel decoder when the actual serialized object is CRmti.
CRimp tagged integers are not universally 16.16 values; origin interpretation is consumer-specific, not a proven final screen position.
Unknown layouts, profiles or property kinds are rejected rather than guessed. Neither metadata parsing nor pixel readback certifies a scene or installable patch.

CRip008 kind 2 output is deliberately large and opaque; kind 3 supports draw rectangles and native partial-alpha codes. The review decoder rejects zero/truncated payloads, bitstream overruns, trailing payload bytes, non-zero final padding, non-positive or excessive canvases, unsupported header versions/depths/flags, and invalid draw geometry before allocating the output. Its current safety ceiling is 16,777,216 pixels; the only accepted tail is 0–7 zero bits needed to reach the declared payload byte boundary. Success for one supported kind/flag profile does not prove unrelated flags such as the distinct kind-2 `flag8` route.

## First read-only decode

Use the ICI [catalog tool](../../tools/catalog/README.md) first; do not guess an offset from readable bytes. Then pass the catalogued volume, `volume_offset`, exact `extent` and exact class/codec to the safe review decoder:

```powershell
python -m rUGP.tools.images.decode_record `
  --source "X:\Game\example.rio.002" `
  --offset 0x123400 `
  --extent 0x5678 `
  --codec crip008 `
  --output "X:\Work\review.png"
```

`cr6ti`, `crip007` and `crip008` are accepted only by their documented supported profiles. The command reads exactly one extent, refuses length/range mismatches, never writes the RIO, and publishes each new PNG/report file through a same-directory create-only atomic link. If an ordinary exception occurs after the first publication, it removes already-published siblings; this is not a claim of crash-atomic two-file transactions. Existing outputs and input aliases are refused. A successful PNG proves this decoder/profile and record extent; it does not prove a safe encoder, replacement capacity, parent route or game acceptance.
