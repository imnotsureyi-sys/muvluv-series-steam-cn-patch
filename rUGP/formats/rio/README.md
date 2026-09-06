# RIO, RUO and CRsa formats

- `crypto.py`: checked arithmetic and encrypted-block primitives.
- `references.py`: encoded archive offset/extent helpers.
- `ruo.py`: minimal RUO overlay construction and readback.
- `crsa.py`: CRsa header/chunk checksum decode and byte-identical identity re-encode.
- `crsa_text.py`: conservative read-only adjacent, counted-CString and CVMMsg3 text-slot discovery, seed expansion and false-positive accounting.
- `crsa_vm_pool.py`: CVMMsg3 command and indexed UTF-16 pool parsing/replacement.
- `crsa_vm_stream.py` and `crsa_vm_schema.json`: sequential, read-only PF/PM native command/object parsing using executable-hash-bound field descriptors, including counted strings, call arguments, message pools and trailing references. Unknown layouts fail without byte resynchronization.
- `crsa_vm_fields.py`: inventories all three message fields in each language and every pool cell; records stale annotation indices and adjacent recovery evidence separately.
- `crsa_vm_edit.py`: hash-bound PF/PM message and annotation edits. It prefers native slots and unused zero runs; non-empty orphan reuse or pool growth requires an explicit reviewed storage contract. It exposes no armament-parameter write action.
- `crsa_vm_rewire.py`: experimental append/rewire proof for variable-length slots; not the default production route.

CRsa is a container for serialized objects, not “the text format” in one fixed layout. A record may contain ordinary counted CStrings, a VM command stream with indexed pools, or no user-visible text at all. Locate fields by verified structure and parent command references, never by replacing every readable UTF-16 sequence.

See the [CRsa postmortem](../../docs/postmortems/crsa-text.md) and [8311 postmortem](../../docs/postmortems/error-8311.md) before authoring new text writers.

The public [CRsa extraction CLI](../../tools/text/README.md) uses these readers against extents from the ICI/RIO catalog. Its hash-only output is an unreviewed translation template, not proof that a slot has a safe static writer or runtime binding. The separate native-field auditor consumes a hash-checked full-volume scan cache; see the [PF/PM full-field audit](../../docs/postmortems/crsa-native-text-20260903.md) for its completed static coverage and remaining runtime boundary.
