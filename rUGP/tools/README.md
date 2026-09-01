# Public rUGP tools

Only portable, supported commands live here. Format implementations live in `rUGP/formats/`; production runtime and packaging have their own directories.

- `text/export_translation_sources.py`: export/check public portable translation tables from a sealed private audit.
- `text/export_reviewed_translation.py`: deterministically redact a complete reviewed comparison table to stable identity, exact source-text hash, and translated text; the 57,547-row Photon authorities use this path.
- [`text/extract_crsa_text.py`](text/README.md): consume a read-only RIO catalog plus explicit local volume bindings and emit a local CRsa source audit and/or hash-only translation template.
- [`provenance/verify_photon_images_v6.py`](provenance/README.md): verify the published Photon V6 image archive against the checked-in manifest and pinned authority hashes; its directory README documents provenance inputs and checks.
- [`provenance/export_portable_photon_snapshot.py`](provenance/README.md): export path-redacted metadata and, only when explicitly requested, a private content-addressed candidate snapshot without official sources.
- [`provenance/audit_photon_locale_bindings.py`](provenance/README.md): reproduce the metadata-only CN/JP/EN binding and 1,490-route audit from separately held, hash-locked project inputs.
- `catalog/rio_inventory.py`: read an ICI plus user-supplied RIO volumes and export the logical resource/type/volume/offset/extent catalog without modifying game files.
- [`images/decode_record.py`](images/README.md): turn one exact catalogued Cr6Ti/CRip007/CRip008 extent into a review PNG and portable metadata report without writing the archive.
- `images/verify_route_closure.py`: prove that all 1,490 approved Photon image identities have an authenticated translation-peer or shared/common semantic endpoint.

Historical probes, per-image candidate builders, runtime bisects and developer-machine installers were deliberately not promoted. Their lasting conclusions are in docs, production code, manifests, and tests.
