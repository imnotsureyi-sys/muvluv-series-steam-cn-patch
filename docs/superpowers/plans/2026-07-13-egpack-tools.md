# EGPACK Exact Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build public, field-aware EGPACK extraction, repacking, and verification tools that preserve every non-target byte and replace the current heuristic JP/EN scripts.

**Architecture:** `egpack_codec.py` owns binary parsing and exact byte replacement. Three thin CLIs export a long-form manifest, apply guarded changes, and verify patched files by reproducing the authorized byte transformation. Tests generate copyright-free EGPACK fixtures at runtime; local integration checks use TDA00-03 and ATE files without committing them.

**Tech Stack:** Python 3.10+ standard library, `unittest`, CSV with UTF-8 BOM, GitHub Actions on Windows and Linux.

## Global Constraints

- Do not modify TDA00-03 subtitle bodies, public chapter CSVs, release payloads, or existing Releases.
- Do not use English fallback, old Chinese fallback, or fuzzy matching.
- Never overwrite source EGPACK files.
- Preserve source control codes in extraction and every unmodified byte; reject manual newline markers in Chinese replacement text.
- Do not commit game resources, real manifests, private paths, or legacy script archives.
- Stage only explicit files; never run `git add -A`.

---

### Task 1: Copyright-Free Fixture and Exact Binary Parser

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/egpack/__init__.py`
- Create: `tests/egpack/fixtures.py`
- Create: `tests/egpack/test_codec.py`
- Create: `tools/egpack/egpack_codec.py`

**Interfaces:**
- Produces: `parse_egpack_bytes(data: bytes, source: str = "<memory>") -> EgpackDocument`
- Produces: `parse_egpack(path: Path) -> EgpackDocument`
- Produces: `classify_resource(path: str, text_id: str) -> str`
- Produces: `extract_control_codes(text: str) -> tuple[str, ...]`
- Produces: `has_manual_newline(text: str) -> bool`
- Produces: `is_control_only(text: str) -> bool`

- [ ] **Step 1: Add a synthetic EGPACK builder**

Implement `tests/egpack/fixtures.py` with the real CRC32 field keys and fixed TDA field order:

```python
SLOT_ORDER = (
    "zh_hans", "pt", "pt_br", "de", "jp",
    "zh_hant", "es", "it", "id", "fr", "en",
)

def field(slot: str, value: str) -> bytes:
    key = (zlib.crc32(slot.encode("ascii")) & 0xFFFFFFFF).to_bytes(4, "little")
    return b"\x87" + key + b"\xa6" + value.encode("utf-8") + b"\0"

def build_egpack(records: list[dict[str, str]]) -> bytes:
    body = b"".join(field(slot, record.get(slot, "")) for record in records for slot in SLOT_ORDER)
    header = b"EPK\0\x03\x02\x40\0\0\0\0\0" + b"\0de\0en\0es\0fr\0id\0it\0jp\0pt\0pt_br\0zh_hans\0zh_hant\0"
    data = header + body
    return data[:8] + len(data).to_bytes(4, "little") + data[12:]
```

- [ ] **Step 2: Write parser tests before production code**

Add tests proving:

```python
def test_parse_keeps_jp_en_and_control_only_records_separate():
    data = build_egpack([
        {"id": "game_t00000", "jp": "「日本語」\\p", "en": "English"},
        {"id": "game_t00001", "jp": "\\f", "en": "\\f"},
        {"id": "game_t00002", "jp": "次の日本語", "en": ""},
    ])
    doc = parse_egpack_bytes(data)
    assert doc.records[0].slots["en"].text == "English"
    assert doc.records[1].slots["jp"].text == "\\f"
    assert doc.records[2].slots["en"].text == ""

def test_classifies_all_known_resource_kinds():
    assert classify_resource("scene.egpack", "game_t00000") == "scene"
    assert classify_resource("scene.egpack", "game_t00000_ruby") == "ruby"
    assert classify_resource("__speakers__.egpack", "game_s00000") == "speaker"
    assert classify_resource("__staffroll__.egpack", "staff90000") == "staffroll"
```

Also test bad magic, declared-size mismatch, invalid UTF-8, missing field, duplicate field, and an unknown but structurally valid ID.

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
python -m unittest tests.egpack.test_codec -v
```

Expected: import failure because `tools.egpack.egpack_codec` does not exist.

- [ ] **Step 4: Implement the minimal exact parser**

Implement immutable data classes:

```python
@dataclass(frozen=True)
class EgpackField:
    slot: str
    crc32_hex: str
    field_offset: int
    value_offset: int
    value_length: int
    text: str

@dataclass(frozen=True)
class EgpackRecord:
    index: int
    text_id: str
    id_offset: int
    slots: dict[str, EgpackField]

@dataclass(frozen=True)
class EgpackDocument:
    source: str
    data: bytes
    declared_size: int
    records: tuple[EgpackRecord, ...]
```

Scan only exact `0x87 + CRC32 + 0xA6 + NUL-terminated UTF-8` fields. Validate every 11-field chunk against `SLOT_ORDER`, identify the `id` field, and expose only the 10 language slots in `record.slots`.

- [ ] **Step 5: Run parser tests and verify GREEN**

Run:

```powershell
python -m unittest tests.egpack.test_codec -v
```

Expected: all parser tests pass.

- [ ] **Step 6: Commit parser deliverable**

```powershell
git add -- tests/__init__.py tests/egpack/__init__.py tests/egpack/fixtures.py tests/egpack/test_codec.py tools/egpack/egpack_codec.py
git commit -m "feat: parse EGPACK language slots exactly"
```

### Task 2: Long-Form Manifest Export

**Files:**
- Create: `tests/egpack/test_manifest.py`
- Create: `tools/egpack/extract_egpack_manifest.py`

**Interfaces:**
- Consumes: `parse_egpack()` and control helpers from Task 1.
- Produces: `manifest_rows(input_path: Path) -> Iterator[dict[str, str | int | bool]]`
- Produces CLI: `python tools/egpack/extract_egpack_manifest.py INPUT --output manifest.csv`

- [ ] **Step 1: Write manifest tests**

Test that two records create exactly 20 rows, empty slots remain present, paths use `/`, offsets point at the real value bytes, hashes match the value bytes, `\f` is marked `is_control_only=true` rather than empty, and manual newlines are explicitly flagged.

- [ ] **Step 2: Run tests and verify RED**

```powershell
python -m unittest tests.egpack.test_manifest -v
```

Expected: import failure because the manifest module does not exist.

- [ ] **Step 3: Implement manifest generation and CLI**

Use the exact approved columns and write with:

```python
with output.open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=MANIFEST_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
```

For a directory, recursively process sorted `*.egpack` files. For a single file, use its filename as `relative_path`.

- [ ] **Step 4: Run manifest and full tests**

```powershell
python -m unittest tests.egpack.test_manifest -v
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit manifest deliverable**

```powershell
git add -- tests/egpack/test_manifest.py tools/egpack/extract_egpack_manifest.py
git commit -m "feat: export complete EGPACK slot manifests"
```

### Task 3: Guarded Exact Repacking

**Files:**
- Create: `tests/egpack/test_repack.py`
- Create: `tools/egpack/repack_egpack.py`
- Modify: `tools/egpack/egpack_codec.py`

**Interfaces:**
- Produces: `EgpackChange(relative_path, text_id, slot, expected_text, replacement_text)`
- Produces: `apply_changes(data: bytes, changes: Sequence[EgpackChange], source: str) -> bytes`
- Produces CLI: `python tools/egpack/repack_egpack.py INPUT --changes changes.csv --output-dir OUTPUT`

- [ ] **Step 1: Write failing writeback tests**

Cover longer Chinese, shorter Chinese, an intentional empty replacement, multiple changes in one file, manual-newline rejection, duplicate target rejection, expected-text mismatch, unknown slot, missing ID, and input/output overlap.

The core byte assertion is:

```python
patched = apply_changes(original, [change], "fixture.egpack")
assert len(patched) == int.from_bytes(patched[8:12], "little")
assert parse_egpack_bytes(patched).records[0].slots["jp"].text == "中文"
assert parse_egpack_bytes(patched).records[0].slots["en"].text == "English"
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
python -m unittest tests.egpack.test_repack -v
```

Expected: import failure for `apply_changes` or the repack module.

- [ ] **Step 3: Implement reverse-offset replacement**

Reparse and resolve every `(id, slot)` before changing bytes. Reject duplicates, then apply `(start, end, replacement_bytes)` operations in descending `start` order. Finally update bytes `8:12` with the rebuilt length and parse the rebuilt file again.

- [ ] **Step 4: Implement changes CSV and safe output CLI**

Require exactly:

```text
relative_path,id,slot,expected_text,replacement_text
```

Only write targeted EGPACK files. Reject existing output files and reject any resolved output path equal to a source path.

- [ ] **Step 5: Run repack and full tests**

```powershell
python -m unittest tests.egpack.test_repack -v
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit repack deliverable**

```powershell
git add -- tests/egpack/test_repack.py tools/egpack/egpack_codec.py tools/egpack/repack_egpack.py
git commit -m "feat: repack guarded EGPACK slot changes"
```

### Task 4: Independent Verification

**Files:**
- Create: `tests/egpack/test_verify.py`
- Create: `tools/egpack/verify_egpack.py`

**Interfaces:**
- Consumes: change parsing and `apply_changes()` from Task 3.
- Produces: `verify_patched_bytes(original: bytes, patched: bytes, changes: Sequence[EgpackChange], source: str) -> None`
- Produces CLI: `python tools/egpack/verify_egpack.py ORIGINAL PATCHED --changes changes.csv`

- [ ] **Step 1: Write failing verification tests**

Test valid authorized output, unauthorized EN modification, missing patched file, changed ID order, bad declared length, and byte changes outside the target value.

- [ ] **Step 2: Run tests and verify RED**

```powershell
python -m unittest tests.egpack.test_verify -v
```

Expected: import failure because the verifier does not exist.

- [ ] **Step 3: Implement deterministic verification**

Compute the only acceptable patched bytes by calling `apply_changes(original, changes)`, then require exact byte equality with the supplied patched file. Parse both documents for clearer diagnostics before raising `EgpackVerificationError`.

- [ ] **Step 4: Run verifier and full tests**

```powershell
python -m unittest tests.egpack.test_verify -v
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit verifier deliverable**

```powershell
git add -- tests/egpack/test_verify.py tools/egpack/verify_egpack.py
git commit -m "feat: verify exact EGPACK patch boundaries"
```

### Task 5: Local Legacy Archive and Public Directory Cleanup

**Files:**
- Local-only create: `C:/Users/Administrator/Documents/MuvLuvSeries_archive_20260623/legacy_tools/egpack_heuristic_20260713/README.md`
- Local-only copy: old `extract_egpack_text.py`
- Local-only copy: old `repack_egpack_with_csv.py`
- Move: `tools/egpack/diagnose_fpd_keys.py` -> `tools/fpd/diagnose_fpd_keys.py`
- Move: `tools/egpack/extract_fpd_filtered.py` -> `tools/fpd/extract_fpd_filtered.py`
- Move: `tools/egpack/probe_fpd.py` -> `tools/fpd/probe_fpd.py`
- Delete from public tree: `tools/egpack/extract_egpack_text.py`
- Delete from public tree: `tools/egpack/repack_egpack_with_csv.py`
- Create: `tools/fpd/README.md`
- Modify: `tools/README.md`

**Interfaces:**
- Preserves existing FPD command behavior under the new `tools/fpd/` path.

- [ ] **Step 1: Copy legacy scripts outside the repository**

Use native PowerShell `Copy-Item -LiteralPath` and record source commit `e59cbce` plus SHA-256 hashes in the local-only README.

- [ ] **Step 2: Verify the archive before deleting public copies**

Run `Get-FileHash` on source and archive copies and require matching SHA-256 values.

- [ ] **Step 3: Move FPD scripts and fix relative references**

Use `apply_patch` for import/path edits after moving with `Move-Item`. Smoke-test each `--help` command.

- [ ] **Step 4: Remove only the two heuristic scripts**

Delete them with an explicit patch after archive verification. Confirm `git status` shows no unrelated deletion.

- [ ] **Step 5: Commit cleanup deliverable**

```powershell
git add -- tools/README.md tools/fpd tools/egpack/extract_egpack_text.py tools/egpack/repack_egpack_with_csv.py tools/egpack/diagnose_fpd_keys.py tools/egpack/extract_fpd_filtered.py tools/egpack/probe_fpd.py
git commit -m "refactor: separate FPD and exact EGPACK tools"
```

### Task 6: Chinese Documentation and CI

**Files:**
- Rewrite: `tools/egpack/README.md`
- Create: `tools/egpack/EGPACK_FORMAT.md`
- Create: `.github/workflows/egpack-tools.yml`

**Interfaces:**
- Documents exact CLI commands, CSV schemas, safety guarantees, and known compatibility limits.

- [ ] **Step 1: Write Chinese usage documentation**

Include commands for manifest extraction, changes CSV, repacking, and verification. State that TDA00-03 currently write Chinese to the JP slot and that `uistring.epk`/WebP are outside this tool.

- [ ] **Step 2: Document the verified binary schema**

Include magic, declared-size offset, CRC32 table, field marker shape, exact-vs-heuristic distinction, control-only records, Chinese auto-wrapping rules, and the fact that the working ATE reference uses variants that are diagnostic-only in version 1.

- [ ] **Step 3: Add cross-platform CI**

Use a Windows/Linux matrix and run:

```yaml
- run: python -m unittest discover -s tests -p "test_*.py" -v
```

No external dependencies or downloaded game data are allowed.

- [ ] **Step 4: Run every documented `--help` and synthetic example**

Require exit code 0 and confirm generated CSV starts with a UTF-8 BOM and has 10 rows per record.

- [ ] **Step 5: Commit docs and CI**

```powershell
git add -- tools/egpack/README.md tools/egpack/EGPACK_FORMAT.md .github/workflows/egpack-tools.yml
git commit -m "docs: publish exact EGPACK workflow"
```

### Task 7: Real-Resource Integration, Final Review, and Push

**Files:**
- No committed real-resource outputs.
- Modify implementation or tests only if a verified defect is found.

**Interfaces:**
- Uses the four original localized EGPACK directories and latest patch packages from the approved project baseline.

- [ ] **Step 1: Run full synthetic verification**

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python -m compileall -q tools tests
```

Expected: all tests pass and compileall exits 0.

- [ ] **Step 2: Extract TDA00-03 manifests to a temporary local-only directory**

Count unique IDs by classification and require exactly:

```text
TDA00 scene=3713 ruby=75 speaker=21 staffroll=229
TDA01 scene=8565 ruby=40 speaker=82 staffroll=257
TDA02 scene=6310 ruby=17 speaker=111 staffroll=280
TDA03 scene=6913 ruby=24 speaker=133 staffroll=232
```

Also require 10 manifest rows per record and exact retention of TDA02's 41 and TDA03's 3 `\f` JP slots.

- [ ] **Step 3: Probe latest patch EGPACKs and ATE**

Confirm TDA00-03 parse successfully. For the working ATE V2 reference, record deterministic differences in declared length, added keys, duplicate fields, and reordered fields; do not weaken TDA validation to force a shared layout and do not describe unsupported variants as an invalid patch.

- [ ] **Step 4: Exercise a local one-line copy-only patch**

Patch one disposable copied JP slot, verify it, then compare all non-target fields. Never modify the source package.

- [ ] **Step 5: Review repository scope and dirty files**

Run:

```powershell
git status --short
git diff --check
git diff --stat origin/main...HEAD
```

Confirm glossary and chapter CSV modifications remain unstaged and unchanged by this work.

- [ ] **Step 6: Sync and push main**

Fetch/pull with `--ff-only` when network is available, resolve only public documentation conflicts without touching user CSV changes, rerun the full test suite, then:

```powershell
git push origin main
```

Expected: GitHub `main` contains the design, plan, new tools, tests, docs, FPD directory split, and CI only.
