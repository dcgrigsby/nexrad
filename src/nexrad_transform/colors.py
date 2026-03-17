"""NWS standard reflectivity color table mapping.

Colors from the NWS standard radar color table (dBZ → RGB).
Values below 5 dBZ are treated as no-data and filtered.
"""

from __future__ import annotations

import numpy as np

# NWS standard reflectivity color table
# Each entry: (min_dbz, max_dbz, R, G, B)
# Colors match the standard NWS WSR-88D color table.
_COLOR_TABLE = [
    # dBZ range      R    G    B   — spec §3.4
    (  5,  10,   0, 150, 255),  # Blue
    ( 10,  15,   0, 200,   0),  # Green
    ( 15,  20, 100, 255,   0),  # Lime Green
    ( 20,  25, 255, 255,   0),  # Yellow
    ( 25,  30, 255, 165,   0),  # Orange
    ( 30,  35, 255, 100,   0),  # Red-Orange
    ( 35,  40, 255,   0,   0),  # Red
    ( 40,  45, 180,   0,   0),  # Dark Red
    ( 45,  50, 255,   0, 255),  # Magenta
    ( 50,  55, 138,  43, 226),  # Violet
    ( 55, 200, 255, 255, 255),  # White
]

# Build lookup arrays for vectorized mapping
_THRESHOLDS = np.array([entry[0] for entry in _COLOR_TABLE], dtype=np.float32)
_COLORS = np.array([(r, g, b) for (_, _, r, g, b) in _COLOR_TABLE], dtype=np.uint8)


def dbz_to_rgb_vectorized(dbz: np.ndarray) -> np.ndarray:
    """Map an array of dBZ values to RGB colors using the NWS standard color table.

    Args:
        dbz: 1-D float32 array of reflectivity values in dBZ.
             Only values >= 5 dBZ should be passed (filtered gates).

    Returns:
        uint8 array of shape (N, 3) with R, G, B values in [0, 255].
    """
    # np.searchsorted finds the index of the bin for each dBZ value
    indices = np.searchsorted(_THRESHOLDS, dbz, side="right") - 1
    # Clip to valid range
    indices = np.clip(indices, 0, len(_COLOR_TABLE) - 1)
    return _COLORS[indices]
