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
    # dBZ range   R    G    B
    (5, 10, 100, 235, 242),  # light grey-blue
    (10, 15, 42, 144, 229),  # light blue
    (15, 20, 30, 60, 255),  # blue
    (20, 25, 18, 230, 18),  # light green
    (25, 30, 0, 187, 0),  # green
    (30, 35, 0, 130, 0),  # dark green
    (35, 40, 255, 255, 0),  # yellow
    (40, 45, 231, 192, 0),  # dark yellow
    (45, 50, 255, 144, 0),  # orange
    (50, 55, 255, 0, 0),  # red
    (55, 60, 188, 0, 0),  # dark red
    (60, 65, 144, 0, 0),  # very dark red
    (65, 75, 255, 0, 255),  # magenta
    (75, 200, 188, 0, 188),  # dark magenta
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
