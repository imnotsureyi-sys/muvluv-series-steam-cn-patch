# Photon images: why a correct localized bitmap still failed at runtime

## Symptom matrix

Several failures looked like image-editing mistakes even though the reviewed localized bitmap was correct:

| Runtime symptom | Falsified shortcut | Actual layer that needed investigation |
| --- | --- | --- |
| Japanese or English remained visible | “The translated asset was never made” | locale endpoint and parent/reference selection |
| blank label or white screen | “Any decodable child record can replace the old span” | child extent, parent ownership, ICI/RUO transport |
| wrong colours, stripes, tearing or double drawing | “Self-decoding proves engine compatibility” | codec profile, guarded tail, state-bank composition and decoded-surface timing |
| one state changed while others did not | “One visible button equals one image record” | multi-state bank geometry and parent scatter |
| a replacement later reverted | “The first decode is the final displayed surface” | engine overwrite/redecode order and runtime state identity |

## What the differential work established

The directory and parent audit separated semantic routing from transport:

- 1,448 images have authenticated translation peers.
- 42 are authenticated shared/common endpoints; they are not permission to fall back to or double-write the Japanese slot.
- A source and target can have different geometry, and several localized sources can alias one physical target or collide with different desired states.
- In the first native-capacity census, only 118 distinct targets fit their official extents, 1,317 were oversized and four remained unresolved. A strict decoder accepting a larger record did not make it safe to overwrite the next object.

Controlled one-record probes then separated the routes. A native translation-slot replacement for the PM “Voice Skip” label displayed and remained interactive. Other tested RUO parent/leaf arrangements either blanked the child, triggered 8311 through an unrelated bad text container, or left the official English child selected. Later full batches exposed parent/state and decoded-surface timing that a single successful child could not prove.

## Why the project moved to a hybrid design

The stable rule is chosen per authenticated endpoint:

1. use an exact native record only when its format, geometry and extent are independently proven;
2. use one cumulative RUO only when the complete redirected record and footer/reference graph are proven;
3. rebuild the nearest authenticated parent/container when a child grows and that parent writer is proven;
4. use the exact-build runtime route for decoded surfaces or font/GDI behavior that cannot be represented safely as an archive-only replacement;
5. leave the item blocked when none of those transports has both static and runtime evidence.

The Hook is therefore not a blind external image loader. It is version- and identity-gated and must disable an optional route on unknown state instead of guessing.

## Production and review rules

- Preserve separate identities for source bitmap, localized authority, encoded record, logical locale endpoint, physical target and runtime observation.
- Never infer a translation peer from adjacency, similar pixels or a missing English filename.
- Treat each visual state and parent bank explicitly; one passing state does not authorize siblings.
- Require independent decode, exact range/parent checks and an in-game visual test. These are three different gates.
- Test a clean baseline and one changed variable; quarantine old RUOs and previous runtime DLLs so they cannot contaminate the result.
- Record failures and supersede unsafe candidates rather than silently replacing their evidence.

## Remaining boundary

The public route closure proves semantic ownership for all 1,490 reviewed images, and the V6 bundle binds reviewed localized authorities. It does not claim that all 1,490 currently have a public clean-install-to-runtime transport. Oversized children, a small set of capacity/parent cases and full-game visual coverage remain release gates. See the [route evidence](../../evidence/photon-image-routes-v1/README.md), [image evidence](../../evidence/photon-images-v6/README.md) and [packaging boundary](../../packaging/README.md).
