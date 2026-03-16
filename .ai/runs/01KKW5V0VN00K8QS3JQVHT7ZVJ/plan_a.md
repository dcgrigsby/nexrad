# NEXRAD 3D Point Cloud Viewer v1 — Implementation Plan A

## Overview

This plan builds three CLI tools (nexrad-fetch, nexrad-transform, nexrad-viewer) plus environment config and validation scripts. The plan is organized into ordered implementation steps, each with clear inputs, outputs, and the AC/IT criteria they satisfy.

---

## Step 0: Project Scaffolding & Environment

**Goal:** Create all config files so `direnv allow && uv sync` and `npm install` work.

### 0.1 — `.envrc`

Create `.envrc` at repo root:

```sh
# Activate uv-managed virtualenv
layout python-venv .venv
# Or, if using uv's built-in approach:
# eval "$(uv generate-shell-completion bash)"
# Prefer: source the venv that uv creates
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
# Load local secrets (API keys for LLM providers, etc.)
dotenv_if_exists .env.local
```

The key requirement is that after `direnv allow`, the Python venv created by `uv sync` is activated automatically.

**Satisfies:** AC-1.4

### 0.2 — `pyproject.toml`

Create at repo root. Must declare:

```toml
[project]
name = "nexrad-pointcloud"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "arm-pyart>=1.18",
    "boto3>=1.34",
    "botocore>=1.34",
    "numpy>=1.24",
]

[project.scripts]
nexrad-fetch = "nexrad_fetch.cli:main"
nexrad-transform = "nexrad_transform.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/nexrad_fetch", "src/nexrad_transform"]
```

Key decisions:
- Use `arm-pyart` (the PyPI package name for Py-ART).
- Both CLI tools are declared as console_scripts entry points.
- Source layout under `src/` with hatchling build backend.

**Satisfies:** AC-1.1, AC-1.3

### 0.3 — `viewer/package.json`

```json
{
  "name": "nexrad-viewer",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "npx serve .",
    "start": "npx serve ."
  },
  "dependencies": {
    "three": "^0.170.0"
  }
}
```

The viewer is a static HTML/JS app. Use `serve` (or `vite`, or `http-server`) for the dev server. Three.js is loaded either from `node_modules` or via a CDN/importmap — the simplest approach is an importmap in the HTML pointing to the `node_modules/three/` ESM build.

**Satisfies:** AC-1.2

### 0.4 — Directory structure

```
.envrc
pyproject.toml
src/
  nexrad_fetch/
    __init__.py
    cli.py
    fetch.py
  nexrad_transform/
    __init__.py
    cli.py
    transform.py
    colors.py
    ply_writer.py
viewer/
  package.json
  index.html
  main.js
scripts/
  validate-build.sh
  validate-fmt.sh
  validate-test.sh
```

**Note on source layout:** The `src/` prefix with `hatch.build.targets.wheel.packages` pointing to `src/nexrad_fetch` and `src/nexrad_transform` means imports work as `from nexrad_fetch.fetch import ...` after `uv sync` (editable install).

---

## Step 1: Fetch Tool (`src/nexrad_fetch/`)

**Goal:** Python CLI that downloads NEXRAD Level II files from S3.

### 1.1 — `src/nexrad_fetch/cli.py` (CLI entry point)

Use `argparse` for argument parsing.

**Arguments:**
- `site` (positional): 4-letter ICAO radar site code (e.g., `KTLX`). Uppercased internally.
- `datetime` (positional): ISO 8601 date/time string (e.g., `2013-05-20T20:00Z`). Parsed with `datetime.fromisoformat()` or a lenient parser.
- `--output` / `-o` (optional): output file path. Default: current directory with the S3 filename.
- `--help`: built-in from argparse (MSG-1 / AC-2.8).

**Behavior:**
1. Parse arguments. Validate site code is 4 uppercase alpha chars; if not, print error (MSG-4) and exit 1 (AC-2.6).
2. Construct S3 prefix: `YYYY/MM/DD/SITE/` from the parsed datetime.
3. Call `boto3.client('s3', region_name='us-east-1')` with anonymous config (`botocore.UNSIGNED`).
4. `list_objects_v2(Bucket='noaa-nexrad-level2', Prefix=prefix)` to get all files for that date+site.
5. If no files found, print error (MSG-5) and exit 1 (AC-2.7).
6. Parse filenames to extract scan timestamps. Find closest scan to requested time. Print listing of available scans (MSG-2) (AC-2.2).
7. Download the closest file using `s3.download_file()` (AC-2.3).
8. Print success message with path and file size (MSG-3).
9. Exit 0 (AC-2.5).

### 1.2 — `src/nexrad_fetch/fetch.py` (core logic)

Separate the S3 logic from CLI parsing for testability:

```python
def list_scans(site: str, date: datetime) -> list[ScanInfo]:
    """List available scans from S3 for a site+date."""

def find_closest_scan(scans: list[ScanInfo], target_time: datetime) -> ScanInfo:
    """Find scan closest to the target time."""

def download_scan(scan: ScanInfo, output_path: Path) -> Path:
    """Download a scan file from S3. Returns local path."""
```

**Key implementation detail — anonymous S3 access:**

```python
from botocore import UNSIGNED
from botocore.config import Config

s3 = boto3.client('s3', region_name='us-east-1', config=Config(signature_version=UNSIGNED))
```

**Satisfies:** AC-2.1 through AC-2.8

### 1.3 — Error handling

- Invalid site code (not 4 alpha chars): print `"Error: Invalid site code '{site}'. Expected 4-letter ICAO code (e.g., KTLX)."`, exit 1.
- No scans found: print `"Error: No scans found for {site} on {date}."`, exit 1.
- S3 errors (network, etc.): catch `botocore.exceptions.ClientError`, print message, exit 1.

---

## Step 2: Transform Tool (`src/nexrad_transform/`)

**Goal:** Parse Level II → PLY point cloud with all elevation tilts, NWS colors, gate-center placement.

### 2.1 — `src/nexrad_transform/cli.py` (CLI entry point)

**Arguments:**
- `input` (positional): Path to Level II archive file.
- `output` (positional): Path for output PLY file.
- `--format` (optional): `ascii` (default) or `binary_little_endian`. ASCII is fine for v1.
- `--help`: built-in from argparse (MSG-6 / AC-3.11).

**Behavior:**
1. Parse arguments. Validate input file exists; if not, print error (MSG-8) and exit 1 (AC-3.10).
2. Call `transform(input_path, output_path, fmt)`.
3. On success, print vertex count (MSG-7 / AC-3.12) and exit 0 (AC-3.9).
4. On failure (invalid file, Py-ART parse error), catch exception, print error (MSG-8), exit 1.

### 2.2 — `src/nexrad_transform/transform.py` (core logic)

```python
def transform(input_path: Path, output_path: Path, fmt: str = "ascii") -> int:
    """Transform Level II file to PLY. Returns vertex count."""
```

**Algorithm (pseudocode):**

```python
import pyart
import numpy as np
from pyart.core.transforms import antenna_vectors_to_cartesian

# 1. Parse
radar = pyart.io.read_nexrad_archive(str(input_path))

# 2. Validate reflectivity field exists
if 'reflectivity' not in radar.fields:
    raise ValueError("No reflectivity field in file")

# 3. Collect all valid points across all sweeps
all_x, all_y, all_z = [], [], []
all_r, all_g, all_b = [], [], []

for sweep_idx in range(radar.nsweeps):
    start = radar.sweep_start_ray_index['data'][sweep_idx]
    end = radar.sweep_end_ray_index['data'][sweep_idx] + 1

    # Get reflectivity data for this sweep
    refl = radar.fields['reflectivity']['data'][start:end, :]  # (n_rays, n_gates)

    # Get coordinate arrays
    az = radar.azimuth['data'][start:end]      # (n_rays,)
    el = radar.elevation['data'][start:end]    # (n_rays,)
    rng = radar.range['data']                   # (n_gates,) — gate centers already

    # Build 2D grids for coordinate transform
    n_rays = end - start
    n_gates = len(rng)
    az_2d = np.broadcast_to(az[:, np.newaxis], (n_rays, n_gates))
    el_2d = np.broadcast_to(el[:, np.newaxis], (n_rays, n_gates))
    rng_2d = np.broadcast_to(rng[np.newaxis, :], (n_rays, n_gates))

    # Cartesian coords via Py-ART (includes earth curvature + 4/3 refraction)
    x, y, z = antenna_vectors_to_cartesian(rng_2d, az_2d, el_2d)

    # Create valid-data mask: not masked AND >= -30 dBZ
    valid = ~np.ma.getmaskarray(refl)
    if valid.any():
        refl_valid = refl[valid].data if hasattr(refl[valid], 'data') else np.asarray(refl[valid])
        valid &= (refl >= -30.0).filled(False)

    # Extract valid points
    x_valid = x[valid]
    y_valid = y[valid]
    z_valid = z[valid]
    refl_valid = np.asarray(refl[valid])

    # Map to NWS colors
    r, g, b = dbz_to_rgb_vectorized(refl_valid)

    all_x.append(x_valid.ravel())
    all_y.append(y_valid.ravel())
    all_z.append(z_valid.ravel())
    all_r.append(r.ravel())
    all_g.append(g.ravel())
    all_b.append(b.ravel())

# 4. Concatenate
X = np.concatenate(all_x)
Y = np.concatenate(all_y)
Z = np.concatenate(all_z)
R = np.concatenate(all_r)
G = np.concatenate(all_g)
B = np.concatenate(all_b)

# 5. Write PLY
write_ply(output_path, X, Y, Z, R, G, B, fmt=fmt)
return len(X)
```

**Gate-center placement (AC-3.13):** Py-ART's `radar.range['data']` already gives the range to the *center* of each gate (not the leading edge). The azimuth and elevation values for each radial represent the beam center direction. Therefore, using `antenna_vectors_to_cartesian(range, az, el)` directly places each point at the volumetric center of its gate. No additional offset is needed — this is the correct behavior by default. Document this reasoning in a code comment.

**All sweeps (AC-3.3):** The loop iterates `range(radar.nsweeps)`, which covers every elevation tilt in the volume scan.

**Satisfies:** AC-3.1 through AC-3.13

### 2.3 — `src/nexrad_transform/colors.py` (NWS color mapping)

```python
# NWS reflectivity color table — exact RGB values from spec
NWS_COLOR_TABLE = [
    (-30, (100, 100, 100)),   # Dark gray
    (-25, (150, 150, 150)),   # Light gray
    (-20, (65, 105, 225)),    # Light blue
    (-10, (0, 200, 255)),     # Cyan
    (0,   (50, 200, 255)),    # Light cyan
    (5,   (0, 150, 255)),     # Blue
    (10,  (0, 200, 0)),       # Green
    (15,  (100, 255, 0)),     # Lime green
    (20,  (255, 255, 0)),     # Yellow
    (25,  (255, 165, 0)),     # Orange
    (30,  (255, 100, 0)),     # Red orange
    (35,  (255, 0, 0)),       # Red
    (40,  (180, 0, 0)),       # Dark red
    (45,  (255, 0, 255)),     # Magenta
    (50,  (138, 43, 226)),    # Violet
    (55,  (255, 255, 255)),   # White
    (60,  (255, 255, 255)),   # Bright white (60+)
]

def dbz_to_rgb(dbz: float) -> tuple[int, int, int]:
    """Map a dBZ value to an (R, G, B) tuple using NWS color table.
    Values below -30 should have been filtered out before calling this.
    """
    for threshold, color in reversed(NWS_COLOR_TABLE):
        if dbz >= threshold:
            return color
    return (100, 100, 100)  # fallback: dark gray for values near -30

def dbz_to_rgb_vectorized(dbz_array: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized NWS color mapping. Returns (R, G, B) arrays of uint8."""
    # Use np.digitize for fast binning
    thresholds = [-30, -25, -20, -10, 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
    colors = np.array([
        [100, 100, 100],  # -30 to -25
        [150, 150, 150],  # -25 to -20
        [65, 105, 225],   # -20 to -10
        [0, 200, 255],    # -10 to 0
        [50, 200, 255],   # 0 to 5
        [0, 150, 255],    # 5 to 10
        [0, 200, 0],      # 10 to 15
        [100, 255, 0],    # 15 to 20
        [255, 255, 0],    # 20 to 25
        [255, 165, 0],    # 25 to 30
        [255, 100, 0],    # 30 to 35
        [255, 0, 0],      # 35 to 40
        [180, 0, 0],      # 40 to 45
        [255, 0, 255],    # 45 to 50
        [138, 43, 226],   # 50 to 55
        [255, 255, 255],  # 55 to 60
        [255, 255, 255],  # 60+
    ], dtype=np.uint8)

    bins = np.digitize(dbz_array, thresholds) - 1
    bins = np.clip(bins, 0, len(colors) - 1)
    mapped = colors[bins]
    return mapped[:, 0], mapped[:, 1], mapped[:, 2]
```

**Satisfies:** AC-3.6

### 2.4 — `src/nexrad_transform/ply_writer.py`

```python
def write_ply(path: Path, x, y, z, r, g, b, fmt="ascii"):
    """Write a colored PLY point cloud file."""
    n = len(x)
    with open(path, 'w' if fmt == 'ascii' else 'wb') as f:
        # Header
        header = f"""ply
format {fmt} 1.0
comment NEXRAD reflectivity point cloud
element vertex {n}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
"""
        if fmt == "ascii":
            f.write(header)
            for i in range(n):
                f.write(f"{x[i]:.2f} {y[i]:.2f} {z[i]:.2f} {r[i]} {g[i]} {b[i]}\n")
        else:
            f.write(header.encode('ascii'))
            # Pack binary data: 3 floats + 3 uchars per vertex
            import struct
            for i in range(n):
                f.write(struct.pack('<fffBBB', x[i], y[i], z[i], r[i], g[i], b[i]))
```

**Performance note:** For large point clouds (>500K points), the per-row loop will be slow. Use `numpy.savetxt` or direct buffer writes instead:

```python
# Fast ASCII write:
data = np.column_stack([x, y, z, r.astype(int), g.astype(int), b.astype(int)])
np.savetxt(f, data, fmt='%.2f %.2f %.2f %d %d %d')

# Fast binary write:
import struct
arr = np.empty(n, dtype=[('x','<f4'),('y','<f4'),('z','<f4'),('r','u1'),('g','u1'),('b','u1')])
arr['x'] = x; arr['y'] = y; arr['z'] = z
arr['r'] = r; arr['g'] = g; arr['b'] = b
f.write(arr.tobytes())
```

**Satisfies:** AC-3.2

---

## Step 3: Viewer (`viewer/`)

**Goal:** Minimal web page that loads PLY and renders interactive 3D point cloud.

### 3.1 — `viewer/index.html`

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>NEXRAD Point Cloud Viewer</title>
  <style>
    body { margin: 0; overflow: hidden; background: #000; }
    canvas { display: block; }
    #file-picker {
      position: absolute; top: 10px; left: 10px; z-index: 10;
      color: #fff; font-family: sans-serif;
    }
  </style>
</head>
<body>
  <div id="file-picker">
    <input type="file" id="ply-input" accept=".ply">
  </div>
  <script type="importmap">
  {
    "imports": {
      "three": "./node_modules/three/build/three.module.js",
      "three/addons/": "./node_modules/three/examples/jsm/"
    }
  }
  </script>
  <script type="module" src="main.js"></script>
</body>
</html>
```

### 3.2 — `viewer/main.js`

```javascript
import * as THREE from 'three';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Scene setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111111);

const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 100, 1000000);
camera.position.set(0, 0, 300000);  // 300km out, looking at origin

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// OrbitControls — orbit (drag), zoom (scroll), pan (right-click drag)
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

// PLY loading
const loader = new PLYLoader();

function loadPLY(url_or_buffer) {
    // If ArrayBuffer, parse directly
    if (url_or_buffer instanceof ArrayBuffer) {
        const geometry = loader.parse(url_or_buffer);
        addPointCloud(geometry);
        return;
    }
    // Otherwise load from URL
    loader.load(url_or_buffer, (geometry) => {
        addPointCloud(geometry);
    });
}

function addPointCloud(geometry) {
    // Remove existing point clouds
    scene.children.filter(c => c.isPoints).forEach(c => scene.remove(c));

    geometry.computeBoundingBox();
    const material = new THREE.PointsMaterial({
        size: 500,  // point size in world units — tune for NEXRAD scale
        vertexColors: true,
        sizeAttenuation: true,
    });
    const points = new THREE.Points(geometry, material);
    scene.add(points);

    // Center camera on point cloud
    const center = new THREE.Vector3();
    geometry.boundingBox.getCenter(center);
    controls.target.copy(center);
    camera.lookAt(center);
}

// File picker handler
document.getElementById('ply-input').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => loadPLY(ev.target.result);
    reader.readAsArrayBuffer(file);
});

// URL parameter: ?ply=path/to/file.ply
const params = new URLSearchParams(window.location.search);
const plyUrl = params.get('ply');
if (plyUrl) {
    loadPLY(plyUrl);
}

// Resize handler
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// Render loop
function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}
animate();
```

**Key design decisions:**
- Camera starts 300km from origin (NEXRAD coords are in meters, storm may span ~200km).
- `sizeAttenuation: true` so points get smaller with distance (natural 3D look).
- Point size 500m — tuned so individual gates are visible but the cloud is not too sparse.
- Both file picker (AC-4.2) and URL parameter supported.
- OrbitControls provides orbit (left-drag, AC-4.4), zoom (scroll, AC-4.5), and pan (right-drag/shift-drag, AC-4.6).

**Satisfies:** AC-4.1 through AC-4.6

---

## Step 4: Validation Scripts

Three committed POSIX sh scripts under `scripts/`.

### 4.1 — `scripts/validate-build.sh`

Verifies that the project builds/installs correctly:

```sh
#!/bin/sh
set -e
echo "=== Validating Python build ==="
uv sync
python -c "import nexrad_fetch; import nexrad_transform; print('Python imports OK')"
echo "=== Validating viewer dependencies ==="
cd viewer && npm install && cd ..
echo "=== validate-build: PASS ==="
```

### 4.2 — `scripts/validate-fmt.sh`

Checks code formatting (optional linter/formatter; use ruff if available):

```sh
#!/bin/sh
set -e
echo "=== Checking Python formatting ==="
if command -v ruff >/dev/null 2>&1; then
  ruff check src/
  ruff format --check src/
  echo "Python formatting: PASS"
else
  echo "ruff not found, skipping Python format check"
fi
echo "=== validate-fmt: PASS ==="
```

### 4.3 — `scripts/validate-test.sh`

Runs the integration tests and writes evidence. This is the most complex script.

**Structure:**

```sh
#!/bin/sh
set -e

RUN_ID="${KILROY_RUN_ID:-01KKW5V0VN00K8QS3JQVHT7ZVJ}"
EVIDENCE_ROOT=".ai/runs/${RUN_ID}/test-evidence/latest"
mkdir -p "$EVIDENCE_ROOT"

# --- Helper functions ---
pass_test() { ... }
fail_test() { ... }

# --- IT-1: Fetch active storm ---
mkdir -p "$EVIDENCE_ROOT/IT-1"
# ... run nexrad-fetch KTLX 2013-05-20T20:00Z, capture stdout/exit code
# ... verify file >5MB, valid gzip
# ... write evidence files

# --- IT-2: Transform active storm ---
mkdir -p "$EVIDENCE_ROOT/IT-2"
# ... run nexrad-transform on downloaded file, capture stdout
# ... verify PLY header, vertex count >100K, coordinate ranges, NWS colors

# --- IT-3: Transform clear air ---
mkdir -p "$EVIDENCE_ROOT/IT-3"
# ... fetch KLSX clear-air file first (or use cached)
# ... run nexrad-transform, verify <10K vertices

# --- IT-6: Fetch error handling ---
mkdir -p "$EVIDENCE_ROOT/IT-6"
# ... test --help, invalid site, no-scans-found

# --- IT-7: Transform error handling ---
mkdir -p "$EVIDENCE_ROOT/IT-7"
# ... test --help, nonexistent file, bad format

# --- IT-4, IT-5: UI/mixed tests ---
# These require a browser; write placeholder evidence noting they need manual verification
# or use a headless browser if available

# --- Write manifest.json ---
cat > "$EVIDENCE_ROOT/manifest.json" << 'MANIFEST'
{
  "run_id": "...",
  "scenarios": [
    {"id": "IT-1", "surface": "non_ui", "status": "...", "artifacts": [...]},
    ...
  ]
}
MANIFEST

echo "=== validate-test: PASS ==="
```

**Evidence directory structure:**
```
.ai/runs/$RUN_ID/test-evidence/latest/
  manifest.json
  IT-1/
    fetch_stdout.log
    fetch_exit_code.txt
    downloaded_file_info.json
  IT-2/
    transform_stdout.log
    transform_exit_code.txt
    ply_header.txt
    ply_validation.json
  IT-3/
    transform_stdout.log
    transform_exit_code.txt
    ply_validation.json
  IT-4/
    (screenshot evidence — requires browser)
  IT-5/
    fetch_stdout.log
    transform_stdout.log
    pipeline_summary.json
    (screenshot evidence — requires browser)
  IT-6/
    help_stdout.log
    invalid_site_stdout.log
    invalid_site_exit_code.txt
    no_scans_stdout.log
    no_scans_exit_code.txt
  IT-7/
    help_stdout.log
    invalid_file_stdout.log
    invalid_file_exit_code.txt
    bad_format_stdout.log
    bad_format_exit_code.txt
```

**Satisfies:** Test evidence contract from DoD

---

## Step 5: Integration Verification

### 5.1 — End-to-end smoke test (IT-5)

After all tools are built:

```sh
# Fetch
nexrad-fetch KTLX 2013-05-20T20:00Z -o /tmp/ktlx_storm.gz

# Transform
nexrad-transform /tmp/ktlx_storm.gz /tmp/ktlx_storm.ply

# View (manual)
cd viewer && npm start
# Open browser, load /tmp/ktlx_storm.ply via file picker
```

This validates AC-5.1 and AC-5.2.

### 5.2 — UI verification (IT-4)

The viewer test (IT-4) requires a browser. The validate-test.sh script will:
1. Start the viewer dev server in background.
2. If a headless browser tool is available (e.g., Playwright), use it to load the page, load the PLY, take screenshots, and verify rendering.
3. If no headless browser, write evidence noting that manual verification is required, with instructions.

---

## Implementation Order & Dependencies

```
Step 0: Scaffolding (.envrc, pyproject.toml, viewer/package.json, directory skeleton)
  ↓
Step 1: Fetch Tool (src/nexrad_fetch/)
  ↓  [fetch tool can now download test data]
Step 2: Transform Tool (src/nexrad_transform/)
  ↓  [transform tool can now produce PLY files]
Step 3: Viewer (viewer/)
  ↓  [viewer can now render the PLY]
Step 4: Validation Scripts (scripts/)
  ↓  [scripts can run end-to-end tests]
Step 5: Integration Verification
```

Steps 1, 2, and 3 could be parallelized (they share no source code), but Step 2 depends on having a Level II file (which Step 1 fetches). In practice, Step 2 development can use the documented test file paths with manual downloads.

---

## AC ↔ Step Traceability Matrix

| AC | Step | How satisfied |
|----|------|---------------|
| AC-1.1 | 0.1, 0.2 | `.envrc` + `pyproject.toml` with arm-pyart, boto3 |
| AC-1.2 | 0.3 | `viewer/package.json` with three |
| AC-1.3 | 0.2 | `pyproject.toml` declares all deps |
| AC-1.4 | 0.1 | `.envrc` activates uv venv |
| AC-2.1 | 1.1 | argparse site + datetime positional args |
| AC-2.2 | 1.2 | `list_scans()` + print listing |
| AC-2.3 | 1.2 | `download_scan()` to output path |
| AC-2.4 | 1.2 | File downloaded directly from S3 (gzip) |
| AC-2.5 | 1.1 | sys.exit(0) on success, sys.exit(1) on error |
| AC-2.6 | 1.3 | Invalid site code validation + error message |
| AC-2.7 | 1.3 | Empty listing check + error message |
| AC-2.8 | 1.1 | argparse `--help` |
| AC-3.1 | 2.1 | argparse input + output positional args |
| AC-3.2 | 2.4 | PLY header with float x/y/z + uchar r/g/b |
| AC-3.3 | 2.2 | Loop over `range(radar.nsweeps)` |
| AC-3.4 | 2.2 | Valid mask filtering (not masked AND >= -30 dBZ) |
| AC-3.5 | 2.2 | `antenna_vectors_to_cartesian()` for earth curvature |
| AC-3.6 | 2.3 | Exact NWS color table with vectorized lookup |
| AC-3.7 | 2.2 | Active storm produces >100K valid gates |
| AC-3.8 | 2.2 | Clear air filtering produces <10K valid gates |
| AC-3.9 | 2.1 | sys.exit(0/1) |
| AC-3.10 | 2.1 | File-not-found / parse-error handling |
| AC-3.11 | 2.1 | argparse `--help` |
| AC-3.12 | 2.1 | Print vertex count on success |
| AC-3.13 | 2.2 | Py-ART range data = gate centers; az/el = beam center |
| AC-4.1 | 3.1 | index.html served by dev server |
| AC-4.2 | 3.2 | File picker + URL param `?ply=` |
| AC-4.3 | 3.2 | Three.js Points with vertexColors |
| AC-4.4 | 3.2 | OrbitControls left-drag = orbit |
| AC-4.5 | 3.2 | OrbitControls scroll = zoom |
| AC-4.6 | 3.2 | OrbitControls right/shift-drag = pan |
| AC-5.1 | 5.1 | End-to-end: fetch → transform → view |
| AC-5.2 | 5.1 | Visual confirmation of layered tilts |

---

## IT ↔ Step Traceability Matrix

| IT | Steps exercised | Automation |
|----|----------------|------------|
| IT-1 | 0, 1 | `validate-test.sh` — fully automated |
| IT-2 | 0, 1, 2 | `validate-test.sh` — fully automated |
| IT-3 | 0, 1, 2 | `validate-test.sh` — fully automated |
| IT-4 | 0, 3 | `validate-test.sh` — needs headless browser or manual |
| IT-5 | 0, 1, 2, 3 | `validate-test.sh` — partial (fetch+transform auto, viewer manual) |
| IT-6 | 0, 1 | `validate-test.sh` — fully automated |
| IT-7 | 0, 2 | `validate-test.sh` — fully automated |

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| **Py-ART API changes** | Pin `arm-pyart>=1.18` in pyproject.toml; code references specific API paths documented in PYART_API_REFERENCE.md |
| **S3 network failures during tests** | validate-test.sh caches downloaded files; if cache exists, skip re-download |
| **Large PLY files (>15MB ASCII)** | Default to ASCII for v1 simplicity; `--format binary_little_endian` available as escape hatch |
| **Three.js importmap not working** | Fallback: use a CDN import (`https://unpkg.com/three@0.170.0/build/three.module.js`) or bundle with vite |
| **Clear air scan might have >10K points** | The -30 dBZ threshold is conservative; if needed, raise to -20 dBZ. KLSX 2024-05-01 is a known calm day. |
| **Gate center accuracy** | Document in code that Py-ART `range['data']` gives gate centers; add a code comment citing AC-3.13 |
| **Browser testing in CI** | IT-4/IT-5 UI evidence marked as requiring headless browser; provide Playwright/Puppeteer instructions as fallback |

---

## Files Created / Modified by This Plan

| File | Action | Purpose |
|------|--------|---------|
| `.envrc` | Create | direnv environment activation |
| `pyproject.toml` | Create | Python project config with deps |
| `src/nexrad_fetch/__init__.py` | Create | Package init |
| `src/nexrad_fetch/cli.py` | Create | Fetch CLI entry point |
| `src/nexrad_fetch/fetch.py` | Create | S3 listing/download logic |
| `src/nexrad_transform/__init__.py` | Create | Package init |
| `src/nexrad_transform/cli.py` | Create | Transform CLI entry point |
| `src/nexrad_transform/transform.py` | Create | Level II → PLY conversion |
| `src/nexrad_transform/colors.py` | Create | NWS color table + vectorized lookup |
| `src/nexrad_transform/ply_writer.py` | Create | PLY file writer (ASCII + binary) |
| `viewer/package.json` | Create | JS deps |
| `viewer/index.html` | Create | Viewer web page |
| `viewer/main.js` | Create | Three.js renderer |
| `scripts/validate-build.sh` | Create | Build validation |
| `scripts/validate-fmt.sh` | Create | Format validation |
| `scripts/validate-test.sh` | Create | Integration tests + evidence |
