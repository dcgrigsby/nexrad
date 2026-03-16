"""Core NEXRAD Level II → PLY transform logic using Py-ART."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyart

from .colors import dbz_to_rgb_vectorized
from .ply_writer import write_ply_ascii, write_ply_binary

# Minimum dBZ threshold: gates below this are treated as no-data (AC-3.4)
DBZ_MIN = 5.0

# Reflectivity field name candidates (Py-ART uses different names by convention)
REFL_FIELD_CANDIDATES = [
    "reflectivity",
    "REF",
    "DBZ",
    "equivalent_reflectivity_factor",
]


def _get_reflectivity_field(radar: pyart.core.Radar) -> str:
    """Return the name of the reflectivity field in the radar object."""
    for name in REFL_FIELD_CANDIDATES:
        if name in radar.fields:
            return name
    # Fall back to first field that has 'refl' or 'dbz' in the name
    for name in radar.fields:
        if "refl" in name.lower() or "dbz" in name.lower():
            return name
    raise ValueError(
        f"No reflectivity field found in radar. Available fields: "
        f"{list(radar.fields.keys())}"
    )


def transform(input_path: Path, output_path: Path, fmt: str = "ascii") -> int:
    """Transform a NEXRAD Level II file to a colored PLY point cloud.

    Processes all elevation sweeps (AC-3.3), filters masked/no-data gates
    (AC-3.4), computes Cartesian coordinates using Py-ART's standard radar
    geometry with earth curvature and beam refraction (AC-3.5, AC-3.13),
    and maps dBZ values to NWS standard colors (AC-3.6).

    Gate positions are at the volumetric center of each gate:
    - Radial center: mid-range of the gate (radar.range['data'] gives gate
      centers by Py-ART convention — AC-3.13)
    - Azimuthal center: center azimuth of each ray
    - Elevation center: center elevation of each sweep

    Args:
        input_path: Path to the NEXRAD Level II archive file (gzip or raw).
        output_path: Path to write the output PLY file.
        fmt: Output format, 'ascii' or 'binary_little_endian'.

    Returns:
        Number of vertices written to the PLY file (AC-3.12).

    Raises:
        FileNotFoundError: If input_path does not exist (AC-3.10).
        ValueError: If the file cannot be parsed or has no reflectivity data (AC-3.10).
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Read radar data with Py-ART
    try:
        radar = pyart.io.read(str(input_path))
    except Exception as exc:
        raise ValueError(f"Cannot parse radar file '{input_path}': {exc}") from exc

    # Find reflectivity field
    try:
        refl_field = _get_reflectivity_field(radar)
    except ValueError:
        raise

    # Collect all points across all sweeps (AC-3.3)
    all_x: list[np.ndarray] = []
    all_y: list[np.ndarray] = []
    all_z: list[np.ndarray] = []
    all_dbz: list[np.ndarray] = []

    for sweep_idx in range(radar.nsweeps):
        # Extract sweep slice
        sweep = radar.get_slice(sweep_idx)
        refl_data = radar.fields[refl_field]["data"][sweep]  # masked array

        # gate_x, gate_y, gate_z: Cartesian coords using standard radar geometry
        # radar.range['data'] contains gate center ranges (AC-3.13: volumetric centers)
        # antenna_vectors_to_cartesian applies earth curvature + beam refraction (AC-3.5)
        gate_x, gate_y, gate_z = radar.get_gate_x_y_z(sweep_idx, edges=False)

        # Flatten
        refl_flat = refl_data.filled(np.nan).ravel()
        x_flat = gate_x.ravel()
        y_flat = gate_y.ravel()
        z_flat = gate_z.ravel()

        # Filter: keep only gates with valid reflectivity >= DBZ_MIN (AC-3.4)
        mask = np.isfinite(refl_flat) & (refl_flat >= DBZ_MIN)
        if not np.any(mask):
            continue

        all_x.append(x_flat[mask])
        all_y.append(y_flat[mask])
        all_z.append(z_flat[mask])
        all_dbz.append(refl_flat[mask])

    if not all_x:
        raise ValueError(
            f"No valid reflectivity gates found in '{input_path}' "
            f"(all gates masked or below {DBZ_MIN} dBZ)"
        )

    # Concatenate all sweeps
    x = np.concatenate(all_x)
    y = np.concatenate(all_y)
    z = np.concatenate(all_z)
    dbz = np.concatenate(all_dbz)

    # Map dBZ to NWS colors (AC-3.6)
    colors = dbz_to_rgb_vectorized(dbz.astype(np.float32))
    r = colors[:, 0]
    g = colors[:, 1]
    b = colors[:, 2]

    # Write PLY (AC-3.2)
    if fmt == "binary_little_endian":
        n = write_ply_binary(output_path, x, y, z, r, g, b)
    else:
        n = write_ply_ascii(output_path, x, y, z, r, g, b)

    return n
