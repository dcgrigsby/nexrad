# Final Implementation Plan — NEXRAD 3D Point Cloud Viewer v1

## Synthesis Notes

This plan consolidates Plan A, Plan B, and Plan C into a single best-of-breed implementation plan.

- **Plan A** (claude-opus-4.6): Most detailed — performed a thorough current-state assessment, identified all critical bugs in the existing codebase (wrong S3 bucket, wrong color table, too-high DBZ threshold, fixture fallback in tests), and provided a step-by-step fix list with AC traceability.
- **Plan B** (gpt-5.3-codex): Clean structure — good coverage of all components and clear milestone sequencing; less specific about existing bugs but well-organized.
- **Plan C** (gpt-5.4): Best evidence/validation design — strongest specification of the evidence contract, PLY binary-vs-ASCII recommendation, and per-scenario implementation notes.

**Conflicts resolved:**
- PLY format: Plan A and B say ASCII initially; Plan C recommends binary for large datasets. **Decision:** Default to `binary_little_endian` (per PLY spec recommendation for >1M points), but support ASCII mode via `--ascii` flag. The transform worker owns this decision.
- Validation scripts: Plan B proposes separate per-IT scripts; Plan C proposes Python scripts; Plan A references existing `scripts/validate-test.sh`. **Decision:** Keep the existing `scripts/validate-*.sh` shell scripts structure (already partially implemented) and fix/extend them rather than rewriting in Python.
- Clear-air test time: Plan A identified that existing scripts use `20240501_050000` but DoD specifies `~17:30 UTC`. **Decision:** Fix to `20240501_173000` (Plan A Step 2.2).

---

## Current State Assessment

The codebase already has substantial implementation. The parallel workers MUST start by reading the existing files before writing anything.

### Existing Files

| Component | Location | Status |
|-----------|----------|--------|
| Python project | `pyproject.toml` | ✅ Exists |
| Environment | `.envrc`, `.gitignore` | ✅ Exists |
| Fetch CLI | `src/nexrad_fetch/cli.py`, `fetch.py`, `__init__.py` | ⚠️ Bug: wrong S3 bucket |
| Transform CLI | `src/nexrad_transform/cli.py`, `transform.py`, `colors.py`, `ply_writer.py` | ⚠️ Bug: wrong color table, DBZ threshold too high |
| Viewer | `viewer/index.html`, `viewer/src/main.js`, `viewer/package.json`, `viewer/vite.config.js` | ✅ Complete |
| Viewer build | `viewer/dist/` | ✅ Pre-built |
| Validation scripts | `scripts/validate-{build,fmt,test,artifacts}.sh` | ⚠️ Fixture fallback in test script; wrong clear-air time |

### Critical Bugs to Fix (blocks all testing)

1. **CRITICAL — Wrong S3 bucket** (`src/nexrad_fetch/fetch.py`): `BUCKET = "noaa-nexrad-level2"` must be `"unidata-nexrad-level2"`. Also fix help text in `src/nexrad_fetch/cli.py`.
2. **CRITICAL — Wrong NWS color table** (`src/nexrad_transform/colors.py`): Replace with canonical NWS RGB mapping.
3. **CRITICAL — DBZ_MIN threshold too high** (`src/nexrad_transform/transform.py`): `DBZ_MIN = 5.0` → `DBZ_MIN = -30.0`. Gates at -30 to 5 dBZ have defined NWS colors and must not be filtered.
4. **MODERATE — Fixture fallback in validate-test.sh**: Remove pyart fixture fallback blocks; if S3 fails, test must report FAIL.
5. **MODERATE — Wrong clear-air test time**: `20240501_050000` → `20240501_173000`.

---

## Parallel Worker Assignments

### Worker 1: `implement_fetch`
**Scope:** Python fetch CLI + environment setup

**Files to own:**
- `src/nexrad_fetch/fetch.py`
- `src/nexrad_fetch/cli.py`
- `src/nexrad_fetch/__init__.py`
- `pyproject.toml`
- `.envrc`
- `.gitignore`
- `tests/__init__.py`
- `tests/test_fetch.py`

**Tasks (in order):**

#### F-1: Fix S3 bucket name
- File: `src/nexrad_fetch/fetch.py`
- Change: `BUCKET = "noaa-nexrad-level2"` → `BUCKET = "unidata-nexrad-level2"`
- Also fix CLI help text in `src/nexrad_fetch/cli.py` that references the old bucket name
- AC: AC-2.2

#### F-2: Verify/improve input validation
- Confirm `validate_site()` rejects codes that are not 4 uppercase letters
- Ensure `ZZZZ`-style codes produce a clear "invalid site code" error (MSG-4) at the S3 listing step if the listing returns zero results AND the site doesn't match a known-valid prefix (K, P, T for CONUS/Pacific/territories)
- AC: AC-2.6

#### F-3: Support ISO 8601 datetime input
- The parse_datetime function must accept both `YYYYMMDD_HHMMSS` and `YYYY-MM-DDTHH:MMZ` / `YYYY-MM-DDTHH:MM:SSZ` formats
- The DoD integration tests use `2013-05-20T20:00Z` style
- AC: AC-2.1

#### F-4: Verify error handling
- Invalid site → non-zero exit + MSG-4
- No scans found → non-zero exit + MSG-5
- S3 transport failure → non-zero exit, no silent fallback
- Download success → exit 0, MSG-2 (scan listing) + MSG-3 (success path + size)
- AC: AC-2.5, AC-2.6, AC-2.7, AC-2.9

#### F-5: Write unit tests for fetch
- `tests/test_fetch.py`:
  - `test_validate_site_valid`: `validate_site("KTLX")` passes
  - `test_validate_site_invalid`: `validate_site("zz")` raises
  - `test_parse_datetime_compact`: parses `20130520_200000`
  - `test_parse_datetime_iso`: parses `2013-05-20T20:00Z`
  - `test_find_closest_scan`: returns time-nearest scan from a mock list
  - Mock S3 responses for listing (do not make real network calls in unit tests)
- AC: AC-2.1, AC-2.5, AC-2.6

#### F-6: Verify pyproject.toml
- Confirm entry points are defined: `nexrad-fetch = nexrad_fetch.cli:main`
- Confirm deps include: `boto3`, `arm-pyart`, `numpy`, `pytest`
- AC: AC-1.3

#### F-7: Verify .envrc
- Confirm `.envrc` activates the uv venv and loads `.env.local` if present
- AC: AC-1.4

**AC coverage:** AC-1.3, AC-1.4, AC-2.1–AC-2.9

---

### Worker 2: `implement_transform`
**Scope:** Python transform CLI

**Files to own:**
- `src/nexrad_transform/transform.py`
- `src/nexrad_transform/colors.py`
- `src/nexrad_transform/ply_writer.py`
- `src/nexrad_transform/cli.py`
- `src/nexrad_transform/__init__.py`
- `tests/test_colors.py`
- `tests/test_ply_writer.py`
- `tests/test_transform.py`

**Tasks (in order):**

#### T-1: Fix NWS color table
- File: `src/nexrad_transform/colors.py`
- Replace entire `_COLOR_TABLE` with the canonical NWS mapping:

```python
# Format: (dbz_min, dbz_max, r, g, b)
_COLOR_TABLE = [
    (-30, -25, 100, 100, 100),   # Dark Gray
    (-25, -20, 150, 150, 150),   # Light Gray
    (-20, -10,  65, 105, 225),   # Light Blue (Royal Blue)
    (-10,   0,   0, 200, 255),   # Cyan
    (  0,   5,  50, 200, 255),   # Light Cyan
    (  5,  10,   0, 150, 255),   # Blue
    ( 10,  15,   0, 200,   0),   # Green
    ( 15,  20, 100, 255,   0),   # Lime Green
    ( 20,  25, 255, 255,   0),   # Yellow
    ( 25,  30, 255, 165,   0),   # Orange
    ( 30,  35, 255, 100,   0),   # Red Orange
    ( 35,  40, 255,   0,   0),   # Red
    ( 40,  45, 180,   0,   0),   # Dark Red
    ( 45,  50, 255,   0, 255),   # Magenta
    ( 50,  55, 138,  43, 226),   # Violet
    ( 55,  60, 255, 255, 255),   # White
    ( 60, 200, 255, 255, 255),   # Bright White (60+ dBZ)
]
```

- Gates with dBZ < -30 (no-data/background) must be **filtered out entirely**, not colored
- Use step/threshold (nearest-neighbor) lookup — no interpolation
- AC: AC-3.6

#### T-2: Lower DBZ_MIN threshold
- File: `src/nexrad_transform/transform.py`
- Change: `DBZ_MIN = 5.0` → `DBZ_MIN = -30.0`
- Gates below -30 dBZ are background/no-data (raw value 0 or 1 in Level II); filter those out
- Gates from -30 to 5 dBZ have legitimate NWS color mappings and must be kept
- This is required for clear-air scans (weak returns at -30 to 0 dBZ) to appear correctly
- AC: AC-3.4, AC-3.7, AC-3.8

#### T-3: Verify gate center placement
- Confirm transform uses gate center coordinates, not gate edge
- Py-ART's `get_gate_x_y_z` uses gate center range (mid-range bin); verify this is what's being used
- If custom geometry code exists, ensure `range = radar.range['data']` + indexing gives gate centers
- AC: AC-3.13

#### T-4: Verify all-sweeps processing
- Confirm `range(radar.nsweeps)` or equivalent iterates all elevation tilts
- Do not skip any sweep
- AC: AC-3.3

#### T-5: Use Py-ART coordinate transform
- Confirm `antenna_vectors_to_cartesian` (or `get_gate_x_y_z`) is used for Cartesian conversion
- This implements the 4/3 earth radius refraction model
- Origin (0,0,0) at radar antenna
- AC: AC-3.5

#### T-6: Handle empty output gracefully
- If all gates are masked/filtered (possible for very clear-air scans), write a valid PLY file with 0 vertices and exit 0
- Do not raise ValueError on empty arrays
- Print "Wrote 0 vertices" on success
- AC: AC-3.8, AC-3.9, AC-3.12

#### T-7: PLY format — default binary, support ASCII flag
- Default output format: `binary_little_endian` (15 bytes/vertex; recommended for >500K points)
- Add `--ascii` flag to write ASCII PLY for debugging
- PLY header must declare exactly:
  ```
  ply
  format binary_little_endian 1.0
  element vertex <count>
  property float x
  property float y
  property float z
  property uchar red
  property uchar green
  property uchar blue
  end_header
  ```
- AC: AC-3.2

#### T-8: Vertex count reporting
- Print vertex count to stdout on success (e.g., "Wrote 847293 vertices to output.ply")
- AC: AC-3.12

#### T-9: Write unit tests for transform
- `tests/test_colors.py`:
  - `test_color_at_each_boundary`: dBZ at each range boundary maps to expected RGB
  - `test_color_above_60`: values >60 dBZ map to white (255, 255, 255)
  - `test_no_color_below_minus30`: values below -30 dBZ should trigger filtering (test boundary behavior)
- `tests/test_ply_writer.py`:
  - `test_ascii_header`: ASCII PLY header has correct magic, format, element, property declarations
  - `test_binary_header`: binary PLY header same structure
  - `test_vertex_count_matches`: vertex count in header matches data rows
- `tests/test_transform.py`:
  - Use `pyart.testing.NEXRAD_ARCHIVE_MSG31_COMPRESSED_FILE` for integration test (pyart built-in fixture)
  - `test_transform_produces_ply`: output PLY exists and has valid header
  - `test_transform_has_vertices`: at least 1 vertex (pyart fixture has some data)
  - `test_transform_exits_cleanly`: process exits 0
  - NOTE: This developer test uses pyart's tiny fixture. IT-1/IT-2 require real S3 data and are not replaced by this test.
- AC: AC-3.2, AC-3.3, AC-3.5, AC-3.6

**AC coverage:** AC-3.1–AC-3.13

---

### Worker 3: `implement_viewer`
**Scope:** JS Three.js viewer + viewer/package.json

**Files to own:**
- `viewer/index.html`
- `viewer/src/main.js` (or main.ts)
- `viewer/package.json`
- `viewer/vite.config.js` (or equivalent)
- `viewer/package-lock.json`

**Tasks (in order):**

#### V-1: Verify viewer dependencies
- `viewer/package.json` must declare `three` as a dependency
- Dev server: Vite (already exists as `vite.config.js`)
- Scripts must include: `"dev"`, `"build"`, `"preview"`
- Run `npm install` in viewer/ to confirm lockfile is up-to-date
- AC: AC-1.2

#### V-2: Verify PLY loading paths
- File picker input: `<input type="file">` triggers load via `FileReader` + `PLYLoader`
- URL parameter: `?ply=<url>` loads via fetch + `PLYLoader`
- Use Three.js `PLYLoader` from `three/examples/jsm/loaders/PLYLoader.js`
- AC: AC-4.2

#### V-3: Verify 3D rendering
- Three.js scene with `WebGLRenderer`, `PerspectiveCamera`, `OrbitControls`
- Load geometry as `THREE.Points` with `vertexColors: true`
- Auto-frame camera: compute bounding sphere of loaded geometry and position camera to see entire cloud
- Point size: default ~1.5–2.0; optionally expose as URL parameter
- AC: AC-4.1, AC-4.3

#### V-4: Verify interactive controls
- OrbitControls from `three/examples/jsm/controls/OrbitControls.js`
- Orbit: left-click drag rotates view
- Zoom: scroll wheel zooms in/out
- Pan: right-click drag pans
- AC: AC-4.4, AC-4.5, AC-4.6

#### V-5: Status text and MSG-9
- Show minimal status text: "Loading..." while PLY loads, remove or replace with point count on success
- On load error: display error message in status area
- Keep UI minimal — no legend, no time scrubber, no additional chrome
- AC: AC-4.1 (MSG-9: page loads with visible rendering canvas)

#### V-6: Add ready-state DOM hook for browser automation
- After render completes, set `document.body.dataset.ready = 'true'` (or similar)
- This enables Playwright scripts to reliably detect render completion for IT-4/IT-5 evidence capture
- AC: IT-4, IT-5 (automation support)

#### V-7: Build verification
- Run `npm run build` in viewer/ — confirm `viewer/dist/index.html` and `viewer/dist/assets/*.js` exist
- Commit updated `viewer/dist/` if anything changed
- AC: AC-1.2, AC-4.1

**AC coverage:** AC-1.2, AC-4.1–AC-4.6

---

## Merge Phase: `merge_implementation`

After all three parallel workers complete, the merge node must:

### M-1: Resolve any conflicts
- Python files: no overlap expected (fetch/transform are separate packages, viewer is JS)
- `pyproject.toml`: merge any dep additions from transform worker
- `tests/`: merge all test files (no overlapping filenames if workers followed scoping)

### M-2: Run `uv sync` and verify Python environment
```bash
direnv allow && uv sync
```
- Confirm `nexrad-fetch --help` and `nexrad-transform --help` work

### M-3: Fix validation scripts
These fixes must be applied in the merge phase (they span multiple tool behaviors):

#### M-3a: Fix validate-test.sh — remove fixture fallback
- Remove pyart fixture fallback blocks from IT-1 and IT-3 sections
- If S3 fetch fails, scripts must exit with FAIL status, not substitute fixture data
- AC: AC-2.9

#### M-3b: Fix validate-test.sh — fix clear-air test time
- Change `KLSX 20240501_050000` → `KLSX 20240501_173000`
- Per DoD IT-3: KLSX 2024-05-01 ~17:30 UTC
- AC: IT-3

#### M-3c: Fix validate-test.sh — add file size check
- After IT-1 fetch, verify downloaded file size > 500 KB
- If ≤ 500 KB, fail the scenario (DoD: "A file ≤500KB is evidence of fixture fallback")
- AC: IT-1

#### M-3d: Fix validate-artifacts.sh — verify execute bit
- Ensure `chmod +x scripts/validate-*.sh` is run

### M-4: Run validation suite
```bash
bash scripts/validate-build.sh
bash scripts/validate-fmt.sh
uv run pytest tests/ -v
```
All must pass before committing.

### M-5: Write evidence directory structure
Create the contracted evidence layout:
```
.ai/runs/$KILROY_RUN_ID/test-evidence/latest/
├── IT-1/
│   ├── fetch_stdout.log
│   ├── fetch_exit_code.txt
│   └── downloaded_file_info.json
├── IT-2/
│   ├── transform_stdout.log
│   ├── transform_exit_code.txt
│   ├── ply_header.txt
│   └── ply_validation.json
├── IT-3/
│   ├── transform_stdout.log
│   ├── transform_exit_code.txt
│   └── ply_validation.json
├── IT-4/
│   ├── viewer_loaded.png
│   ├── ply_rendered.png
│   ├── orbit_rotated.png
│   └── viewer_console.log
├── IT-5/
│   ├── fetch_stdout.log
│   ├── transform_stdout.log
│   ├── pipeline_rendered.png
│   └── pipeline_summary.json
├── IT-6/
│   ├── help_stdout.log
│   ├── invalid_site_stdout.log
│   ├── invalid_site_exit_code.txt
│   ├── no_scans_stdout.log
│   └── no_scans_exit_code.txt
├── IT-7/
│   ├── help_stdout.log
│   ├── invalid_file_stdout.log
│   ├── invalid_file_exit_code.txt
│   ├── bad_format_stdout.log
│   └── bad_format_exit_code.txt
└── manifest.json
```

The `manifest.json` must record for each scenario:
```json
{
  "scenario_id": "IT-1",
  "status": "pass|fail|skip",
  "artifacts": ["fetch_stdout.log", "fetch_exit_code.txt", "downloaded_file_info.json"],
  "missing_artifacts": [],
  "summary": { "size_bytes": 26543210, "exit_code": 0 }
}
```

### M-6: Run IT-1 through IT-7 via validate-test.sh and capture evidence
- IT-4 and IT-5 require browser automation (Playwright or manual screenshot)
- IT-1, IT-2, IT-3, IT-6, IT-7 are fully automated non-UI scenarios
- For IT-4/IT-5 viewer screenshots: use Playwright (`npx playwright`) if available, otherwise document as manual

---

## Implementation Order and Dependencies

```
implement_fetch (parallel) ─────────────────────────────┐
implement_transform (parallel) ──────────────────────────┤ → merge_implementation
implement_viewer (parallel) ─────────────────────────────┘
```

Within each parallel worker, the order is as specified in each worker's task list above.

The three workers are independent and have no shared file ownership (by design).

---

## AC-to-Worker Traceability Matrix

| AC | Description | Worker | Status |
|----|-------------|--------|--------|
| AC-1.1 | `direnv allow && uv sync` works | fetch (F-6, F-7) | verify |
| AC-1.2 | `npm install` in viewer works | viewer (V-1, V-7) | verify |
| AC-1.3 | `pyproject.toml` declares deps | fetch (F-6) | verify |
| AC-1.4 | `.envrc` activates venv | fetch (F-7) | verify |
| AC-2.1 | Fetch accepts site + datetime CLI args | fetch (F-3) | fix |
| AC-2.2 | Fetch uses `unidata-nexrad-level2` anon | fetch (F-1) | **FIX** |
| AC-2.3 | Fetch downloads to specified path | fetch (F-4) | verify |
| AC-2.4 | Downloaded file is valid gzip | fetch (F-1+F-4) | verify after F-1 |
| AC-2.5 | Fetch exits 0/non-zero correctly | fetch (F-4) | verify |
| AC-2.6 | Error for invalid site code | fetch (F-2) | improve |
| AC-2.7 | Error when no scans found | fetch (F-4) | verify |
| AC-2.8 | Fetch help text | fetch | verify |
| AC-2.9 | No silent fixture fallback | fetch (F-4) + merge (M-3a) | **FIX** |
| AC-3.1 | Transform accepts input/output paths | transform | verify |
| AC-3.2 | PLY header correct format | transform (T-7) | fix |
| AC-3.3 | All elevation tilts included | transform (T-4) | verify |
| AC-3.4 | No-data gates filtered | transform (T-2) | **FIX** |
| AC-3.5 | Py-ART coordinate transform | transform (T-5) | verify |
| AC-3.6 | NWS color table | transform (T-1) | **FIX** |
| AC-3.7 | Active storm >100K vertices | transform (T-2) | verify after T-2 |
| AC-3.8 | Clear-air <10K vertices | transform (T-2, T-6) | verify after T-2 |
| AC-3.9 | Transform exits 0/non-zero | transform (T-6) | fix |
| AC-3.10 | Error for invalid input | transform | verify |
| AC-3.11 | Transform help text | transform | verify |
| AC-3.12 | Reports vertex count | transform (T-8) | verify |
| AC-3.13 | Gate center placement | transform (T-3) | verify |
| AC-4.1 | Viewer serves web page | viewer (V-3, V-7) | verify |
| AC-4.2 | Loads PLY via picker/URL | viewer (V-2) | verify |
| AC-4.3 | Colored point cloud renders | viewer (V-3) | verify |
| AC-4.4 | Orbit controls | viewer (V-4) | verify |
| AC-4.5 | Zoom controls | viewer (V-4) | verify |
| AC-4.6 | Pan controls | viewer (V-4) | verify |
| AC-5.1 | Full pipeline end-to-end | merge (M-6) | verify |
| AC-5.2 | Layered tilts visible in viewer | merge (M-6) | verify |

---

## IT Scenario Coverage

| Scenario | Key Fix Dependencies | Primary Worker | Automated? |
|----------|---------------------|----------------|------------|
| IT-1 | F-1 (bucket), M-3a (no fallback), M-3c (size check) | fetch | Yes |
| IT-2 | T-1 (colors), T-2 (threshold), T-7 (PLY format) | transform | Yes |
| IT-3 | T-2 (threshold), T-6 (empty handling), M-3b (correct time) | transform | Yes |
| IT-4 | V-2, V-3, V-4, V-6 | viewer | Manual/Playwright |
| IT-5 | All of IT-1 + IT-2 + IT-4 | merge | Mixed |
| IT-6 | F-1, F-2, F-3, F-4 | fetch | Yes |
| IT-7 | T-9 (error handling verified) | transform | Yes |

---

## File Ownership Summary

### `implement_fetch` owns:
- `src/nexrad_fetch/fetch.py` — **FIX: bucket name**
- `src/nexrad_fetch/cli.py` — **FIX: help text bucket ref; add ISO datetime**
- `src/nexrad_fetch/__init__.py`
- `pyproject.toml` — verify/update
- `.envrc` — verify
- `.gitignore` — verify
- `tests/__init__.py` — create if missing
- `tests/test_fetch.py` — **CREATE**

### `implement_transform` owns:
- `src/nexrad_transform/colors.py` — **FIX: replace color table**
- `src/nexrad_transform/transform.py` — **FIX: DBZ_MIN threshold; empty result handling**
- `src/nexrad_transform/ply_writer.py` — **FIX: default binary format, add --ascii flag**
- `src/nexrad_transform/cli.py` — verify/update
- `src/nexrad_transform/__init__.py`
- `tests/test_colors.py` — **CREATE**
- `tests/test_ply_writer.py` — **CREATE**
- `tests/test_transform.py` — **CREATE**

### `implement_viewer` owns:
- `viewer/index.html` — verify/update
- `viewer/src/main.js` — verify/update
- `viewer/package.json` — verify/update
- `viewer/vite.config.js` — verify
- `viewer/package-lock.json` — update after npm install

### `merge_implementation` owns:
- `scripts/validate-test.sh` — **FIX: remove fallback, fix time, add size check**
- `scripts/validate-build.sh` — verify
- `scripts/validate-fmt.sh` — verify
- `scripts/validate-artifacts.sh` — verify + chmod
- `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/**` — **CREATE** during IT run

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| `unidata-nexrad-level2` S3 path format differs from NOAA | Pre-test with `--list-only` before full IT run; verify path format `YYYY/MM/DD/SITE/SITE_YYYYMMDD_HHMMSS_V06` |
| Clear-air scan at KLSX 2024-05-01 17:30 UTC doesn't exist | Search window ±2 hours; if needed, try adjacent times; record actual key used in evidence |
| Active storm with DBZ_MIN=-30 produces >2M points → viewer performance | Binary PLY (15 bytes/vertex) keeps files under 30 MB; Three.js handles 2M points on modern hardware; add optional `--max-points N` downsampling flag |
| pyart fixture in unit tests is too small to exercise all sweeps | Unit tests supplement, not replace, integration tests; IT-2 with real KTLX 2013-05-20 data is ground truth |
| Browser automation for IT-4/IT-5 screenshots may be flaky | Use DOM ready-state hook (V-6); capture console logs alongside screenshots; document manual fallback |

---

## Definition of Success

Implementation is complete only when:
- All three CLIs are installed and respond to `--help`
- `uv run pytest tests/ -v` passes (all new unit tests green)
- `bash scripts/validate-build.sh` passes
- `bash scripts/validate-fmt.sh` passes
- `bash scripts/validate-test.sh` completes IT-1 through IT-7 with correct evidence artifacts
- `bash scripts/validate-artifacts.sh` passes (manifest.json contains all 7 scenario IDs)
- Fetch correctly downloads from `unidata-nexrad-level2` (no fixture fallback)
- Transform produces >100K vertices for KTLX 2013-05-20 with correct NWS colors
- Transform produces <10K vertices for KLSX 2024-05-01 ~17:30 UTC
- Viewer renders the PLY interactively with orbit/zoom/pan visible
- IT-5 end-to-end produces a screenshot showing layered 3D tilt structure
