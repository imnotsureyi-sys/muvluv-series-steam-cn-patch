# AGES Internal Error 8311: embedded NUL in a counted CString

The observed dialog says **AGES Internal Error 8311**. Some working notes and conversations abbreviated it to “831”; this document uses the exact number.

## Symptom

A Photon Melodies RUO passed every static CRsa check but the game rejected it during startup with Internal Error 8311. Early hypotheses blamed Chinese glyphs, CRsa encryption/checksums, a changed record extent, self/parent references, or a missing nested-footer update.

## Controlled differential

The final experiment used PM record ordinal 2 and held everything structural constant:

- native position/ordinal unchanged;
- record extent `3821` bytes and plaintext extent `3578` bytes unchanged;
- product identifier, self-reference, field count/boundaries, header, and bytes outside one menu CString unchanged;
- CRsa identity re-encode and every encrypted chunk checksum verified.

Three variants isolated the serialized value:

| Variant | Counted CString content | Actual game result |
| --- | --- | --- |
| F | `返回标题菜单` plus five embedded `U+0000` code units to retain 11 units | Internal Error 8311 |
| M | a one-unit non-NUL UTF-16 change | Startup passed |
| N | natural 11-unit Chinese `返回至游戏标题菜单界面` | Startup passed |

An independent census of all 151 official counted CStrings found zero with an embedded `U+0000`.

## Root cause

`U+0000` is legal as the terminal delimiter outside the counted value. It is not a safe padding character *inside* a length-counted CString. The serializer's static structure remains valid, but the AGES runtime rejects the value.

The failure was therefore **not** caused by Chinese text, record location, RIO/RUO transport, CRsa encryption, checksum drift, record growth, or missing parent closure. Those hypotheses were useful but were falsified by the M/N controls.

## Production rule

- Never embed `U+0000` inside a counted CString.
- For a native fixed-capacity field, use natural non-NUL text with the exact required UTF-16 unit count.
- Rephrase an overlength field or fail closed. Do not silently pad with `U+0000`, ASCII space, or ideographic space.
- Where the reviewed runtime contract explicitly permits invisible capacity fill, use the pinned `U+2060` font/runtime path and record it in `padding_codepoint`; this is a separate, tested rule, not a generic serializer trick.
- Keep the terminal UTF-16 NUL that ends a direct pool slot; it is not part of the visible counted value.

For the large ordinal-49 CVM pool, 774 of 799 translations fit their native slots and 25 required rephrasing or fail-closed handling. Append/rewire was statically demonstrable but changed the record extent and added risk without being necessary for the 774; production therefore prefers exact in-place slots.

## Regression boundary

The portable translation manifest stores `native_capacity_units`, `replacement_units`, `padding_codepoint`, and `padding_units`. Writers must reject an unapproved embedded NUL and must distinguish counted-CString serialization from NUL-terminated CVM pool storage.

Capacity has route-specific meaning. A `direct_top_level` record is rebuilt as
a variable-length RUO record, so an audited natural replacement may grow; an
over-capacity control/layout change must carry an explicit reason. A
`nested_requires_linking` value is scattered into an existing native range and
may not grow. Its public `runtime_text` can be shorter than the effective
capacity only when the writer restores native leading or trailing boundary
controls from the legally extracted source record.
