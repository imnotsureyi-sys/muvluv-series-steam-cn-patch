# rUGP image tools

- [`decode_record.py`](decode_record.py) is the read-only first-step tool: combine an exact ICI-catalogued volume/offset/extent with the matching supported codec and create a review PNG plus portable JSON evidence.
- [`export_crmt_layers.py`](export_crmt_layers.py) exports **all inline CRmti layers** from an exact, SHA-256-locked CRmt extent to a new directory. It does not fetch external references or treat mips as animation frames.
- [`decode_crmti.py`](decode_crmti.py) handles a class-confirmed standalone CRmti extent at its full serialized dimensions; its framing differs from an inline child.
- [`inspect_crimp.py`](inspect_crimp.py) reports typed properties from one exact CRimp extent. It never generates a PNG or infers an owner from adjacency.
- [`check_localized_image.py`](check_localized_image.py) measures dimensions, transparency and RGBA changes outside explicitly allowed text regions. Mechanical success is not translation or runtime acceptance.
- [`replace_crmt.py`](replace_crmt.py) regenerates all template mips, checks native capacity and independently decodes a new standalone replacement. It does not install or inject it.
- [`sanitize_route_closure.py`](sanitize_route_closure.py) projects a private route-working set into the path-redacted public route contract.
- [`verify_route_closure.py`](verify_route_closure.py) verifies the frozen 1,490-row Photon route closure.

Codec implementations and their proven boundaries live in [`rUGP/formats/images`](../../formats/images/README.md). These tools do not infer a locale peer, choose a writer or authorize a package merely because an image decodes successfully.

See the [CRmt family workflow](../../docs/crmt-family.md) for CLI examples, locale pairing, external-image boundaries, metadata pitfalls and release gates.
`decode_record --codec crmt` returns the top preview only; use `export_crmt_layers` for the complete inline chain.
