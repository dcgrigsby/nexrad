# NEXRAD Pointcloud Viewer

Convert NEXRAD Level II weather radar data into 3D point clouds and visualize them interactively in your browser.

[Watch demo video](https://daysuntilmigration.com/nexrad/)

## Tools

- **nexrad-fetch**: Python CLI — downloads Level II archives from Unidata S3
- **nexrad-transform**: Python CLI — converts binary radar reflectivity data to PLY point cloud format
- **viewer**: Browser-based interactive 3D visualization — loads and displays the point cloud with mouse controls and color-mapped reflectivity (Three.js)

## Usage

```bash
uv sync
nexrad-fetch KATX 2026-03-21 18:00
nexrad-transform scan.gz scan.ply
cd viewer && npm install && npm run dev
```

## About This Repository

This is a **software factory** built with [Kilroy](https://github.com/danshapiro/kilroy) and the [Attractor](https://github.com/strongdm/attractor) pattern. The entire pipeline — from requirements through implementation across Python and JavaScript — was generated and validated by the factory. No code was hand-written.

The Attractor graph describes multi-stage product development: requirements → spec → implementation (fetch, transform, viewer) → testing → integration. Kilroy orchestrated each stage using Claude to design, build, and verify the artifacts.

## License

Apache License 2.0 — See LICENSE file.
