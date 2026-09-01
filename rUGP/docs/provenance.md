# rUGP provenance model

The stable ID describes an artifact without publishing its complete official contents. In the two runtime-bound Photon text tables it is accompanied by game, RIO file, block/payload/text offsets, writer mode, delimiter/control contract, capacity, source-field hash and source-identity hash. The larger reviewed-text tables intentionally use a coarser review/porting contract—stable ID, RIO/scene, source-field hash and translated text—and are not writer inputs. For images the identity chain includes game, volume, offset, codec/kind, geometry, official record hash, localized authority hash and packaging authority.

The two portable runtime-bound Photon text tables deliberately omit full official source strings. A contributor extracts them from a legally obtained game and verifies the stable ID plus hashes before applying the localized text. `translation_text` is the human authority; `runtime_text` is the exact serialized value and may differ only for an explicitly recorded control/capacity reason.

The two Photon CSVs are byte-preserved in `.gitattributes` because some quoted
fields contain meaningful CRLF controls. Do not run a generic line-ending
normalizer over them. Their byte counts and SHA-256 values are locked by
`evidence/photon/text/runtime/manifest.json` and a clean-checkout regression test.

The separate [57,547-row reviewed-text evidence](../evidence/photon/text/reviewed/README.md) preserves the wider translation work for review and other locales without pretending those rows have already been bound to a writer/runtime route.

The image V6 manifest distinguishes an approved review PNG from a native encoded record. For 243 recovered previews the native record is authoritative; decoding the preview and re-encoding it would be a lossy, unreviewed new asset.

Local absolute paths, a gallery filename, and “it looked right once” are not provenance. Content hashes, exact object identity, build code, runtime result, and release manifest are.
