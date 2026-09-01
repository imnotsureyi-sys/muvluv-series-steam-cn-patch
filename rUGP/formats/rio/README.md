# RIO, RUO and CRsa formats

- `crypto.py`: checked arithmetic and encrypted-block primitives.
- `references.py`: encoded archive offset/extent helpers.
- `ruo.py`: minimal RUO overlay construction and readback.
- `crsa.py`: CRsa header/chunk checksum decode and byte-identical identity re-encode.
- `crsa_text.py`: conservative read-only adjacent, counted-CString and CVMMsg3 text-slot discovery, seed expansion and false-positive accounting.
- `crsa_vm_pool.py`: CVMMsg3 command and indexed UTF-16 pool parsing/replacement.
- `crsa_vm_rewire.py`: experimental append/rewire proof for variable-length slots; not the default production route.

CRsa is a container for serialized objects, not “the text format” in one fixed layout. A record may contain ordinary counted CStrings, a VM command stream with indexed pools, or no user-visible text at all. Locate fields by verified structure and parent command references, never by replacing every readable UTF-16 sequence.

See the [CRsa postmortem](../../docs/postmortems/crsa-text.md) and [8311 postmortem](../../docs/postmortems/error-8311.md) before authoring new text writers.

The public [CRsa extraction CLI](../../tools/text/README.md) uses these readers against extents from the ICI/RIO catalog. Its hash-only output is an unreviewed translation template, not proof that a slot has a safe static writer or runtime binding.
