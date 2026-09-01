# rUGP image tools

- [`decode_record.py`](decode_record.py) is the read-only first-step tool: combine an exact ICI-catalogued volume/offset/extent with the matching supported codec and create a review PNG plus portable JSON evidence.
- [`sanitize_route_closure.py`](sanitize_route_closure.py) projects a private route-working set into the path-redacted public route contract.
- [`verify_route_closure.py`](verify_route_closure.py) verifies the frozen 1,490-row Photon route closure.

Codec implementations and their proven boundaries live in [`rugp/formats/images`](../../formats/images/README.md). These tools do not infer a locale peer, choose a writer or authorize a package merely because an image decodes successfully.
