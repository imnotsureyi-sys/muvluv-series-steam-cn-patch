# rUGP architecture

## Directory and archive layers

An ICI is a small encrypted serialized catalog. Once decoded, its object/reference graph supplies names, classes, encoded offsets and extents. The payload may live in the base RIO or a numbered continuation volume. The ICI is not a ZIP central directory with ordinary files and it is not the image decoder.

`CodeArcRef` is the engine's serialized archive-reference concept: it binds an object to an encoded archive position/extent. It was not invented by this project. GARbro, AFHook/rUGP research and direct executable/runtime observation supplied the vocabulary; this project independently audited the exact PF/PM instances and their parent bindings.

## Typed records

- **CRsa** wraps encrypted serialized objects. Some contain direct counted CStrings; others contain CVM message commands and UTF-16 pools referenced by indices.
- **Cr6Ti** is the dominant AGES image codec in the audited Photon set. Standard records use LSB-first compressed pixel streams.
- **CRip007** is a narrow older MSB-first RGB branch represented by four audited assets.
- **CRip008** uses an MSB-first integer stream, optional predictors, draw rectangles, and kind-specific RGB/alpha semantics.

Cr6Ti and CRip008 share an initial serialized-object signature, so magic bytes alone are insufficient; strict header framing and payload-length locations distinguish them.

## Three replacement routes

1. **Native exact/in-place record:** best when the encoded result fits the proven target extent and all references remain valid.
2. **RUO overlay:** supplies replacement records keyed to source ranges without rewriting the whole RIO. It still obeys the engine's object and reference contracts.
3. **Pinned runtime:** used where the locale endpoint is shared/dynamic, the decoded surface is selected after archive resolution, or GDI font requests override static font configuration.

The runtime is not a generic “load any PNG” hook. It verifies the exact host executable, private resource DLL, font, generated identity tables, draw geometry and surface state before installing a narrowly scoped route. Failure disables the optional image path rather than accepting an unknown build.
