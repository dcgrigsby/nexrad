"""PLY file writer for NEXRAD point cloud data."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def write_ply_ascii(
    output_path: Path,
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    r: np.ndarray,
    g: np.ndarray,
    b: np.ndarray,
) -> int:
    """Write point cloud data to a PLY file in ASCII format.

    Args:
        output_path: Path to write the PLY file.
        x, y, z: float32 arrays of Cartesian coordinates in meters.
        r, g, b: uint8 arrays of color components.

    Returns:
        Number of vertices written.
    """
    n = len(x)
    assert len(y) == n and len(z) == n
    assert len(r) == n and len(g) == n and len(b) == n

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        # PLY header (AC-3.2: x, y, z float + r, g, b uchar)
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {n}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("property uchar red\n")
        f.write("property uchar green\n")
        f.write("property uchar blue\n")
        f.write("end_header\n")

        # Write vertex data
        data = np.column_stack([
            x.astype(np.float32),
            y.astype(np.float32),
            z.astype(np.float32),
            r.astype(np.uint8),
            g.astype(np.uint8),
            b.astype(np.uint8),
        ])
        for row in data:
            f.write(
                f"{row[0]:.2f} {row[1]:.2f} {row[2]:.2f} "
                f"{int(row[3])} {int(row[4])} {int(row[5])}\n"
            )

    return n


def write_ply_binary(
    output_path: Path,
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    r: np.ndarray,
    g: np.ndarray,
    b: np.ndarray,
) -> int:
    """Write point cloud data to a PLY file in binary little-endian format.

    Args:
        output_path: Path to write the PLY file.
        x, y, z: float32 arrays of Cartesian coordinates in meters.
        r, g, b: uint8 arrays of color components.

    Returns:
        Number of vertices written.
    """
    n = len(x)
    assert len(y) == n and len(z) == n
    assert len(r) == n and len(g) == n and len(b) == n

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build header as bytes
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {n}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        "end_header\n"
    ).encode("ascii")

    # Build structured array for efficient binary write
    dtype = np.dtype([
        ("x", "<f4"),
        ("y", "<f4"),
        ("z", "<f4"),
        ("r", "u1"),
        ("g", "u1"),
        ("b", "u1"),
    ])
    data = np.empty(n, dtype=dtype)
    data["x"] = x.astype(np.float32)
    data["y"] = y.astype(np.float32)
    data["z"] = z.astype(np.float32)
    data["r"] = r.astype(np.uint8)
    data["g"] = g.astype(np.uint8)
    data["b"] = b.astype(np.uint8)

    with open(output_path, "wb") as f:
        f.write(header)
        f.write(data.tobytes())

    return n
