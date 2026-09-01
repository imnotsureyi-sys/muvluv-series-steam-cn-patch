# rUGP format libraries

`images/` contains record-level image codecs; `rio/` contains archive encryption/reference/RUO and CRsa/CVM structures. They are libraries used by tests and production builders, not a single command that blindly unpacks every RIO.

Supported scope is intentionally narrower than every historical rUGP variant. Unsupported flags, legacy headers, ambiguous extents, malformed checksums, unrepresentable alpha, or an encoder outside its tested subset raise an error.

Each encoder is paired with strict decode/readback tests under `rugp/tests/formats/`. Adding a decoder branch does not authorize writing that branch; add a separately verified encoder and runtime evidence.
