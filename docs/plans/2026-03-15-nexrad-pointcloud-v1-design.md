# NEXRAD 3D Point Cloud Viewer — v1 Design

## Goal

Build CLI tools that fetch NEXRAD radar data, transform it into a 3D point cloud, and display it in an interactive web viewer. A single volume scan (one radar site, one moment in time) rendered as a colored point cloud showing all elevation tilts.

## Product

Three CLI tools:

### 1. Fetch Tool (Python)

Downloads a NEXRAD Level II archive file from the Unidata NEXRAD S3 bucket (`s3://unidata-nexrad-level2/`).

- Input: radar site code (e.g., `KATX`) + date/time
- Output: raw Level II binary file
- Lists available scans near the requested time
- No authentication required (public bucket, anonymous access)
- Note: the original NOAA bucket (`noaa-nexrad-level2`) was deprecated September 2025; `unidata-nexrad-level2` is the current public archive
- Dependencies: `boto3`

### 2. Transform Tool (Python)

Parses a Level II file and produces a PLY point cloud with all elevation tilts.

- Input: Level II binary file
- Output: PLY file (ASCII or binary) with position + color per point
- Processing steps:
  1. Parse Level II archive (binary format with compressed messages per tilt)
  2. For each gate in each radial in each tilt: convert polar (azimuth, range, elevation) to Cartesian (x, y, z) using standard radar geometry (earth curvature + beam refraction). Origin (0,0,0) is the radar antenna — the point cloud is centered on the radar site. Each point is placed at the volumetric center of its gate (mid-range bin, center of azimuth beam width, center of elevation beam width).
  3. Filter out gates with no data (most of the volume is empty)
  4. Map reflectivity (dBZ) values to colors using the standard NWS color scale
- Dependencies: `pyart` (Py-ART) for parsing and coordinate transforms
- A full volume scan has ~18M total gates; after filtering empty gates, an active storm produces ~500K–2M points

### 3. Viewer (JavaScript/TypeScript)

Minimal web page that loads a PLY file and renders it as an interactive 3D point cloud.

- Input: PLY file (loaded via file picker or URL)
- Rendering: Three.js with built-in PLY loader
- Controls: orbit, zoom, pan (Three.js OrbitControls)
- No UI chrome, no color legend, no time controls in v1 — just enough to confirm the data looks right

## Environment and Reproducibility

- **direnv** — `.envrc` at repo root for automatic environment activation
- **uv** — Python package/project manager for deterministic dependency resolution
- `pyproject.toml` for Python dependencies
- `package.json` + lockfile for the viewer

## Language Choices

- **Python** for fetch + transform: Py-ART is the dominant NEXRAD library, battle-tested by the meteorological community. `boto3` is the standard AWS S3 client. This is the "strong existing library" case from AGENTS.md.
- **JavaScript/TypeScript** for viewer: Three.js is the standard web 3D library with native PLY support.

## Reference Specifications (to gather before Phase 2)

These specs must be collected and saved to `docs/specs/` so Kilroy pipeline node prompts can reference them:

| Material | Purpose |
|---|---|
| NEXRAD Level II ICD (Interface Control Document) | Binary format spec for archive files |
| Py-ART API documentation | `pyart.io.read_nexrad_archive()`, coordinate transforms, field access |
| PLY format specification | ASCII/binary point cloud format definition |
| NWS reflectivity color table | Standard dBZ-to-color mapping |
| Test scan: active storm | Known supercell or severe storm for the "it works" scenario |
| Test scan: clear air | Minimal-return scan to verify empty filtering |

## Test Scenarios (capabilities, not unit tests)

These will be formalized in the DoD, but conceptually:

1. **Fetch succeeds** — given a valid site + time, a Level II file is downloaded and is a valid archive
2. **Transform produces output** — given a Level II file with an active storm, a PLY file is produced with >100K points
3. **Transform handles clear air** — given a clear-air scan, a PLY file is produced with significantly fewer points (correctly filtered)
4. **Viewer renders** — the PLY file loads in the web viewer and responds to orbit/zoom controls
5. **End-to-end** — fetch a known storm, transform it, open in viewer, and visually confirm the 3D structure shows the layered elevation tilts

## Future Work (not in v1 scope, recorded for reference)

- **Surface rendering** — mesh representation of each elevation tilt as solid colored surfaces
- **Volumetric rendering** — semi-transparent ray-marched volume showing internal structure
- **Time series / animation** — multiple scans over time from one site
- **Multi-site** — combine data from multiple nearby radar sites
- **VR / Apple Vision Pro** — immersive 3D experience (format choices in v1 do not block this)

## How This Gets Built

This product is built by a **Kilroy pipeline**, not by direct Claude Code execution. The pipeline graph (created via `create-dotfile` in Phase 2) will contain software engineering stages: design each tool, implement it, test it, integrate. Reference specs and the DoD are inputs to the pipeline's node prompts.
