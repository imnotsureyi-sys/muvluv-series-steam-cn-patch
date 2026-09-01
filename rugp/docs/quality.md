# rUGP quality gates

PF/PM do not yet have a player-ready Release. These are mandatory gates for a future candidate and a description of narrow checks already enforced by individual components; their presence does not mean the complete route has passed.

## Static structure

- exact clean input hashes and volume sizes;
- decoded offset/extent resolves to the intended physical record;
- strict header, payload, trailer, chunk checksum, draw rectangle and full-stream consumption;
- identity re-encode of an unchanged supported record;
- localized encode → independent decode returns exact intended runtime text/RGBA;
- all non-target bytes/references stay unchanged or are explicitly rebuilt and audited.

## Runtime

- clean baseline launches without an old RUO or font transaction contaminating the result;
- one-variable differential probes before a bulk build;
- host/private DLL/font hashes and architecture match;
- hook count, selected resource ID, geometry and transaction status are observable;
- no English/Japanese fallback, missing image, color-channel swap, alpha tear, stale state, or first-frame race;
- both start/exit/restart and the actual menu/story paths are tested.

## Release

- PF and PM pass independently;
- reproducible runtime build hash and package member hashes;
- no workstation path, credential, PDB, source archive, or rejected candidate;
- installer refuses unknown inputs and supports exact rollback/Steam recovery;
- PF/PM installer validates the confirmed Steam `english` route in both locale fields and rechecks the same manifest seal immediately before its first write;
- image/text/font manifests bind every installed byte.
