# rUGP reverse-engineering and incident records

These notes preserve the experiments behind the current Photon Flowers / Photon Melodies support. They are not a claim that every rUGP game, record variant, or clean-install-to-release path is supported.

## Case index

| Case | Question answered | Reproducible evidence | Remaining boundary |
| --- | --- | --- | --- |
| [Internal Error 8311](error-8311.md) | Why did a structurally valid CRsa/RUO fail at startup? | Controlled F/M/N CString variants, a census of official strings, public manifest/exporter tests | The conclusion applies to the observed counted-CString route; it is not a catalogue of every AGES error code |
| [CRsa text](crsa-text.md) | How are direct strings and CVMMsg3 pool strings located and rewritten? | Read-only [catalog/extractor](../../tools/text/README.md), [`crsa.py`](../../formats/rio/crsa.py), [`crsa_vm_pool.py`](../../formats/rio/crsa_vm_pool.py), and synthetic tests | The extractor is conservative and append/rewire remains experimental; it does not bind every extracted row to a production writer/runtime route |
| [RUO overlay](ruo-overlay.md) | What does a `.ruo1` redirect, and why are multiple independent RUOs unsafe? | [`ruo.py`](../../formats/rio/ruo.py) plus synthetic footer/unit/merge tests | A valid redirect map does not prove the replacement record or game route |
| [Cr6Ti extent](cr6ti.md) | Is archive alignment part of the serialized image record? | Strict Cr6Ti codecs/tests and an independent PF record census | Proven standard and named legacy profiles do not authorize unknown flags/profiles |
| [CRip007](crip007.md) | How did four source records become exact antialiased grayscale replacements? | Strict decoder/encoder, independent narrow reference decoder and synthetic tests | The proved 8-bit grayscale profile is not every theoretical CRip007 variant |
| [CRip008](crip008.md) | How was the decoder and conservative encoder subset derived? | [`formats/images`](../../formats/images/README.md) and [`test_crip008_encode.py`](../../tests/formats/images/test_crip008_encode.py) | A successful kind/profile does not prove every kind-3 flag, geometry, predictor, or alpha combination |
| [Photon font runtime](font-runtime.md) | Why were a copied font and registry-only changes insufficient? | [`runtime`](../../runtime/README.md), build checks, and runtime unit tests | CI proves build and guarded logic, not a complete visual pass on every supported game screen |
| [Shared/common images](shared-common-images.md) | Why are 42 image endpoints shared rather than missing translation peers? | Authenticated parent/family evidence, the [1,448/42 route closure](../../evidence/photon-image-routes-v1/README.md), and the [Photon image evidence bundle](../../evidence/photon-images-v6/README.md) | Semantic route authority and runtime replacement transport are separate claims |
| [ICI resize metadata](ici-resize-metadata.md) | Why could a statically decodable resized ICI still lead to a white screen? | Clean/candidate differential, duplicate-size and bitmap checks, plus independent static decoding | The corrected run had zero AGES launches and remains runtime-pending, not a released general ICI writer |
| [Image transport/runtime](image-transport-runtime.md) | Why did correct localized bitmaps blank, tear, recolour, revert or leave English visible? | Locale/parent route census, capacity differential and controlled single-record runtime probes | All 1,490 semantic routes are known; not all have a public production transport or complete visual pass |

## How to read a postmortem

Each record should distinguish four layers:

1. **Symptom** — the exact failure observed, including game/build and runtime route when known.
2. **Competing hypotheses** — plausible explanations before the controlled test.
3. **Discriminating experiment** — what changed, what stayed fixed, and the actual result.
4. **Production rule and boundary** — what the repository now enforces, plus what the experiment did not prove.

Screenshots and visually plausible output are supporting observations, not structural proof. A parser round trip proves the parser/writer contract exercised by that sample; it does not by itself prove AGES runtime acceptance. Conversely, one successful game run does not establish support for every format variant.

For the broader map from public prior work to project-specific findings, see the [research index](../../../docs/research/README.md), [provenance policy](../provenance.md), and [quality gates](../quality.md).
