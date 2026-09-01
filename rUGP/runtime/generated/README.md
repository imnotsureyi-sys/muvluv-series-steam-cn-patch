# Sealed generated runtime configuration

These six headers are reviewed, hash-locked runtime configuration inputs. They
contain identities, sizes, geometry and routing metadata, but no game image
payloads. [`provenance.json`](provenance.json) records each file's exact bytes,
SHA-256, role and any sealed source-manifest identity embedded in the header.

The important limitation is explicit: the public repository currently has no
maintained deterministic generator plus complete publishable input set for
these headers. A clean clone can verify their hashes, stage the authorization
bit in a temporary directory, compile them, and reproduce the normalized DLL;
it cannot regenerate the tables independently. They are therefore classified
as **sealed reviewed configuration**, not as publicly reproducible generated
source.

Changing a header requires more than editing its checksum. A future update
must either publish a deterministic generator and redacted/hash-bound inputs,
or repeat the private authority audit and replace this provenance manifest in
the same reviewed change. Until then, docs and build manifests must preserve
the distinction between “reproducible compile from checked-in configuration”
and “reproducible generation of that configuration.”
