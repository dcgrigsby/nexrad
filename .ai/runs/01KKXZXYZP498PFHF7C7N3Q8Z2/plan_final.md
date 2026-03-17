# NEXRAD 3D Point Cloud Viewer v1 — Final Implementation Plan

> **Synthesized from Plans A, B, and C.** Plan A provides the definitive gap analysis against existing code; Plan B contributes structural workstream framing; Plan C provides the most detailed IT-scenario specifications and evidence contract detail. All DoD acceptance criteria (AC-1 through AC-5) and integration test scenarios (IT-1 through IT-7) are covered.

---

## 1. Current-State Assessment

The repository already contains a substantial (~85–90% complete) implementation from a prior pipeline run. The table below summarizes what is correct, what needs fixing, and what is missing.

| Component | Location | Status |
|---|---|---|
| **pyproject.toml** | `pyproject.toml` | ✅ Correct — `arm-pyart`, `boto3`, `numpy`, pytest, ruff, hatch, entry points |
| **.envrc** | `.envrc` | ✅ Correct — activates `.venv`, loads `.env.local` |
| **.gitignore** | `.gitignore` | ✅ Correct |
| **Fetch CLI** | `src/nexrad_fetch/cli.py` | ✅ Correct |
| **Fetch core** | `src/nexrad_fetch/fetch.py` | ✅ Correct |
| **Transform CLI** | `src/nexrad_transform/cli.py` | ✅ Correct — needs `--min-dbz` option added |
| **Transform core** | `src/nexrad_transform/transform.py` | ⚠️ Three issues: wrong reader function, DBZ_MIN hard filter, no-data error vs 0-vertex |
| **Color mapping** | `src/nexrad_transform/colors.py` | ⚠️ Non-NWS color table — must be replaced |
| **PLY writer** | `src/nexrad_transform/ply_writer.py` | ✅ Correct (verify binary struct is 15 bytes/vertex) |
| **Viewer HTML** | `viewer/index.html` | ✅ Correct |
| **Viewer JS** | `viewer/src/main.js` | ✅ Correct |
| **Viewer config** | `viewer/package.json`, `viewer/vite.config.js` | ✅ Correct |
| **Validation scripts** | `scripts/validate-{build,fmt,test,artifacts}.sh` | ✅ Correct — test script needs clear-air fetch time fix |
| **Unit tests** | `tests/test_fetch.py`, `tests/test_transform.py` | ⚠️ Missing NWS color verification + synthetic transform test |

---

## 2. Gaps and Required Changes

### G1 — NWS Color Table Mismatch (AC-3.6) **[HIGH]**

`src/nexrad_transform/colors.py` uses non-standard RGB values (e.g., `(100, 235, 242)` for 5–10 dBZ instead of `(0, 150, 255)` per spec). The authoritative table from `docs/specs/NWS_REFLECTIVITY_COLOR_TABLE.md` must replace it entirely.

**Replace `_COLOR_TABLE` with:**
```python
_COLOR_TABLE = [
    (-30, -25, 100, 100, 100),   # Dark Gray
    (-25, -20, 150, 150, 150),   # Light Gray
    (-20, -10,  65, 105, 225),   # Royal Blue
    (-10,   0,   0, 200, 255),   # Cyan
    (  0,   5,  50, 200, 255),   # Light Cyan
    (  5,  10,   0, 150, 255),   # Blue
    ( 10,  15,   0, 200,   0),   # Green
    ( 15,  20, 100, 255,   0),   # Lime Green
    ( 20,  25, 255, 255,   0),   # Yellow
    ( 25,  30, 255, 165,   0),   # Orange
    ( 30,  35, 255, 100,   0),   # Red-Orange
    ( 35,  40, 255,   0,   0),   # Red
    ( 40,  45, 180,   0,   0),   # Dark Red
    ( 45,  50, 255,   0, 255),   # Magenta
    ( 50,  55, 138,  43, 226),   # Violet
    ( 55,  75, 255, 255, 255),   # White
    ( 75, 200, 255, 255, 255),   # Bright White (cap)
]
```

**Files:** `src/nexrad_transform/colors.py`

---

### G2 — DBZ_MIN Hard Filter Violates Spec (AC-3.4, AC-3.7, AC-3.8) **[HIGH]**

`transform.py` applies `refl_flat >= DBZ_MIN` (5.0) after Py-ART masking. The spec states "filter out gates with no reflectivity data" — meaning masked/fill-value gates only. The NWS color table starts at −30 dBZ; the hard 5 dBZ floor discards valid data and does not match spec intent.

**Required changes in `transform.py`:**
1. Remove `DBZ_MIN = 5.0` constant.
2. Change filter from `np.isfinite(refl_flat) & (refl_flat >= DBZ_MIN)` to `np.isfinite(refl_flat)`.
3. Add optional `min_dbz: float | None = None` parameter to `transform()` — if provided, apply as additional filter; otherwise filter masked/NaN only.

**Required change in `cli.py`:**
- Add `--min-dbz` optional CLI argument (default: `None`); pass through to `transform()`.

**Files:** `src/nexrad_transform/transform.py`, `src/nexrad_transform/cli.py`

---

### G3 — Wrong Py-ART Reader Function (AC-3.5) **[MEDIUM]**

`transform.py` uses `pyart.io.read()` (generic reader). The spec and Py-ART API reference specify `pyart.io.read_nexrad_archive()` (NEXRAD-specific reader). While both may work for standard archives, the explicit reader is more robust and matches spec intent.

**Required change:** Replace `pyart.io.read(str(input_path))` with `pyart.io.read_nexrad_archive(str(input_path))`.

**File:** `src/nexrad_transform/transform.py`

---

### G4 — Empty Scan Raises ValueError Instead of Writing 0-Vertex PLY (AC-3.8) **[MEDIUM]**

If all gates are masked or below threshold, `transform()` raises `ValueError`. The DoD says clear-air should produce <10K vertices (implying success with a sparse PLY), not an error. A 0-vertex PLY is valid per the PLY spec.

**Required change:** Instead of raising `ValueError` when `all_x` is empty, write a valid PLY with 0 vertices and return 0.

**File:** `src/nexrad_transform/transform.py`

---

### G5 — Clear-Air Fetch Time Mismatch in validate-test.sh **[LOW]**

`scripts/validate-test.sh` fetches clear-air data at `20240501_050000` (5:00 UTC) but the canonical test case from `docs/specs/NEXRAD_TEST_CASES.md` specifies `~17:30 UTC` (`KLSX_20240501_173000_V06.gz`).

**Required change:** Update the clear-air fetch time to `20240501_173000`.

**File:** `scripts/validate-test.sh`

---

### G6 — Missing NWS Color Table Unit Tests (AC-3.6) **[MEDIUM]**

`tests/test_transform.py` checks colors are different and in-range but does not verify specific NWS dBZ→RGB values against the spec table.

**Required additions to `tests/test_transform.py`:**
```
test_nws_color_specific_values():
    12 dBZ  → (0, 200, 0)      # Green bin
    22 dBZ  → (255, 255, 0)    # Yellow bin
    27 dBZ  → (255, 165, 0)    # Orange bin
    37 dBZ  → (255, 0, 0)      # Red bin
    47 dBZ  → (255, 0, 255)    # Magenta bin
    52 dBZ  → (138, 43, 226)   # Violet bin
    -15 dBZ → (65, 105, 225)   # Royal Blue bin
```

---

### G7 — Missing End-to-End Transform Unit Test **[MEDIUM]**

No unit test exercises the full `transform()` function with a synthetic/mock radar object. Plan A proposes creating a minimal numpy-based synthetic radar via Py-ART test fixtures.

**Required addition:** `test_transform_with_synthetic_data()` — construct minimal radar, run `transform()`, verify output PLY structure.

**File:** `tests/test_transform.py`

---

### G8 — Binary PLY Struct Byte Alignment Verification **[LOW]**

The binary PLY writer uses a numpy structured dtype combining `float32 × 3` (12 bytes) and `uint8 × 3` (3 bytes). NumPy may add padding to 16 bytes/vertex instead of the expected 15. The existing test asserts 15 bytes/vertex; if it passes, no issue. Verify with explicit packed dtype if needed.

**File:** `src/nexrad_transform/ply_writer.py` (verify only — edit only if test fails)

---

## 3. Implementation Parallelization

Work is divided into **three parallel workers** followed by a **merge/integration pass**:

### Worker 1 — `implement_fetch`
**Owns:** Python fetch CLI + environment setup

**Files to create/edit:**
| File | Action |
|---|---|
| `pyproject.toml` | Verify/update: ensure `arm-pyart>=1.18`, `boto3>=1.34`, `numpy>=1.24`, pytest, ruff; console scripts `nexrad-fetch` and `nexrad-transform`; Python ≥3.10 |
| `.envrc` | Verify: activates `.venv`, loads `.env.local` |
| `.gitignore` | Verify: covers `.env.local`, `.venv/`, `__pycache__/`, `node_modules/`, `viewer/dist/`, `.ai/`, `*.gz`, `*.ply` |
| `src/nexrad_fetch/__init__.py` | Verify exists |
| `src/nexrad_fetch/cli.py` | Verify: argparse, `--site`, `--time` / positional datetime, `--output`, `--window`, `--list-only`, `--help` |
| `src/nexrad_fetch/fetch.py` | Verify: unsigned boto3, paginated S3 listing, time-window filtering, closest-scan, download, all error paths |
| `tests/test_fetch.py` | Verify: site validation, scan time parsing, closest-scan logic |

**Acceptance criteria to satisfy:** AC-1.1, AC-1.3, AC-1.4, AC-2.1–AC-2.8

**DoD messages to cover:** MSG-1, MSG-2, MSG-3, MSG-4, MSG-5

---

### Worker 2 — `implement_transform`
**Owns:** Python transform CLI

**Files to create/edit:**
| File | Action | Gap |
|---|---|---|
| `src/nexrad_transform/colors.py` | **Replace** `_COLOR_TABLE` with exact NWS spec table (17 entries, −30 to 75+ dBZ); update `_THRESHOLDS` and `_COLORS` derivation | G1 |
| `src/nexrad_transform/transform.py` | **Edit**: switch to `pyart.io.read_nexrad_archive()`; remove `DBZ_MIN`; change filter to `np.isfinite()` only; add optional `min_dbz` param; write 0-vertex PLY instead of raising on empty | G2, G3, G4 |
| `src/nexrad_transform/cli.py` | **Edit**: add `--min-dbz` optional float arg (default `None`); pass to `transform()` | G2 |
| `src/nexrad_transform/ply_writer.py` | **Verify**: binary dtype is 15 bytes/vertex (no padding); edit only if test fails | G8 |
| `src/nexrad_transform/__init__.py` | Verify exists |
| `tests/test_transform.py` | **Add**: `test_nws_color_specific_values()` spot-checking 7+ dBZ→RGB pairs; `test_transform_with_synthetic_data()` end-to-end with mock radar | G6, G7 |

**Acceptance criteria to satisfy:** AC-3.1–AC-3.13

**DoD messages to cover:** MSG-6, MSG-7, MSG-8

---

### Worker 3 — `implement_viewer`
**Owns:** JS Three.js viewer + viewer/package.json

**Files to create/edit:**
| File | Action |
|---|---|
| `viewer/package.json` | Verify: `three` dependency, `vite` dev dep, `dev`/`build`/`preview` scripts |
| `viewer/vite.config.js` | Verify |
| `viewer/index.html` | Verify: `<input type="file" accept=".ply">`, full-viewport canvas, no chrome |
| `viewer/src/main.js` | Verify: `PLYLoader`, `OrbitControls`, file picker + `?file=` URL param, `THREE.Points` with `vertexColors: true`, `fitCameraToGeometry`, responsive resize, dark background, loading/error status text |

**Acceptance criteria to satisfy:** AC-1.2, AC-4.1–AC-4.6

**DoD messages to cover:** MSG-9

---

### Worker 4 — `merge_implementation`
**Owns:** Integration, validation scripts, conflict resolution, evidence contract

**Responsibilities:**
1. Merge commits from workers 1–3; resolve any conflicts (primarily in `tests/` and `scripts/`).
2. Verify `scripts/validate-build.sh` runs: `uv sync`, imports `boto3` and `pyart`, `nexrad-fetch --help`, `nexrad-transform --help`, `cd viewer && npm install && npm run build`.
3. Verify `scripts/validate-fmt.sh`: `ruff check` passes on all Python files.
4. Fix `scripts/validate-test.sh`: update clear-air fetch time to `20240501_173000` (G5).
5. Verify `scripts/validate-artifacts.sh`: evidence manifest covers all IT-1 through IT-7.
6. Verify evidence root path is `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/` (canonical DoD path).
7. Run `uv run pytest tests/ -v` — all unit tests pass.
8. Remove any committed files under `viewer/dist/` from git tracking (`git rm -r --cached viewer/dist/` if needed).
9. Confirm binary PLY struct test (15 bytes/vertex) passes.

---

## 4. Detailed File-Level Change Manifest

| File | Worker | Action | Gaps |
|---|---|---|---|
| `src/nexrad_transform/colors.py` | 2 | Replace `_COLOR_TABLE` with NWS spec table | G1 |
| `src/nexrad_transform/transform.py` | 2 | Switch reader; remove DBZ_MIN; handle empty gracefully | G2, G3, G4 |
| `src/nexrad_transform/cli.py` | 2 | Add `--min-dbz` argument | G2 |
| `tests/test_transform.py` | 2 | Add NWS color spot checks + synthetic transform test | G6, G7 |
| `scripts/validate-test.sh` | 4 | Fix clear-air fetch time `050000` → `173000` | G5 |
| `src/nexrad_transform/ply_writer.py` | 2 | Verify only; fix dtype if needed | G8 |
| All other existing files | — | Verify correctness; no changes expected | — |

---

## 5. Dependency Order

```
Worker 1 (implement_fetch)     ─┐
Worker 2 (implement_transform)  ├─→ merge_implementation → validation_pass
Worker 3 (implement_viewer)    ─┘
```

Workers 1–3 are fully independent. `merge_implementation` depends on all three completing.

---

## 6. Acceptance Criteria Coverage Matrix

| AC | Worker | Status After Plan |
|---|---|---|
| AC-1.1 | 1 | ✅ pyproject.toml + .envrc + uv sync |
| AC-1.2 | 3 | ✅ viewer/package.json + npm install |
| AC-1.3 | 1 | ✅ pyproject.toml with all deps |
| AC-1.4 | 1 | ✅ .envrc activates venv |
| AC-2.1 | 1 | ✅ CLI accepts site + datetime args |
| AC-2.2 | 1 | ✅ Lists scans near requested time |
| AC-2.3 | 1 | ✅ Downloads to specified path |
| AC-2.4 | 1 | ✅ Downloads valid gzip |
| AC-2.5 | 1 | ✅ Exit 0/non-zero |
| AC-2.6 | 1 | ✅ Error for invalid site |
| AC-2.7 | 1 | ✅ Error for no scans |
| AC-2.8 | 1 | ✅ --help works |
| AC-3.1 | 2 | ✅ CLI accepts input/output paths |
| AC-3.2 | 2 | ✅ PLY header correct |
| AC-3.3 | 2 | ✅ All sweeps iterated |
| AC-3.4 | 2 | ✅ Filter masked/NaN only (G2 fix) |
| AC-3.5 | 2 | ✅ read_nexrad_archive + antenna_vectors_to_cartesian (G3 fix) |
| AC-3.6 | 2 | ✅ NWS color table replacement (G1 fix) |
| AC-3.7 | 2 | ✅ >100K vertices for active storm |
| AC-3.8 | 2 | ✅ <10K vertices for clear-air (G4 fix: 0-vertex PLY succeeds) |
| AC-3.9 | 2 | ✅ Exit codes correct |
| AC-3.10 | 2 | ✅ Error for invalid file |
| AC-3.11 | 2 | ✅ --help works |
| AC-3.12 | 2 | ✅ Reports vertex count |
| AC-3.13 | 2 | ✅ edges=False gives gate centers |
| AC-4.1 | 3 | ✅ Viewer serves page |
| AC-4.2 | 3 | ✅ File picker + ?file= URL |
| AC-4.3 | 3 | ✅ vertexColors: true |
| AC-4.4 | 3 | ✅ OrbitControls left-drag |
| AC-4.5 | 3 | ✅ OrbitControls scroll zoom |
| AC-4.6 | 3 | ✅ OrbitControls right-drag pan |
| AC-5.1 | 4 | ✅ End-to-end via IT-5 |
| AC-5.2 | 4 | ✅ Visual layered tilts |

---

## 7. Integration Test Scenario Coverage

| Scenario | Covered by | Evidence location |
|---|---|---|
| IT-1: Fetch active storm (KTLX, 2013-05-20T20:00Z) | Worker 1 + merge_implementation | `IT-1/fetch_stdout.log`, `IT-1/fetch_exit_code.txt`, `IT-1/downloaded_file_info.json` |
| IT-2: Transform storm → PLY, validate header/vertex count/coords/colors/tilts | Worker 2 + merge_implementation | `IT-2/transform_stdout.log`, `IT-2/transform_exit_code.txt`, `IT-2/ply_header.txt`, `IT-2/ply_validation.json` |
| IT-3: Transform clear-air → sparse PLY (<10K vertices) | Worker 2 + merge_implementation | `IT-3/transform_stdout.log`, `IT-3/transform_exit_code.txt`, `IT-3/ply_validation.json` |
| IT-4: Viewer renders PLY in browser, orbit/zoom/pan | Worker 3 + merge_implementation | `IT-4/viewer_loaded.png`, `IT-4/ply_rendered.png`, `IT-4/orbit_rotated.png`, `IT-4/viewer_console.log` |
| IT-5: End-to-end pipeline from scratch | All workers + merge_implementation | `IT-5/fetch_stdout.log`, `IT-5/transform_stdout.log`, `IT-5/pipeline_rendered.png`, `IT-5/pipeline_summary.json` |
| IT-6: Fetch error handling + --help | Worker 1 + merge_implementation | `IT-6/help_stdout.log`, `IT-6/invalid_site_stdout.log`, `IT-6/invalid_site_exit_code.txt`, `IT-6/no_scans_stdout.log`, `IT-6/no_scans_exit_code.txt` |
| IT-7: Transform error handling + --help | Worker 2 + merge_implementation | `IT-7/help_stdout.log`, `IT-7/invalid_file_stdout.log`, `IT-7/invalid_file_exit_code.txt`, `IT-7/bad_format_stdout.log`, `IT-7/bad_format_exit_code.txt` |

**Evidence root:** `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/`
**Manifest:** `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/manifest.json`

---

## 8. Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Removing DBZ_MIN causes clear-air PLY to exceed 10K points | Low | Py-ART masks truly empty gates; clear-air has <500 real returns. If exceeded, add `--min-dbz 5` default. |
| `read_nexrad_archive()` behaves differently from `read()` on edge cases | Low | read_nexrad_archive is recommended API; test files are standard NEXRAD archives |
| S3 network access unavailable during validation | Medium | validate-test.sh already has pyart fixture fallbacks for both storm and clear-air scenarios |
| Binary PLY struct has padding (16 bytes vs 15) | Low | Existing test asserts 15 bytes/vertex; if it passes, no issue |
| NWS color table change breaks existing IT-2 color validation | Low | Validation script checks valid RGB ranges, not specific values; new unit tests verify exact NWS values |
| Py-ART field name variation across different NEXRAD files | Low | `_get_reflectivity_field()` already has multi-alias fallback |
| Large memory usage during storm transform (18M gates total) | Medium | Current sweep-by-sweep processing with numpy masking handles this; no whole-volume intermediate needed |

---

## 9. Done Criteria for This Implementation

The implementation is complete when ALL of the following hold:

1. `direnv allow && uv sync` produces working Python environment with pyart and boto3
2. `cd viewer && npm install && npm run build` succeeds
3. `nexrad-fetch --help` and `nexrad-transform --help` both exit 0 with usage text
4. `uv run pytest tests/ -v` passes all tests including new NWS color spot-checks
5. `scripts/validate-build.sh` exits 0
6. `scripts/validate-fmt.sh` exits 0 (ruff clean)
7. `scripts/validate-test.sh` runs IT-1 through IT-7 and produces evidence artifacts
8. `scripts/validate-artifacts.sh` exits 0 with complete manifest.json
9. Evidence for IT-1 through IT-7 exists under `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/`
10. NWS color table in `colors.py` exactly matches `docs/specs/NWS_REFLECTIVITY_COLOR_TABLE.md`
11. `transform.py` uses `pyart.io.read_nexrad_archive()` and does not apply DBZ_MIN
12. Storm scan (KTLX, 2013-05-20T20:00Z) produces >100K vertices; clear-air (KLSX, 2024-05-01T17:30Z) produces <10K vertices
