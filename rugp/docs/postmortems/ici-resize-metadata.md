# ICI growth: duplicate sizes and preserved outer-header metadata

## Symptom

A rebuilt Photon ICI passed the project's first static decoder, yet a full image candidate could still produce a white screen. The affected candidates were the ones whose enlarged RIO changed the ICI allocation bitmap length. Three candidates whose encoded ICI length did not change remained byte-identical; five length-changing candidates shared the failure pattern.

## Wrong assumption

The first helper treated the encrypted wrapper as a generic length header whenever the plaintext length changed. That regenerated the second header word with low three bits set to `7`. The clean PF/PM files carried `3` in those metadata bits.

The decoded `CInstallSource` object also stores the final RIO size twice. Updating only the obvious size field is therefore incomplete even when the object graph otherwise parses.

## Discriminating repair

The corrected, read-only experiment started again from hash-locked clean bytes and changed only derived size information:

1. decode the exact clean encrypted wrapper and ICI payload;
2. update both serialized RIO-size values;
3. extend the allocation bitmap only with the zero bits implied by the new block count;
4. rebuild the redundant encrypted size header for the new plaintext extent;
5. inherit the clean second word's low three metadata bits exactly;
6. independently decode both size fields, the bitmap and all non-target archive references.

All eight synthetic/candidate rebuilds passed both static decoders. The five previously affected headers changed only at the expected metadata-bearing byte, and the three unchanged-length cases remained byte-identical.

## Production rule

- An ICI resize is an object-graph change, a bitmap change and an encrypted-wrapper change; it is not a one-field integer patch.
- The two `CInstallSource` RIO sizes must agree with the final archive length.
- Wrapper bits whose meaning has not been independently established are inherited from the exact clean file, never replaced with a convenient default.
- Rebuild from a clean, hash-locked ICI. Do not repair an earlier generated candidate in place.
- Cross-decode the result and prove that all unrelated references are unchanged before it can enter a package candidate.

## Evidence boundary

This closed a static root cause only. The recorded repair run performed zero game writes and zero AGES launches; its state was explicitly `runtime pending` and `release=false`. The repository therefore preserves the algorithm and failure lesson, but does not publish the old data-specific repair helper as a general production ICI writer. A future writer needs synthetic tests for duplicate sizes, bitmap growth boundaries, low-bit inheritance, byte-identical no-op output and independent decoding before any runtime authorization.
