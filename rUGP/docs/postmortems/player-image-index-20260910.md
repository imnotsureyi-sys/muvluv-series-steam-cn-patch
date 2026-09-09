# Player package lost previously working album translations

The user installed the 2026.09.10 PF/PM packages on another computer. New UI and
CRmt presentations appeared, but previously accepted album translations,
including PF festival signs, were absent. This was a packaging regression.

The private assembler regenerated ordinary image tables in manifest order.
The production loader binary-searches `(payload_bytes, payload_fnv1a64)` in
strictly ascending order. The package preserved PNG files and their hashes but
emitted unordered tables, making 252 of 1,197 PF entries and 198 of 1,596 PM
entries unreachable. The previously accepted runtime tables were ordered.

The packaging checks proved file membership, pixel hashes and header inclusion,
but never exercised lookup of every entry in the newly generated delivery
headers. Existing route tests used the repository's ordered tables, so those
results did not cover the package-specific regression.

The fix sorts complete rows by their numeric lookup keys without changing their
PNG/RGBA identities. Runtime preparation rejects unordered keys, duplicate keys
and count mismatches before compiling; tests cover both historical PM header
branches. `exact_rgba_table_replay.c` uses the production lookup and PNG loader
with the delivery include root, not the repository baseline.

| Delivery table | PF unreachable / decoded | PM unreachable / decoded |
| --- | --- | --- |
| Faulty 2026.09.10 | 252 / 945 | 198 / 1,398 |
| Sorted replacement | 0 / 1,197 | 0 / 1,596 |

All reachable PNG loads passed their existing authentication checks. The same
final generated headers also pass the PF G2018/G2019 full/partial festival
fixture against the assembled archive, including two/three trailing bytes,
both pitch signs and unchanged pixels outside the partial rectangle. G1661,
G1662 and G1972 were also present but unreachable in the faulty table.

These are runtime lookup/load and surface-commit results. They do not execute
the proprietary decoder, Steam startup or every scene. The user still needs
to replay the final combined package in game. The 1,789 image-bearing review
entries are a provenance catalog, not the number of ordinary runtime routes or
a claim of complete live acceptance.

The maintainer separately requested a player installer with no backups or
rollback. The revised installer writes directly, reports failures with Steam
reinstallation instructions, and cleans its own temporary extraction on normal
exit. This policy does not authorize deleting historical local development
archives or save files.
