# NEXRAD 3D Point Cloud Viewer v1 — Definition of Done

## Scope

### In Scope

- Python CLI tool to fetch NEXRAD Level II archive files from NOAA S3
- Python CLI tool to transform Level II data into colored PLY point clouds (all elevation tilts, reflectivity only)
- Web-based 3D viewer that loads PLY files and renders interactive point clouds with orbit/zoom/pan
- Reproducible dev environment via direnv + uv (Python) and package.json (JS)

### Out of Scope

- Surface rendering, volumetric rendering, or any non-point-cloud representation
- Time series / animation across multiple scans
- Multi-site data combination
- VR or native app targets
- Color legend, UI controls, or any viewer chrome beyond orbit/zoom/pan
- Velocity, spectrum width, or dual-pol variables (reflectivity only)

### Assumptions

- Network access to `s3://noaa-nexrad-level2/` (public, no auth)
- Python 3.10+ available via uv
- Node.js 18+ available for viewer build/dev
- direnv installed on the development machine
- A modern web browser with WebGL support for the viewer

## Deliverables

| Artifact | Location | Description |
|----------|----------|-------------|
| Fetch tool | `src/nexrad_fetch/` | Python CLI: downloads Level II files from S3 given site + time |
| Transform tool | `src/nexrad_transform/` | Python CLI: Level II binary → PLY point cloud via Py-ART |
| Viewer | `viewer/` | HTML/JS web page: loads PLY, renders 3D point cloud with Three.js |
| Python project config | `pyproject.toml` | Dependencies (pyart, boto3), scripts, uv config |
| JS project config | `viewer/package.json` | Dependencies (three), dev server config |
| Environment config | `.envrc` | direnv setup for automatic environment activation |

## Acceptance Criteria

### Environment (AC-1)

| ID | Criterion | Covered by |
|----|-----------|------------|
| AC-1.1 | Running `direnv allow && uv sync` in a fresh clone produces a working Python environment with pyart and boto3 installed | IT-1, IT-2, IT-3, IT-5 |
| AC-1.2 | Running `npm install` in `viewer/` installs Three.js and produces a working dev server | IT-4, IT-5 |
| AC-1.3 | `pyproject.toml` exists and declares all Python dependencies | IT-1, IT-2, IT-3 |
| AC-1.4 | `.envrc` exists and activates the uv-managed virtual environment | IT-1, IT-2, IT-3, IT-5 |

### Fetch (AC-2)

| ID | Criterion | Covered by |
|----|-----------|------------|
| AC-2.1 | Fetch tool accepts a site code and date/time as CLI arguments | IT-1, IT-5 |
| AC-2.2 | Fetch tool lists available scans near the requested time from S3 | IT-1 |
| AC-2.3 | Fetch tool downloads a Level II archive file to a specified output path | IT-1, IT-5 |
| AC-2.4 | Downloaded file is a valid gzip archive containing Level II data | IT-1, IT-5 |
| AC-2.5 | Fetch tool exits 0 on success and non-zero on failure | IT-1, IT-6 |
| AC-2.6 | Fetch tool displays an error message when given an invalid site code | IT-6 |
| AC-2.7 | Fetch tool displays an error message when no scans are found for the given time | IT-6 |
| AC-2.8 | Fetch tool displays help text when invoked with `--help` | IT-6 |

### Transform (AC-3)

| ID | Criterion | Covered by |
|----|-----------|------------|
| AC-3.1 | Transform tool accepts a Level II file path as CLI input and an output PLY path | IT-2, IT-3, IT-5 |
| AC-3.2 | Output PLY file has a valid header with vertex element declaring x, y, z (float) and red, green, blue (uchar) properties | IT-2, IT-3 |
| AC-3.3 | All elevation tilts from the volume scan are included in the output | IT-2 |
| AC-3.4 | Gates with no reflectivity data are filtered out (not written to PLY) | IT-3 |
| AC-3.5 | Cartesian coordinates use standard radar geometry (earth curvature + beam refraction via Py-ART) with origin (0,0,0) at the radar antenna | IT-2 |
| AC-3.13 | Each point is placed at the volumetric center of its gate (mid-range, center azimuth, center elevation), not at any edge | IT-2 |
| AC-3.6 | Colors map dBZ values to the standard NWS reflectivity color table | IT-2 |
| AC-3.7 | Active storm scan produces >100K vertices in the PLY | IT-2 |
| AC-3.8 | Clear-air scan produces <10K vertices in the PLY | IT-3 |
| AC-3.9 | Transform tool exits 0 on success and non-zero on failure | IT-2, IT-3, IT-7 |
| AC-3.10 | Transform tool displays an error message when given an invalid input file | IT-7 |
| AC-3.11 | Transform tool displays help text when invoked with `--help` | IT-7 |
| AC-3.12 | Transform tool reports the number of vertices written on success | IT-2, IT-3 |

### Viewer (AC-4)

| ID | Criterion | Covered by |
|----|-----------|------------|
| AC-4.1 | Viewer serves a web page that loads in a modern browser | IT-4, IT-5 |
| AC-4.2 | Viewer loads a PLY file (via file picker or URL parameter) | IT-4, IT-5 |
| AC-4.3 | Point cloud renders in 3D with colored points visible | IT-4, IT-5 |
| AC-4.4 | Orbit controls allow rotating the view by mouse drag | IT-4 |
| AC-4.5 | Zoom controls allow zooming in/out by scroll wheel | IT-4 |
| AC-4.6 | Pan controls allow panning the view | IT-4 |

### Integration (AC-5)

| ID | Criterion | Covered by |
|----|-----------|------------|
| AC-5.1 | The full pipeline (fetch → transform → view) works end-to-end on a known storm scan | IT-5 |
| AC-5.2 | The 3D point cloud visually shows layered elevation tilts as distinct spatial layers | IT-5 |

## User-Facing Message Inventory

| ID | Message surface | Trigger condition | Covered by |
|----|----------------|-------------------|------------|
| MSG-1 | Fetch: help text showing usage, arguments, and options | `--help` flag | IT-6 |
| MSG-2 | Fetch: listing available scans near requested time | Valid site + time with results | IT-1 |
| MSG-3 | Fetch: download success with file path and size | Successful download | IT-1, IT-5 |
| MSG-4 | Fetch: error for invalid site code | Unrecognized ICAO code | IT-6 |
| MSG-5 | Fetch: error for no scans found | Valid site but no data at time | IT-6 |
| MSG-6 | Transform: help text showing usage, arguments, and options | `--help` flag | IT-7 |
| MSG-7 | Transform: success with vertex count | Successful conversion | IT-2, IT-3 |
| MSG-8 | Transform: error for invalid input file | Non-existent or non-Level-II file | IT-7 |
| MSG-9 | Viewer: page loads with visible rendering canvas | Browser navigates to viewer URL | IT-4, IT-5 |

## Test Evidence Contract

| Item | Requirement |
|------|-------------|
| Evidence root | `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/` |
| Scenario folder pattern | `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/IT-<id>/` |
| Manifest | `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/manifest.json` |
| UI scenarios (`surface=ui` or `surface=mixed`) | Include screenshot evidence proving key states |
| Non-UI scenarios (`surface=non_ui`) | Include text/structured evidence (log/stdout/json) |
| Failure behavior | Emit best-effort artifacts and manifest entry; record missing artifacts explicitly |

## Integration Test Scenarios

### IT-1: Fetch active storm scan

**Surface:** `non_ui`

**Starting state:** Network access to S3. No local files.

**Actions:**
1. Run fetch tool with site `KTLX` (Oklahoma City) and date `2013-05-20T20:00Z` (Moore tornado) → tool lists available scans, selects closest, downloads file
2. Verify downloaded file exists and is >5MB
3. Verify file is valid gzip (`gunzip -t` exits 0)
4. Verify tool printed scan listing (MSG-2) and success message with path and size (MSG-3)

**Verification:** Fetch command exits 0. Downloaded file passes gzip validation.

**Evidence artifacts:**
- `IT-1/fetch_stdout.log` — full stdout capture
- `IT-1/fetch_exit_code.txt` — exit code
- `IT-1/downloaded_file_info.json` — file name, size, gzip validity

---

### IT-2: Transform active storm to PLY

**Surface:** `non_ui`

**Starting state:** Test downloads a Level II file for KTLX 2013-05-20 as setup (or uses cached copy).

**Actions:**
1. Run transform tool on the Level II file → outputs PLY file
2. Verify PLY file exists and has valid header (`ply` magic, `element vertex` with count, x/y/z float + r/g/b uchar properties)
3. Verify vertex count >100K (AC-3.7)
4. Parse first 10 and last 10 vertices: confirm coordinates are in plausible range (x/y within ~300km, z within ~20km) and colors are valid RGB (0-255)
5. Verify all elevation tilts are present: count distinct z-value clusters (expect 10+)
6. Verify colors follow NWS table: vertices with high reflectivity (near core) should have red/magenta colors, outer regions green/yellow
7. Verify tool printed vertex count on success (MSG-7)

**Verification:** Transform command exits 0. PLY file validates structurally and semantically.

**Evidence artifacts:**
- `IT-2/transform_stdout.log` — full stdout capture
- `IT-2/transform_exit_code.txt` — exit code
- `IT-2/ply_header.txt` — first 10 lines of PLY file
- `IT-2/ply_validation.json` — vertex count, coordinate ranges, tilt count, color distribution summary

---

### IT-3: Transform clear air to sparse PLY

**Surface:** `non_ui`

**Starting state:** Test downloads a clear-air Level II file as setup.

**Actions:**
1. Run transform tool on clear-air Level II file → outputs PLY
2. Verify PLY file exists with valid header
3. Verify vertex count <10K (AC-3.8) — confirms empty gate filtering works
4. Verify tool exits 0 and prints vertex count (MSG-7)

**Verification:** Transform command exits 0. Vertex count confirms filtering.

**Evidence artifacts:**
- `IT-3/transform_stdout.log` — full stdout capture
- `IT-3/transform_exit_code.txt` — exit code
- `IT-3/ply_validation.json` — vertex count, file size

---

### IT-4: Viewer renders PLY in browser

**Surface:** `ui`

**Starting state:** PLY file from IT-2 available. Viewer dev server not running.

**Actions:**
1. Install viewer dependencies (`npm install` in `viewer/`)
2. Start viewer dev server
3. Open viewer URL in browser
4. Load the PLY file (file picker or URL parameter)
5. Verify colored point cloud is visible on screen (not blank, not error)
6. Perform orbit (mouse drag) — verify view rotates
7. Perform zoom (scroll) — verify view zooms
8. Perform pan — verify view pans

**Verification:** Viewer loads, renders points, and responds to all three control types.

**Evidence artifacts:**
- `IT-4/viewer_loaded.png` — screenshot after page loads
- `IT-4/ply_rendered.png` — screenshot showing rendered point cloud
- `IT-4/orbit_rotated.png` — screenshot after orbit rotation
- `IT-4/viewer_console.log` — browser console output (no errors)

---

### IT-5: End-to-end pipeline

**Surface:** `mixed`

**Starting state:** Network access. No local files. Viewer not running.

**Actions:**
1. Run fetch tool with site `KTLX` and date `2013-05-20T20:00Z` → downloads Level II file
2. Run transform tool on downloaded file → outputs PLY
3. Start viewer dev server, open in browser, load the PLY
4. Verify 3D point cloud renders with visible layered elevation tilts
5. Verify distinct spatial layers are visible (the "layered cake" of tilts)
6. Verify colors span the NWS range (greens through reds/magentas present)

**Verification:** All three tools execute successfully. Visual confirms layered 3D structure.

**Evidence artifacts:**
- `IT-5/fetch_stdout.log` — fetch output
- `IT-5/transform_stdout.log` — transform output with vertex count
- `IT-5/pipeline_rendered.png` — screenshot of final 3D rendering
- `IT-5/pipeline_summary.json` — fetch file size, transform vertex count, viewer load status

---

### IT-6: Fetch error handling and help

**Surface:** `non_ui`

**Starting state:** Network access.

**Actions:**
1. Run fetch with `--help` → verify help text displays (MSG-1)
2. Run fetch with invalid site code `ZZZZ` → verify error message (MSG-4) and non-zero exit
3. Run fetch with valid site but impossible date `1900-01-01T00:00Z` → verify "no scans found" message (MSG-5) and non-zero exit

**Verification:** All three invocations produce expected messages and exit codes.

**Evidence artifacts:**
- `IT-6/help_stdout.log` — help text output
- `IT-6/invalid_site_stdout.log` — error message for bad site
- `IT-6/invalid_site_exit_code.txt` — non-zero exit code
- `IT-6/no_scans_stdout.log` — error message for no data
- `IT-6/no_scans_exit_code.txt` — non-zero exit code

---

### IT-7: Transform error handling and help

**Surface:** `non_ui`

**Starting state:** No special setup.

**Actions:**
1. Run transform with `--help` → verify help text displays (MSG-6)
2. Run transform with non-existent file path → verify error message (MSG-8) and non-zero exit
3. Run transform with a file that is not Level II data (e.g., a text file) → verify error message (MSG-8) and non-zero exit

**Verification:** All three invocations produce expected messages and exit codes.

**Evidence artifacts:**
- `IT-7/help_stdout.log` — help text output
- `IT-7/invalid_file_stdout.log` — error for non-existent file
- `IT-7/invalid_file_exit_code.txt` — non-zero exit code
- `IT-7/bad_format_stdout.log` — error for wrong file format
- `IT-7/bad_format_exit_code.txt` — non-zero exit code

---

## Crosscheck

### Per scenario:

| Scenario | Exercises deliverable? | Automatable? | Bounded? | Proportional? | Independent? | Evidence defined? |
|----------|----------------------|--------------|----------|---------------|--------------|-------------------|
| IT-1 | Fetch tool CLI | Yes | Yes (1 download) | Yes | Yes (own download) | Yes |
| IT-2 | Transform tool CLI | Yes | Yes (1 file) | Yes | Yes (downloads own input) | Yes |
| IT-3 | Transform tool CLI | Yes | Yes (1 file) | Yes | Yes (downloads own input) | Yes |
| IT-4 | Viewer in browser | Yes | Yes (load + 3 controls) | Yes | Yes (uses IT-2 PLY or generates own) | Yes (screenshots) |
| IT-5 | Full pipeline | Yes | Yes (3 steps) | Yes | Yes (starts from scratch) | Yes (mixed) |
| IT-6 | Fetch tool CLI (errors) | Yes | Yes (3 invocations) | Yes | Yes (no deps) | Yes |
| IT-7 | Transform tool CLI (errors) | Yes | Yes (3 invocations) | Yes | Yes (no deps) | Yes |

### Per AC coverage:

| AC | Covered by scenarios |
|----|---------------------|
| AC-1.1 | IT-1, IT-2, IT-3, IT-5 (all Python scenarios use the environment) |
| AC-1.2 | IT-4, IT-5 (both install/run viewer) |
| AC-1.3 | IT-1, IT-2, IT-3 (import fails if deps missing) |
| AC-1.4 | IT-1, IT-2, IT-3, IT-5 (environment must activate) |
| AC-2.1 | IT-1, IT-5 |
| AC-2.2 | IT-1 |
| AC-2.3 | IT-1, IT-5 |
| AC-2.4 | IT-1, IT-5 |
| AC-2.5 | IT-1, IT-6 |
| AC-2.6 | IT-6 |
| AC-2.7 | IT-6 |
| AC-2.8 | IT-6 |
| AC-3.1 | IT-2, IT-3, IT-5 |
| AC-3.2 | IT-2, IT-3 |
| AC-3.3 | IT-2 |
| AC-3.4 | IT-3 |
| AC-3.5 | IT-2 |
| AC-3.6 | IT-2 |
| AC-3.7 | IT-2 |
| AC-3.8 | IT-3 |
| AC-3.9 | IT-2, IT-3, IT-7 |
| AC-3.10 | IT-7 |
| AC-3.11 | IT-7 |
| AC-3.12 | IT-2, IT-3 |
| AC-4.1 | IT-4, IT-5 |
| AC-4.2 | IT-4, IT-5 |
| AC-4.3 | IT-4, IT-5 |
| AC-4.4 | IT-4 |
| AC-4.5 | IT-4 |
| AC-4.6 | IT-4 |
| AC-5.1 | IT-5 |
| AC-5.2 | IT-5 |

All ACs covered. All messages covered (MSG-1 through MSG-9 each have at least one scenario).

### Delivery form check:

- CLI tools tested via CLI invocation: IT-1, IT-2, IT-3, IT-5, IT-6, IT-7
- Web viewer tested in browser: IT-4, IT-5

### Message coverage:

| MSG | Covered by |
|-----|-----------|
| MSG-1 | IT-6 |
| MSG-2 | IT-1 |
| MSG-3 | IT-1, IT-5 |
| MSG-4 | IT-6 |
| MSG-5 | IT-6 |
| MSG-6 | IT-7 |
| MSG-7 | IT-2, IT-3 |
| MSG-8 | IT-7 |
| MSG-9 | IT-4, IT-5 |

All messages covered.
