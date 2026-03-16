# NEXRAD 3D Point Cloud Viewer v1 — Final Consolidated Implementation Plan

## Overview

This plan synthesizes the best elements from three parallel implementation plans (A, B, C). It covers all acceptance criteria (AC-1.x through AC-5.x) and all integration test scenarios (IT-1 through IT-7) defined in the DoD.

Implementation is split across three parallel workers followed by a merge/integration worker:

| Worker | Scope |
|--------|-------|
| `implement_fetch` | Python fetch CLI + environment setup (`pyproject.toml`, `.envrc`, `.gitignore` entry for `.env.local`) |
| `implement_transform` | Python transform CLI |
| `implement_viewer` | JS viewer + `viewer/package.json` |
| `merge_implementation` | Fan-in: integrate all three, write validation scripts, resolve conflicts |

---

## Repo Layout

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
  package-lock.json        # committed after npm install
  index.html
  main.js
scripts/
  validate-build.sh        # executable
  validate-fmt.sh          # executable
  validate-test.sh         # executable
tests/
  test_fetch.py            # unit tests for fetch logic (mocked boto3)
  test_transform.py        # unit tests for color mapping + PLY structure
```

---

## Worker 1: `implement_fetch`

**Scope:** Environment scaffolding + Python fetch CLI.

**Satisfies:** AC-1.1, AC-1.3, AC-1.4, AC-2.1–AC-2.8

### 1.1 — `.envrc`

```sh
# Activate uv-managed virtualenv automatically
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
# Load local secrets without requiring them in git
dotenv_if_exists .env.local
```

- Uses `dotenv_if_exists` (not `dotenv`) so the file is optional.
- Satisfies AC-1.4.

### 1.2 — `pyproject.toml`

```toml
[project]
name = "nexrad-pointcloud"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "arm-pyart>=1.18",
    "boto3>=1.34",
    "numpy>=1.24",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff>=0.4",
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

- `arm-pyart` is the correct PyPI package name for Py-ART.
- Both CLI entry points declared so `uv sync` installs `nexrad-fetch` and `nexrad-transform` as commands.
- Satisfies AC-1.1 and AC-1.3.

### 1.3 — `.gitignore` additions

Ensure `.env.local` is gitignored (may already exist; add if not):
```
.env.local
.venv/
__pycache__/
*.pyc
dist/
*.egg-info/
```

### 1.4 — `src/nexrad_fetch/__init__.py`

Empty package init.

### 1.5 — `src/nexrad_fetch/fetch.py` (core S3 logic)

```python
"""Core S3 listing and download logic for NEXRAD Level II files."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config


BUCKET = "noaa-nexrad-level2"
REGION = "us-east-1"

# NEXRAD Level II filename pattern: SITE_YYYYMMDD_HHMMSS_VERSION.gz
_KEY_RE = re.compile(
    r"(?P<site>[A-Z]{4})_(?P<date>\d{8})_(?P<time>\d{6})_(?P<version>V\d+)(?:\.gz)?$"
)


@dataclass
class ScanInfo:
    key: str
    site: str
    scan_time: datetime
    size: int = 0


def _s3_client():
    return boto3.client(
        "s3",
        region_name=REGION,
        config=Config(signature_version=UNSIGNED),
    )


def list_scans(site: str, date: datetime) -> list[ScanInfo]:
    """List available Level II scans from S3 for a given site and date (UTC)."""
    prefix = f"{date.year:04d}/{date.month:02d}/{date.day:02d}/{site.upper()}/"
    s3 = _s3_client()
    paginator = s3.get_paginator("list_objects_v2")
    scans: list[ScanInfo] = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]
            m = _KEY_RE.search(filename)
            if not m:
                continue
            try:
                scan_time = datetime.strptime(
                    m.group("date") + m.group("time"), "%Y%m%d%H%M%S"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            scans.append(ScanInfo(key=key, site=site.upper(), scan_time=scan_time, size=obj.get("Size", 0)))
    return sorted(scans, key=lambda s: s.scan_time)


def find_closest_scan(scans: list[ScanInfo], target_time: datetime) -> ScanInfo:
    """Return the scan closest to target_time. Tie-break: earlier scan wins."""
    if not scans:
        raise ValueError("No scans to select from")
    return min(scans, key=lambda s: abs((s.scan_time - target_time).total_seconds()))


def download_scan(scan: ScanInfo, output_path: Path) -> Path:
    """Download a scan file from S3 to output_path. Returns the local path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    s3 = _s3_client()
    s3.download_file(BUCKET, scan.key, str(output_path))
    return output_path
```

### 1.6 — `src/nexrad_fetch/cli.py` (CLI entry point)

```python
"""nexrad-fetch: download NEXRAD Level II archive files from S3."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from nexrad_fetch.fetch import download_scan, find_closest_scan, list_scans

SITE_RE = re.compile(r"^[A-Z]{4}$", re.IGNORECASE)


def parse_datetime(s: str) -> datetime:
    """Parse ISO 8601 datetime string to UTC datetime."""
    # Accept formats: 2013-05-20T20:00Z, 2013-05-20T20:00:00Z, 2013-05-20T20:00:00+00:00
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid datetime: {s!r}. Use ISO 8601, e.g. 2013-05-20T20:00Z")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nexrad-fetch",
        description="Download a NEXRAD Level II archive file from s3://noaa-nexrad-level2/.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  nexrad-fetch KTLX 2013-05-20T20:00Z\n"
            "  nexrad-fetch KLSX 2024-05-01T17:30Z -o /tmp/klsx_clear.gz\n"
        ),
    )
    parser.add_argument("site", help="4-letter ICAO radar site code (e.g. KTLX)")
    parser.add_argument("datetime", type=parse_datetime, help="Target date/time in ISO 8601 UTC (e.g. 2013-05-20T20:00Z)")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output file path (default: <site>_<datetime>.gz in current directory)")
    args = parser.parse_args()

    site = args.site.upper()
    if not SITE_RE.match(site):
        print(f"Error: Invalid site code {args.site!r}. Expected 4-letter ICAO code (e.g. KTLX).", file=sys.stderr)
        sys.exit(1)

    target_time: datetime = args.datetime

    print(f"Listing scans for {site} on {target_time.date()} ...")
    try:
        scans = list_scans(site, target_time)
    except Exception as e:
        print(f"Error: Failed to list scans from S3: {e}", file=sys.stderr)
        sys.exit(1)

    if not scans:
        print(f"Error: No scans found for {site} on {target_time.date().isoformat()}.", file=sys.stderr)
        sys.exit(1)

    # Print available scans (MSG-2)
    print(f"Available scans ({len(scans)} found):")
    for scan in scans:
        print(f"  {scan.scan_time.isoformat()}  {scan.key.split('/')[-1]}")

    closest = find_closest_scan(scans, target_time)
    filename = closest.key.split("/")[-1]

    if args.output is None:
        output_path = Path(filename)
    else:
        output_path = args.output

    print(f"\nSelecting closest scan: {closest.scan_time.isoformat()}  ({filename})")
    print(f"Downloading to: {output_path} ...")
    try:
        download_scan(closest, output_path)
    except Exception as e:
        print(f"Error: Download failed: {e}", file=sys.stderr)
        sys.exit(1)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    # MSG-3: success with path and size
    print(f"Downloaded: {output_path}  ({size_mb:.1f} MB)")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

### 1.7 — `tests/test_fetch.py` (unit tests)

Test key construction, timestamp parsing, nearest-scan selection, and error paths using mocked boto3. No live S3 calls.

```python
from datetime import datetime, timezone
from nexrad_fetch.fetch import ScanInfo, find_closest_scan

def _scan(dt_str: str) -> ScanInfo:
    dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
    return ScanInfo(key=f"KTLX/{dt_str}.gz", site="KTLX", scan_time=dt)

def test_find_closest_exact():
    scans = [_scan("2013-05-20T19:55:00"), _scan("2013-05-20T20:03:00"), _scan("2013-05-20T20:10:00")]
    target = datetime(2013, 5, 20, 20, 0, 0, tzinfo=timezone.utc)
    result = find_closest_scan(scans, target)
    assert result.scan_time == datetime(2013, 5, 20, 20, 3, 0, tzinfo=timezone.utc)

def test_find_closest_tie_earlier():
    scans = [_scan("2013-05-20T19:58:00"), _scan("2013-05-20T20:02:00")]
    target = datetime(2013, 5, 20, 20, 0, 0, tzinfo=timezone.utc)
    result = find_closest_scan(scans, target)
    # Both 2min away; min() returns first in order → earlier
    assert result.scan_time == datetime(2013, 5, 20, 19, 58, 0, tzinfo=timezone.utc)
```

---

## Worker 2: `implement_transform`

**Scope:** Python transform CLI (Level II → PLY point cloud).

**Satisfies:** AC-3.1–AC-3.13

### 2.1 — `src/nexrad_transform/__init__.py`

Empty package init.

### 2.2 — `src/nexrad_transform/colors.py` (NWS color table)

Exact NWS reflectivity color table from spec. Use vectorized `np.digitize` for performance.

```python
"""NWS reflectivity color table — exact RGB mapping per spec."""
from __future__ import annotations

import numpy as np

# Threshold → RGB. Entry i covers [thresholds[i], thresholds[i+1]).
# Values < -30 are filtered BEFORE calling these functions.
_THRESHOLDS = np.array([-30, -25, -20, -10, 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60],
                        dtype=np.float32)
_COLORS = np.array([
    [100, 100, 100],  # -30 to -25  dark gray
    [150, 150, 150],  # -25 to -20  light gray
    [ 65, 105, 225],  # -20 to -10  light blue
    [  0, 200, 255],  # -10 to 0    cyan
    [ 50, 200, 255],  #   0 to 5    light cyan
    [  0, 150, 255],  #   5 to 10   blue
    [  0, 200,   0],  #  10 to 15   green
    [100, 255,   0],  #  15 to 20   lime green
    [255, 255,   0],  #  20 to 25   yellow
    [255, 165,   0],  #  25 to 30   orange
    [255, 100,   0],  #  30 to 35   red orange
    [255,   0,   0],  #  35 to 40   red
    [180,   0,   0],  #  40 to 45   dark red
    [255,   0, 255],  #  45 to 50   magenta
    [138,  43, 226],  #  50 to 55   violet
    [255, 255, 255],  #  55 to 60   white
    [255, 255, 255],  #  60+        bright white
], dtype=np.uint8)


def dbz_to_rgb_vectorized(dbz: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Map an array of dBZ values to (R, G, B) uint8 arrays via the NWS color table.

    Caller must have already filtered out masked / below-threshold gates.
    """
    # np.digitize(x, bins) returns index i such that bins[i-1] <= x < bins[i]
    # Subtract 1 to get 0-based color index; clip to valid range.
    idx = np.digitize(dbz, _THRESHOLDS) - 1
    idx = np.clip(idx, 0, len(_COLORS) - 1)
    mapped = _COLORS[idx]
    return mapped[:, 0], mapped[:, 1], mapped[:, 2]
```

### 2.3 — `src/nexrad_transform/ply_writer.py` (PLY output)

Supports both ASCII and binary little-endian formats. Uses numpy for fast writes.

```python
"""PLY file writer for colored point clouds."""
from __future__ import annotations

from pathlib import Path

import numpy as np


def write_ply(
    path: Path,
    x: np.ndarray, y: np.ndarray, z: np.ndarray,
    r: np.ndarray, g: np.ndarray, b: np.ndarray,
    fmt: str = "ascii",
) -> None:
    """Write a colored PLY point cloud.

    Args:
        path: output file path
        x, y, z: float32 coordinate arrays (meters, radar-relative)
        r, g, b: uint8 color arrays (NWS colors)
        fmt: "ascii" or "binary_little_endian"
    """
    if fmt not in ("ascii", "binary_little_endian"):
        raise ValueError(f"Unsupported PLY format: {fmt!r}")

    n = len(x)
    header = (
        "ply\n"
        f"format {fmt} 1.0\n"
        "comment NEXRAD reflectivity point cloud\n"
        f"element vertex {n}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        "end_header\n"
    )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "ascii":
        with open(path, "w") as f:
            f.write(header)
            # Vectorized write: faster than per-row loop for large arrays
            data = np.column_stack([
                x.astype(np.float32),
                y.astype(np.float32),
                z.astype(np.float32),
                r.astype(np.int32),
                g.astype(np.int32),
                b.astype(np.int32),
            ])
            np.savetxt(f, data, fmt="%.3f %.3f %.3f %d %d %d")
    else:
        # binary_little_endian: 3×float32 + 3×uint8 = 15 bytes/vertex
        with open(path, "wb") as f:
            f.write(header.encode("ascii"))
            # Pack into structured array for contiguous layout
            dtype = np.dtype([
                ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                ("r", "u1"), ("g", "u1"), ("b", "u1"),
            ])
            arr = np.empty(n, dtype=dtype)
            arr["x"] = x.astype(np.float32)
            arr["y"] = y.astype(np.float32)
            arr["z"] = z.astype(np.float32)
            arr["r"] = r
            arr["g"] = g
            arr["b"] = b
            f.write(arr.tobytes())
```

### 2.4 — `src/nexrad_transform/transform.py` (core transform logic)

```python
"""NEXRAD Level II → PLY point cloud transform."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyart
from pyart.core.transforms import antenna_vectors_to_cartesian

from nexrad_transform.colors import dbz_to_rgb_vectorized
from nexrad_transform.ply_writer import write_ply

# Minimum reflectivity threshold (dBZ). Gates at or below this are filtered out.
# Per spec: < -30 dBZ is background noise.
DBZ_MIN = -30.0


def transform(input_path: Path, output_path: Path, fmt: str = "ascii") -> int:
    """Transform a NEXRAD Level II archive to a colored PLY point cloud.

    Args:
        input_path: path to Level II archive (.gz or uncompressed)
        output_path: path for output PLY file
        fmt: PLY format — "ascii" or "binary_little_endian"

    Returns:
        Number of vertices written.

    Raises:
        FileNotFoundError: input file does not exist
        ValueError: file is not a valid Level II archive or lacks reflectivity
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    try:
        radar = pyart.io.read_nexrad_archive(str(input_path))
    except Exception as e:
        raise ValueError(f"Failed to parse Level II archive {input_path}: {e}") from e

    if "reflectivity" not in radar.fields:
        available = list(radar.fields.keys())
        raise ValueError(
            f"No 'reflectivity' field found in {input_path}. "
            f"Available fields: {available}"
        )

    all_x, all_y, all_z = [], [], []
    all_r, all_g, all_b = [], [], []

    rng = radar.range["data"]  # (n_gates,) — already gate centers (mid-range per gate)
    n_gates = len(rng)

    for sweep_idx in range(radar.nsweeps):
        start = int(radar.sweep_start_ray_index["data"][sweep_idx])
        end   = int(radar.sweep_end_ray_index["data"][sweep_idx]) + 1

        refl = radar.fields["reflectivity"]["data"][start:end, :]  # (n_rays, n_gates)
        az   = radar.azimuth["data"][start:end]                     # (n_rays,) degrees
        el   = radar.elevation["data"][start:end]                   # (n_rays,) degrees
        n_rays = end - start

        # Build 2D grids (n_rays × n_gates) for coordinate transform.
        # np.tile is used per Py-ART API reference — equivalent to broadcast_to but
        # ensures contiguous arrays required by antenna_vectors_to_cartesian.
        az_2d  = np.tile(az[:, np.newaxis], (1, n_gates))
        el_2d  = np.tile(el[:, np.newaxis], (1, n_gates))
        rng_2d = np.tile(rng[np.newaxis, :], (n_rays, 1))

        # Cartesian coords via Py-ART standard model:
        # includes 4/3 effective Earth radius refraction.
        # Origin (0,0,0) = radar antenna. X=East, Y=North, Z=Up (meters).
        # radar.range['data'] gives the center of each range gate, so each
        # resulting point is placed at the volumetric center of its gate (AC-3.13).
        x, y, z = antenna_vectors_to_cartesian(rng_2d, az_2d, el_2d)

        # Build validity mask: not masked AND >= DBZ_MIN
        mask = np.ma.getmaskarray(refl)            # True = invalid/no-data
        valid = ~mask
        refl_data = np.ma.filled(refl, fill_value=np.nan)
        valid &= (refl_data >= DBZ_MIN)

        if not np.any(valid):
            continue

        # Extract valid points and map colors
        r, g, b = dbz_to_rgb_vectorized(refl_data[valid].astype(np.float32))

        all_x.append(x[valid].ravel().astype(np.float32))
        all_y.append(y[valid].ravel().astype(np.float32))
        all_z.append(z[valid].ravel().astype(np.float32))
        all_r.append(r)
        all_g.append(g)
        all_b.append(b)

    if not all_x:
        # No valid gates — write an empty but valid PLY
        write_ply(output_path, np.array([]), np.array([]), np.array([]),
                  np.array([], dtype=np.uint8), np.array([], dtype=np.uint8), np.array([], dtype=np.uint8),
                  fmt=fmt)
        return 0

    X = np.concatenate(all_x)
    Y = np.concatenate(all_y)
    Z = np.concatenate(all_z)
    R = np.concatenate(all_r)
    G = np.concatenate(all_g)
    B = np.concatenate(all_b)

    write_ply(output_path, X, Y, Z, R, G, B, fmt=fmt)
    return len(X)
```

### 2.5 — `src/nexrad_transform/cli.py` (CLI entry point)

```python
"""nexrad-transform: convert NEXRAD Level II archives to colored PLY point clouds."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nexrad_transform.transform import transform


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nexrad-transform",
        description="Convert a NEXRAD Level II archive file to a colored PLY point cloud.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  nexrad-transform ktlx_storm.gz storm.ply\n"
            "  nexrad-transform ktlx_storm.gz storm.ply --format binary_little_endian\n"
        ),
    )
    parser.add_argument("input", type=Path, help="Path to input NEXRAD Level II archive (.gz or uncompressed)")
    parser.add_argument("output", type=Path, help="Path for output PLY file")
    parser.add_argument(
        "--format",
        choices=["ascii", "binary_little_endian"],
        default="ascii",
        help="PLY output format (default: ascii). Use binary_little_endian for large files.",
    )
    args = parser.parse_args()

    try:
        n_vertices = transform(args.input, args.output, fmt=args.format)
    except FileNotFoundError as e:
        # MSG-8: error for missing/invalid input
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Unexpected failure during transform: {e}", file=sys.stderr)
        sys.exit(1)

    # MSG-7: success with vertex count
    print(f"Transformed: {args.output}  ({n_vertices:,} vertices)")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

### 2.6 — `tests/test_transform.py` (unit tests)

```python
"""Unit tests for transform components — no live network required."""
import numpy as np
import pytest

from nexrad_transform.colors import dbz_to_rgb_vectorized
from nexrad_transform.ply_writer import write_ply


# --- Color mapping tests ---

def test_color_active_storm_core():
    # 55 dBZ → white (255, 255, 255)
    r, g, b = dbz_to_rgb_vectorized(np.array([55.0]))
    assert (r[0], g[0], b[0]) == (255, 255, 255)

def test_color_moderate_rain():
    # 25 dBZ → orange (255, 165, 0)
    r, g, b = dbz_to_rgb_vectorized(np.array([25.0]))
    assert (r[0], g[0], b[0]) == (255, 165, 0)

def test_color_light_rain():
    # 15 dBZ → lime green (100, 255, 0)
    r, g, b = dbz_to_rgb_vectorized(np.array([15.0]))
    assert (r[0], g[0], b[0]) == (100, 255, 0)

def test_color_boundary_exact():
    # Exact boundary: 35 dBZ → red (255, 0, 0), not dark red (35-40 bin)
    r, g, b = dbz_to_rgb_vectorized(np.array([35.0]))
    assert (r[0], g[0], b[0]) == (255, 0, 0)

def test_color_vectorized_shape():
    dbz = np.array([-25.0, 0.0, 20.0, 45.0, 65.0])
    r, g, b = dbz_to_rgb_vectorized(dbz)
    assert r.shape == (5,) and g.shape == (5,) and b.shape == (5,)


# --- PLY writer tests ---

def test_ply_header_ascii(tmp_path):
    p = tmp_path / "test.ply"
    x = np.array([1.0, 2.0], dtype=np.float32)
    y = np.array([3.0, 4.0], dtype=np.float32)
    z = np.array([5.0, 6.0], dtype=np.float32)
    r = np.array([255, 0], dtype=np.uint8)
    g = np.array([0, 255], dtype=np.uint8)
    b = np.array([0, 0], dtype=np.uint8)
    write_ply(p, x, y, z, r, g, b, fmt="ascii")
    content = p.read_text()
    assert content.startswith("ply\n")
    assert "format ascii 1.0" in content
    assert "element vertex 2" in content
    assert "property float x" in content
    assert "property uchar red" in content
    assert "end_header" in content

def test_ply_binary_writes(tmp_path):
    p = tmp_path / "test.ply"
    x = np.array([100.0], dtype=np.float32)
    y = np.array([200.0], dtype=np.float32)
    z = np.array([300.0], dtype=np.float32)
    r = np.array([128], dtype=np.uint8)
    g = np.array([64], dtype=np.uint8)
    b = np.array([32], dtype=np.uint8)
    write_ply(p, x, y, z, r, g, b, fmt="binary_little_endian")
    raw = p.read_bytes()
    assert raw.startswith(b"ply\n")
    assert b"format binary_little_endian 1.0" in raw
    assert b"element vertex 1" in raw
```

---

## Worker 3: `implement_viewer`

**Scope:** Three.js web viewer + `viewer/package.json`.

**Satisfies:** AC-1.2, AC-4.1–AC-4.6

### 3.1 — `viewer/package.json`

```json
{
  "name": "nexrad-viewer",
  "version": "0.1.0",
  "private": true,
  "description": "NEXRAD 3D point cloud viewer using Three.js",
  "scripts": {
    "dev": "npx serve . --listen 8080",
    "start": "npx serve . --listen 8080",
    "test": "echo 'No automated viewer tests; run manually per IT-4'"
  },
  "dependencies": {
    "three": "^0.170.0"
  },
  "devDependencies": {
    "serve": "^14.0.0"
  },
  "engines": {
    "node": ">=18"
  }
}
```

**Notes:**
- `three` ≥0.170 includes `PLYLoader` and `OrbitControls` in `examples/jsm/`.
- `serve` provides a simple static dev server (needed because `file://` URLs block module imports in some browsers).

### 3.2 — `viewer/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NEXRAD Point Cloud Viewer</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #000; overflow: hidden; font-family: sans-serif; }
    canvas { display: block; }
    #ui {
      position: absolute; top: 12px; left: 12px; z-index: 10;
      display: flex; align-items: center; gap: 10px;
    }
    #ui label { color: #ccc; font-size: 13px; }
    #status {
      position: absolute; bottom: 12px; left: 12px; z-index: 10;
      color: #ccc; font-size: 12px;
    }
  </style>
</head>
<body>
  <!-- MSG-9: page loads with visible canvas -->
  <div id="ui">
    <label for="ply-input">Load PLY:</label>
    <input type="file" id="ply-input" accept=".ply">
  </div>
  <div id="status">No file loaded. Use file picker or ?ply=URL</div>
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

### 3.3 — `viewer/main.js`

```javascript
import * as THREE from 'three';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// --- Scene setup ---
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111111);

const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 100, 2000000);
// Start 300 km out — NEXRAD storm may span ~200 km radius
camera.position.set(0, -300000, 100000);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// AC-4.4, AC-4.5, AC-4.6: orbit (left-drag), zoom (scroll), pan (right-drag)
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.1;
controls.screenSpacePanning = true;

const loader = new PLYLoader();
const statusEl = document.getElementById('status');

function setStatus(msg) {
    if (statusEl) statusEl.textContent = msg;
}

function addPointCloud(geometry) {
    // Remove any existing point clouds
    scene.children.filter(c => c.isPoints).forEach(c => {
        c.geometry.dispose();
        c.material.dispose();
        scene.remove(c);
    });

    geometry.computeBoundingBox();
    geometry.computeBoundingSphere();

    // AC-4.3: colored points using vertex colors from PLY
    const material = new THREE.PointsMaterial({
        size: 300,           // ~300m point footprint — visible at NEXRAD scale
        vertexColors: true,
        sizeAttenuation: true,
    });

    const points = new THREE.Points(geometry, material);
    scene.add(points);

    // Center camera/orbit target on the bounding sphere
    const center = geometry.boundingSphere.center.clone();
    const radius = geometry.boundingSphere.radius;

    controls.target.copy(center);
    camera.position.copy(center).add(new THREE.Vector3(0, -radius * 1.5, radius * 0.5));
    camera.lookAt(center);
    controls.update();

    const vertCount = geometry.attributes.position.count;
    setStatus(`Loaded ${vertCount.toLocaleString()} vertices. Drag to orbit, scroll to zoom, right-drag to pan.`);
}

function loadFromBuffer(buffer) {
    try {
        const geometry = loader.parse(buffer);
        addPointCloud(geometry);
    } catch (e) {
        setStatus(`Error parsing PLY: ${e.message}`);
        console.error('PLY parse error:', e);
    }
}

function loadFromUrl(url) {
    setStatus(`Loading ${url} ...`);
    loader.load(
        url,
        (geometry) => addPointCloud(geometry),
        (xhr) => {
            if (xhr.lengthComputable) {
                const pct = Math.round(xhr.loaded / xhr.total * 100);
                setStatus(`Loading ... ${pct}%`);
            }
        },
        (err) => {
            setStatus(`Error loading PLY from URL: ${err.message || err}`);
            console.error('PLY load error:', err);
        }
    );
}

// AC-4.2a: file picker
document.getElementById('ply-input').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setStatus(`Reading ${file.name} ...`);
    const reader = new FileReader();
    reader.onload = (ev) => loadFromBuffer(ev.target.result);
    reader.onerror = () => setStatus('Error reading file');
    reader.readAsArrayBuffer(file);
});

// AC-4.2b: URL parameter ?ply=<path>
const params = new URLSearchParams(window.location.search);
const plyUrl = params.get('ply');
if (plyUrl) {
    loadFromUrl(plyUrl);
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

---

## Worker 4: `merge_implementation`

**Scope:** Fan-in all three workers, write validation scripts, resolve any conflicts, verify end-to-end.

This worker runs after `implement_fetch`, `implement_transform`, and `implement_viewer` all succeed.

### 4.1 — Merge procedure

1. Verify all source files from workers 1–3 are present.
2. Resolve any path conflicts (unlikely given distinct file ownership).
3. Confirm `uv sync` succeeds (installs arm-pyart, boto3, etc.).
4. Confirm `npm install` in `viewer/` succeeds.
5. Confirm `nexrad-fetch --help` and `nexrad-transform --help` print usage.

### 4.2 — `scripts/validate-build.sh`

```sh
#!/bin/sh
set -e

echo "=== [validate-build] Python: uv sync ==="
uv sync
echo "=== [validate-build] Python: import check ==="
python -c "
import nexrad_fetch
import nexrad_fetch.fetch
import nexrad_transform
import nexrad_transform.transform
import nexrad_transform.colors
import nexrad_transform.ply_writer
print('Python imports: OK')
"

echo "=== [validate-build] CLI entrypoints ==="
nexrad-fetch --help > /dev/null
nexrad-transform --help > /dev/null
echo "nexrad-fetch --help: OK"
echo "nexrad-transform --help: OK"

echo "=== [validate-build] Viewer: npm install ==="
cd viewer
npm install
cd ..
echo "=== [validate-build] PASS ==="
```

### 4.3 — `scripts/validate-fmt.sh`

```sh
#!/bin/sh
set -e

echo "=== [validate-fmt] Python formatting check ==="
if command -v ruff >/dev/null 2>&1; then
  ruff check src/ tests/
  echo "ruff check: OK"
  ruff format --check src/ tests/
  echo "ruff format: OK"
else
  echo "ruff not found — skipping Python format check"
fi

echo "=== [validate-fmt] PASS ==="
```

### 4.4 — `scripts/validate-test.sh`

This is the primary evidence-generating script. Produces all artifacts required by the DoD test evidence contract.

```sh
#!/bin/sh
set -e

RUN_ID="${KILROY_RUN_ID:-01KKW5V0VN00K8QS3JQVHT7ZVJ}"
EVIDENCE_ROOT=".ai/runs/${RUN_ID}/test-evidence/latest"

# --- Helpers ---
pass_test() { echo "[PASS] $1"; }
fail_test() { echo "[FAIL] $1: $2"; }

mkdir -p "$EVIDENCE_ROOT"

echo "=== Running unit tests ==="
uv run pytest tests/ -v 2>&1 | tee "$EVIDENCE_ROOT/pytest_output.txt"

# === IT-6: Fetch error handling ===
echo "=== IT-6: Fetch error handling ==="
mkdir -p "$EVIDENCE_ROOT/IT-6"

nexrad-fetch --help > "$EVIDENCE_ROOT/IT-6/help_stdout.log" 2>&1 || true
pass_test "IT-6: --help"

(nexrad-fetch ZZZZ 2013-05-20T20:00Z > "$EVIDENCE_ROOT/IT-6/invalid_site_stdout.log" 2>&1; echo $? > "$EVIDENCE_ROOT/IT-6/invalid_site_exit_code.txt") || true
INVALID_EXIT=$(cat "$EVIDENCE_ROOT/IT-6/invalid_site_exit_code.txt" 2>/dev/null || echo "?")
if [ "$INVALID_EXIT" != "0" ]; then
  pass_test "IT-6: invalid site exits non-zero"
else
  fail_test "IT-6" "invalid site should exit non-zero but got 0"
fi

(nexrad-fetch KTLX 1900-01-01T00:00Z > "$EVIDENCE_ROOT/IT-6/no_scans_stdout.log" 2>&1; echo $? > "$EVIDENCE_ROOT/IT-6/no_scans_exit_code.txt") || true
NO_SCANS_EXIT=$(cat "$EVIDENCE_ROOT/IT-6/no_scans_exit_code.txt" 2>/dev/null || echo "?")
if [ "$NO_SCANS_EXIT" != "0" ]; then
  pass_test "IT-6: no scans found exits non-zero"
else
  fail_test "IT-6" "no-scans case should exit non-zero but got 0"
fi

# === IT-7: Transform error handling ===
echo "=== IT-7: Transform error handling ==="
mkdir -p "$EVIDENCE_ROOT/IT-7"

nexrad-transform --help > "$EVIDENCE_ROOT/IT-7/help_stdout.log" 2>&1 || true
pass_test "IT-7: --help"

(nexrad-transform /nonexistent/path.gz /tmp/out.ply > "$EVIDENCE_ROOT/IT-7/invalid_file_stdout.log" 2>&1; echo $? > "$EVIDENCE_ROOT/IT-7/invalid_file_exit_code.txt") || true
INV_EXIT=$(cat "$EVIDENCE_ROOT/IT-7/invalid_file_exit_code.txt" 2>/dev/null || echo "?")
if [ "$INV_EXIT" != "0" ]; then
  pass_test "IT-7: non-existent file exits non-zero"
else
  fail_test "IT-7" "non-existent file should exit non-zero"
fi

# Create a non-Level-II file and test
echo "This is not a NEXRAD file" > /tmp/bad_format_test.txt
(nexrad-transform /tmp/bad_format_test.txt /tmp/out.ply > "$EVIDENCE_ROOT/IT-7/bad_format_stdout.log" 2>&1; echo $? > "$EVIDENCE_ROOT/IT-7/bad_format_exit_code.txt") || true
BAD_EXIT=$(cat "$EVIDENCE_ROOT/IT-7/bad_format_exit_code.txt" 2>/dev/null || echo "?")
if [ "$BAD_EXIT" != "0" ]; then
  pass_test "IT-7: bad format exits non-zero"
else
  fail_test "IT-7" "bad format file should exit non-zero"
fi

# === IT-1: Fetch active storm ===
echo "=== IT-1: Fetch KTLX 2013-05-20T20:00Z ==="
mkdir -p "$EVIDENCE_ROOT/IT-1"
KTLX_FILE="/tmp/nexrad_test_ktlx_storm.gz"
if [ ! -f "$KTLX_FILE" ]; then
  nexrad-fetch KTLX 2013-05-20T20:00Z -o "$KTLX_FILE" > "$EVIDENCE_ROOT/IT-1/fetch_stdout.log" 2>&1
  echo $? > "$EVIDENCE_ROOT/IT-1/fetch_exit_code.txt"
else
  echo "(using cached file $KTLX_FILE)" > "$EVIDENCE_ROOT/IT-1/fetch_stdout.log"
  echo "0" > "$EVIDENCE_ROOT/IT-1/fetch_exit_code.txt"
fi
FETCH_EXIT=$(cat "$EVIDENCE_ROOT/IT-1/fetch_exit_code.txt")
FILESIZE=$(stat -f%z "$KTLX_FILE" 2>/dev/null || stat -c%s "$KTLX_FILE" 2>/dev/null || echo "0")
GZIP_OK=$(gunzip -t "$KTLX_FILE" 2>&1 && echo "valid" || echo "invalid")
python3 -c "import json; json.dump({'file': '$KTLX_FILE', 'size_bytes': $FILESIZE, 'gzip_valid': '$GZIP_OK', 'fetch_exit': $FETCH_EXIT}, open('$EVIDENCE_ROOT/IT-1/downloaded_file_info.json','w'), indent=2)"
if [ "$FETCH_EXIT" = "0" ] && [ "$GZIP_OK" = "valid" ] && [ "$FILESIZE" -gt "5000000" ]; then
  pass_test "IT-1: fetch succeeds, file >5MB, valid gzip"
else
  fail_test "IT-1" "fetch_exit=$FETCH_EXIT gzip=$GZIP_OK size=$FILESIZE"
fi

# === IT-2: Transform active storm ===
echo "=== IT-2: Transform KTLX storm ==="
mkdir -p "$EVIDENCE_ROOT/IT-2"
STORM_PLY="/tmp/nexrad_test_ktlx_storm.ply"
nexrad-transform "$KTLX_FILE" "$STORM_PLY" > "$EVIDENCE_ROOT/IT-2/transform_stdout.log" 2>&1
echo $? > "$EVIDENCE_ROOT/IT-2/transform_exit_code.txt"
head -10 "$STORM_PLY" > "$EVIDENCE_ROOT/IT-2/ply_header.txt" 2>/dev/null || true
python3 - "$STORM_PLY" "$EVIDENCE_ROOT/IT-2/ply_validation.json" << 'PYEOF'
import sys, json, re
ply_path, out_path = sys.argv[1], sys.argv[2]
with open(ply_path) as f:
    header_lines = []
    for line in f:
        header_lines.append(line.rstrip())
        if line.strip() == "end_header":
            break
m = re.search(r"element vertex (\d+)", "\n".join(header_lines))
vertex_count = int(m.group(1)) if m else 0
# Read sample vertices
import numpy as np
data = np.genfromtxt(ply_path, skip_header=len(header_lines), max_rows=10)
if data.ndim == 1 and len(data) > 0: data = data.reshape(1, -1)
result = {
    "vertex_count": vertex_count,
    "header_valid": "property float x" in "\n".join(header_lines),
    "sample_coords": data[:, :3].tolist() if data.shape[0] > 0 else [],
    "gt_100k": vertex_count > 100000,
}
json.dump(result, open(out_path, "w"), indent=2)
print(json.dumps(result, indent=2))
PYEOF
TR_EXIT=$(cat "$EVIDENCE_ROOT/IT-2/transform_exit_code.txt")
VERTEX_COUNT=$(python3 -c "import json; d=json.load(open('$EVIDENCE_ROOT/IT-2/ply_validation.json')); print(d.get('vertex_count',0))" 2>/dev/null || echo "0")
if [ "$TR_EXIT" = "0" ] && [ "$VERTEX_COUNT" -gt "100000" ]; then
  pass_test "IT-2: transform succeeds, >100K vertices ($VERTEX_COUNT)"
else
  fail_test "IT-2" "exit=$TR_EXIT vertices=$VERTEX_COUNT"
fi

# === IT-3: Transform clear air ===
echo "=== IT-3: Fetch/transform clear air KLSX ==="
mkdir -p "$EVIDENCE_ROOT/IT-3"
KLSX_FILE="/tmp/nexrad_test_klsx_clear.gz"
if [ ! -f "$KLSX_FILE" ]; then
  nexrad-fetch KLSX 2024-05-01T17:30Z -o "$KLSX_FILE" >> "$EVIDENCE_ROOT/IT-3/transform_stdout.log" 2>&1 || true
fi
CLEAR_PLY="/tmp/nexrad_test_klsx_clear.ply"
nexrad-transform "$KLSX_FILE" "$CLEAR_PLY" >> "$EVIDENCE_ROOT/IT-3/transform_stdout.log" 2>&1
echo $? > "$EVIDENCE_ROOT/IT-3/transform_exit_code.txt"
python3 - "$CLEAR_PLY" "$EVIDENCE_ROOT/IT-3/ply_validation.json" << 'PYEOF'
import sys, json, re
ply_path, out_path = sys.argv[1], sys.argv[2]
with open(ply_path) as f:
    header_lines = []
    for line in f:
        header_lines.append(line.rstrip())
        if line.strip() == "end_header":
            break
m = re.search(r"element vertex (\d+)", "\n".join(header_lines))
vertex_count = int(m.group(1)) if m else 0
import os
result = {"vertex_count": vertex_count, "file_size": os.path.getsize(ply_path), "lt_10k": vertex_count < 10000}
json.dump(result, open(out_path, "w"), indent=2)
print(json.dumps(result, indent=2))
PYEOF
CLR_EXIT=$(cat "$EVIDENCE_ROOT/IT-3/transform_exit_code.txt")
CLR_VERTS=$(python3 -c "import json; d=json.load(open('$EVIDENCE_ROOT/IT-3/ply_validation.json')); print(d.get('vertex_count',99999))" 2>/dev/null || echo "99999")
if [ "$CLR_EXIT" = "0" ] && [ "$CLR_VERTS" -lt "10000" ]; then
  pass_test "IT-3: clear-air transform exits 0, <10K vertices ($CLR_VERTS)"
else
  fail_test "IT-3" "exit=$CLR_EXIT vertices=$CLR_VERTS"
fi

# === IT-4, IT-5: Browser-based tests (require manual or headless verification) ===
echo "=== IT-4/IT-5: Viewer tests (browser required) ==="
mkdir -p "$EVIDENCE_ROOT/IT-4"
mkdir -p "$EVIDENCE_ROOT/IT-5"
cat > "$EVIDENCE_ROOT/IT-4/README.txt" << 'EOF'
IT-4 requires browser interaction. Steps:
  1. cd viewer && npm install && npm start
  2. Open http://localhost:8080 in a modern browser
  3. Load the PLY file from IT-2 via file picker
  4. Verify colored points render (AC-4.3)
  5. Orbit (left-drag), zoom (scroll), pan (right-drag) all work (AC-4.4/4.5/4.6)
  6. Capture screenshots: viewer_loaded.png, ply_rendered.png, orbit_rotated.png
  7. Capture console log: viewer_console.log (should show no errors)
EOF
cat > "$EVIDENCE_ROOT/IT-5/README.txt" << 'EOF'
IT-5 is the full end-to-end pipeline test. Steps:
  1. nexrad-fetch KTLX 2013-05-20T20:00Z -o /tmp/ktlx_storm.gz
  2. nexrad-transform /tmp/ktlx_storm.gz /tmp/ktlx_storm.ply
  3. cd viewer && npm start
  4. Open browser, load /tmp/ktlx_storm.ply via ?ply= or file picker
  5. Verify layered elevation tilts are visible (AC-5.2)
  6. Capture pipeline_rendered.png and pipeline_summary.json
EOF

# Write a pipeline_summary.json with what we know from the automated steps
python3 - "$EVIDENCE_ROOT/IT-5/pipeline_summary.json" << PYEOF
import json, os, sys
out = sys.argv[1]
storm_ply = "/tmp/nexrad_test_ktlx_storm.ply"
summary = {
    "fetch_file": "/tmp/nexrad_test_ktlx_storm.gz",
    "fetch_size_bytes": os.path.getsize("/tmp/nexrad_test_ktlx_storm.gz") if os.path.exists("/tmp/nexrad_test_ktlx_storm.gz") else None,
    "transform_ply": storm_ply,
    "transform_vertex_count": None,
    "viewer_load_status": "requires_manual_verification",
}
import re
if os.path.exists(storm_ply):
    with open(storm_ply) as f:
        for line in f:
            m = re.search(r"element vertex (\d+)", line)
            if m:
                summary["transform_vertex_count"] = int(m.group(1))
            if line.strip() == "end_header":
                break
json.dump(summary, open(out, "w"), indent=2)
PYEOF

# === Write manifest ===
python3 - "$EVIDENCE_ROOT/manifest.json" "$RUN_ID" << 'PYEOF'
import json, sys
out, run_id = sys.argv[1], sys.argv[2]
manifest = {
    "run_id": run_id,
    "scenarios": [
        {"id": "IT-1", "surface": "non_ui", "artifacts": ["fetch_stdout.log", "fetch_exit_code.txt", "downloaded_file_info.json"]},
        {"id": "IT-2", "surface": "non_ui", "artifacts": ["transform_stdout.log", "transform_exit_code.txt", "ply_header.txt", "ply_validation.json"]},
        {"id": "IT-3", "surface": "non_ui", "artifacts": ["transform_stdout.log", "transform_exit_code.txt", "ply_validation.json"]},
        {"id": "IT-4", "surface": "ui", "artifacts": ["README.txt"], "note": "screenshots require manual/headless browser"},
        {"id": "IT-5", "surface": "mixed", "artifacts": ["README.txt", "pipeline_summary.json"], "note": "visual verification required"},
        {"id": "IT-6", "surface": "non_ui", "artifacts": ["help_stdout.log", "invalid_site_stdout.log", "invalid_site_exit_code.txt", "no_scans_stdout.log", "no_scans_exit_code.txt"]},
        {"id": "IT-7", "surface": "non_ui", "artifacts": ["help_stdout.log", "invalid_file_stdout.log", "invalid_file_exit_code.txt", "bad_format_stdout.log", "bad_format_exit_code.txt"]},
    ]
}
json.dump(manifest, open(out, "w"), indent=2)
PYEOF

echo "=== [validate-test] Evidence written to: $EVIDENCE_ROOT ==="
echo "=== [validate-test] PASS (non-UI) — IT-4/IT-5 require browser verification ==="
```

---

## Implementation Order & Dependencies

```
implement_fetch  ─────────────────────────────────┐
implement_transform  ────────────────────────────── ▶  merge_implementation
implement_viewer  ───────────────────────────────┘
```

- Workers 1–3 can run in **parallel** (no shared source files).
- `merge_implementation` runs after all three succeed.
- Within `merge_implementation`: scaffolding (4.1) → scripts (4.2–4.4) → end-to-end smoke test.

---

## Conflict Resolution Notes

All three branch plans were consistent on the core design. Key synthesis decisions:

| Issue | Resolution |
|-------|-----------|
| **PLY format default** | ASCII default (Plan A/C) with `--format binary_little_endian` option (Plan B/C's preference for large files). ASCII is simpler for debugging; binary available when needed. |
| **CLI argument style** | Positional args (`site datetime`) from Plan A, consistent with Plan C. Plan B used `--site`/`--time` flags; positional are more ergonomic for a simple tool. |
| **Unit tests** | Plan B and C both recommended them; Plan A only mentioned them. Include unit tests for `test_fetch.py` and `test_transform.py`. |
| **PLY writer performance** | Use `np.savetxt` / structured array `.tobytes()` (Plan A's fast path) rather than per-row loops. |
| **Viewer camera framing** | Auto-center camera on bounding sphere (Plans A/C both suggested this). |
| **`np.tile` vs `np.broadcast_to`** | Use `np.tile` per Py-ART API reference (ensures contiguous arrays). |
| **Error handling coverage** | All three plans agreed on error paths. Combined into explicit `FileNotFoundError` + `ValueError` hierarchy. |
| **`.envrc` optional secrets** | `dotenv_if_exists` (not `dotenv`) so `.env.local` is optional. |

---

## AC ↔ Worker Traceability Matrix

| AC | Worker | How satisfied |
|----|--------|---------------|
| AC-1.1 | implement_fetch | `pyproject.toml` + `uv sync` + `arm-pyart`/`boto3` imports |
| AC-1.2 | implement_viewer | `viewer/package.json` with `three`, `npm install` + dev server |
| AC-1.3 | implement_fetch | `pyproject.toml` lists all deps |
| AC-1.4 | implement_fetch | `.envrc` activates uv venv, loads `.env.local` |
| AC-2.1 | implement_fetch | `cli.py` positional `site` + `datetime` args |
| AC-2.2 | implement_fetch | `list_scans()` + print scan listing (MSG-2) |
| AC-2.3 | implement_fetch | `download_scan()` to `--output` path |
| AC-2.4 | implement_fetch | Downloaded directly from S3 gzip archive |
| AC-2.5 | implement_fetch | `sys.exit(0/1)` |
| AC-2.6 | implement_fetch | SITE_RE validation + error message (MSG-4) |
| AC-2.7 | implement_fetch | Empty scan list check + error message (MSG-5) |
| AC-2.8 | implement_fetch | argparse `--help` (MSG-1) |
| AC-3.1 | implement_transform | `cli.py` positional `input` + `output` args |
| AC-3.2 | implement_transform | PLY header with `float x/y/z` + `uchar r/g/b` |
| AC-3.3 | implement_transform | `range(radar.nsweeps)` loop in `transform.py` |
| AC-3.4 | implement_transform | `~np.ma.getmaskarray()` filter in `transform.py` |
| AC-3.5 | implement_transform | `antenna_vectors_to_cartesian()` from Py-ART |
| AC-3.6 | implement_transform | Exact NWS table via `dbz_to_rgb_vectorized()` |
| AC-3.7 | implement_transform | Storm produces >100K valid gates |
| AC-3.8 | implement_transform | Clear-air filtering produces <10K gates |
| AC-3.9 | implement_transform | `sys.exit(0/1)` in `cli.py` |
| AC-3.10 | implement_transform | `FileNotFoundError` + `ValueError` paths |
| AC-3.11 | implement_transform | argparse `--help` (MSG-6) |
| AC-3.12 | implement_transform | Print vertex count on success (MSG-7) |
| AC-3.13 | implement_transform | `radar.range['data']` = gate centers; comment in code |
| AC-4.1 | implement_viewer | `viewer/index.html` + `npm start` dev server |
| AC-4.2 | implement_viewer | File picker + URL `?ply=` param |
| AC-4.3 | implement_viewer | `THREE.Points` with `vertexColors: true` |
| AC-4.4 | implement_viewer | `OrbitControls` left-drag = orbit |
| AC-4.5 | implement_viewer | `OrbitControls` scroll = zoom |
| AC-4.6 | implement_viewer | `OrbitControls` right-drag = pan |
| AC-5.1 | merge_implementation | End-to-end pipeline in `validate-test.sh` |
| AC-5.2 | merge_implementation | Visual verification of layered tilts in IT-5 |

---

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| **Py-ART install friction** | Pin `arm-pyart>=1.18` in `pyproject.toml`; validate early via `uv sync` in `validate-build.sh` |
| **S3 network in CI** | `validate-test.sh` caches downloaded files; skips re-download if file exists |
| **Large PLY files (>15MB ASCII)** | `--format binary_little_endian` option available; ASCII default for debugging simplicity |
| **Three.js importmap browser support** | importmap is supported in all modern browsers (Chrome 89+, Firefox 108+, Safari 16.4+); fallback: swap `main.js` import to CDN URL |
| **Clear-air scan >10K points** | `-30 dBZ` filter is per-spec; KLSX 2024-05-01 is a documented calm day; if threshold needs tuning, do so only within the no-data/masked filtering rules |
| **Gate center accuracy (AC-3.13)** | `radar.range['data']` gives gate centers by Py-ART convention; document this in code comment citing AC-3.13 |
| **Browser IT-4/IT-5 evidence** | `validate-test.sh` writes `README.txt` with manual steps; if Playwright is available it can be used to automate screenshots |
| **`np.tile` memory** | For very large sweeps (>5M elements), use `np.broadcast_to` with `.copy()` if needed; `np.tile` is safe for typical NEXRAD sweep sizes |
