# Translation peers and the 42 shared/common images

## The question

Most official Photon images have a Japanese/source endpoint and a separate translation endpoint. Forty-two did not. It was tempting either to replace the Japanese source slot or to assume all 42 used one undocumented translation rule.

## Evidence chronology

The first complete graph pass proved 1,448 translation-peer routes. For the remaining 42 it proved only direct source keys; three were already demonstrably common fields inside bilingual parents, while 39 lacked enough parent topology evidence. That stage correctly remained release-fail-closed.

A later authenticated parent/family audit resolved the 39 without inventing translation siblings. The final 42 are:

| Class | Count | Meaning |
| --- | ---: | --- |
| Common fields inside bilingual parents | 3 | Japanese/English pages are separate, but navigation fields are structurally common |
| Singleton common state bank | 32 | one 8×4 visual-state bank (enabled/disabled/selected/pushed), with no parallel locale bank or language selector |
| Singleton common UI parent endpoint | 7 | one endpoint in the parent, with no official translation peer |

Thus the final route census is 1,448 `translation_peer_native_range` plus 42 `proven_shared_native_range`. None of the 42 is authorized by “fall back to the Japanese slot”; its parent structure proves a genuinely shared endpoint.

## Why display can still differ

Files that look identical in a directory listing may be selected by different parent fields, composed into different state banks, decoded into a reused surface, or overwritten later. Static route authority answers *which logical endpoint is correct*. It does not prove that an encoded replacement fits the old extent or that the engine consumes a rebuilt parent correctly.

For that reason the parent-family audit closed the semantic route while keeping production/runtime authorization separate. Packaging/runtime work must address native extent, append/ICI, parent scatter, decoded-surface timing and visual QA independently; any row without transport, runtime and visual proof remains blocked.

## Rule

Never generalize “shared/common” from adjacency, identical pixels, or a missing English neighbor. Prove the authenticated parent object, count all matching endpoints/banks, check locale selector fields, preserve state geometry, and require an actual runtime observation for the chosen transport.
