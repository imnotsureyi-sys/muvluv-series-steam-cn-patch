# Finding and writing text inside CRsa

CRsa is an encrypted serialized-object record. “Search the RIO for readable Japanese and replace it” is not a safe text workflow.

## Extraction chain

1. Decode ICI/reference metadata to identify a RIO volume, physical record offset, extent and parent object.
2. Validate the CRsa header and decrypt the payload in its checksum-framed chunks.
3. Parse the serialized payload according to the object type.
4. For direct strings, read the counted CString boundary and encoding.
5. For CVMMsg3, parse the command stream, source/translation indices, pool length, slot prefixes, UTF-16 text and terminal delimiter.
6. Export stable identity, source hash, controls, capacity and the exact runtime binding to a translation table.

The public [read-only extraction CLI](../../tools/text/README.md) now implements a conservative subset of steps 2–5 for CRsa extents supplied by the ICI/RIO catalog. It emits local source rows and a hash-only, unreviewed template; it does not infer capacity, writer mode, runtime authorization or perform step 6 automatically.

This approach was informed by public rUGP/GARbro behavior, but the PF/PM CString/CVM layouts, capacity census, write routes and runtime probes were independently derived for this project.

## Writing

For a supported direct field, preserve the header/object structure and replace only the authenticated value, then rebuild CRsa checksums and require an unchanged record to re-encode byte-identically. For a CVM pool, prefer an in-place slot whose native capacity is sufficient and preserve all other command indices/slots/suffix bytes.

An append-and-rewire proof exists in `crsa_vm_rewire.py`: it can append a source/translation pair, update one command's indices and rebuild the record/RUO. It remains an experimental structural proof, not the default production strategy, because runtime acceptance and every parent/extent consumer must also be proven.

## Controls and capacity

`translation_text` is what a reviewer approves. `runtime_text` is what the serializer consumes after an explicitly documented control or capacity rule. They must never drift silently. Count UTF-16 code units, not Python characters or UTF-8 bytes. Preserve trailing controls and distinguish a terminal NUL from an illegal embedded NUL; see [Internal Error 8311](error-8311.md).

## Why results from English/Japanese slots differ

The parent VM may point to separate source and translation indices, reuse a common slot, or construct a dynamic string. A byte sequence being present in a record does not prove that the active locale calls it. Runtime binding is therefore part of the stable identity, not an afterthought.
