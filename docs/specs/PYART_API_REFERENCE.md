# Py-ART API Reference: NEXRAD Level II Data Processing

**Python ARM Radar Toolkit (Py-ART)** — comprehensive library for reading, processing, and visualizing radar data, including NEXRAD Level II archives.

---

## 1. Installation

### Conda (Recommended)
```bash
conda install -c conda-forge arm_pyart
```

### Pip
```bash
pip install arm-pyart
```

### Dependencies
- numpy
- scipy
- matplotlib
- netCDF4

### Verify Installation
```python
import pyart
print(pyart.__version__)
```

---

## 2. Reading NEXRAD Level II Files

### Function: `pyart.io.read_nexrad_archive()`

Read a NEXRAD Level II archive file (compressed or uncompressed).

#### Signature
```python
pyart.io.read_nexrad_archive(filename, delay_field_loading=False,
                             file_field_names=False, exclude_fields=None)
```

#### Parameters
- **filename** (str): Path to NEXRAD file (`.gz`, `.bz2`, or uncompressed)
- **delay_field_loading** (bool, default=False): If True, field data is not loaded into memory until accessed (lazy loading)
- **file_field_names** (bool, default=False): If True, preserve original field names from file instead of standardizing them
- **exclude_fields** (list, optional): List of field names to exclude from loading

#### Returns
- **Radar** object: Contains metadata, field data, and coordinate information

#### Example
```python
import pyart

# Basic read
radar = pyart.io.read_nexrad_archive('NEXRAD_file.gz')

# With lazy loading
radar = pyart.io.read_nexrad_archive('NEXRAD_file.gz', delay_field_loading=True)
```

#### Common Fields Available (NEXRAD Level II)
- `'reflectivity'` — Equivalent reflectivity factor (dBZ)
- `'velocity'` — Radial velocity (m/s)
- `'spectrum_width'` — Doppler spectrum width (m/s)
- `'differential_reflectivity'` — ZDR (dB) — if available in data
- `'cross_correlation_ratio'` — ρhv — if available in data
- `'differential_phase'` — ΦDP (degrees) — if available in data

---

## 3. Radar Object Structure

The Radar object is the core data container. Key attributes:

### Core Attributes

#### Fields Dictionary
```python
radar.fields  # dict
# Keys: field names (strings)
# Values: dicts with 'data' (numpy array), 'units', 'long_name', 'standard_name'

# Access reflectivity data
reflectivity_field = radar.fields['reflectivity']
reflectivity_array = reflectivity_field['data']  # shape: (n_rays, n_gates)
```

#### Coordinate Arrays

```python
# Azimuth: one value per ray [0-360 degrees]
radar.azimuth['data']  # shape: (n_rays,)

# Elevation: one value per ray [degrees above horizon]
radar.elevation['data']  # shape: (n_rays,)

# Range: gate distances from radar [meters]
radar.range['data']  # shape: (n_gates,)

# Time: seconds since start of scan for each ray
radar.time['data']  # shape: (n_rays,)
```

#### Radar Metadata
```python
radar.latitude['data']        # latitude of radar (degrees)
radar.longitude['data']       # longitude of radar (degrees)
radar.altitude['data']        # altitude of radar above sea level (meters)
radar.metadata                # dict of additional attributes
radar.scan_type               # 'ppi', 'rhi', etc.
```

#### Sweep Information
```python
radar.sweep_number            # array: sweep index for each ray
radar.sweep_start_ray_index   # array: starting ray index for each sweep
radar.sweep_end_ray_index     # array: ending ray index for each sweep
radar.fixed_angle             # array: nominal angle for each sweep (elevation for PPI)
```

#### Instrument Info
```python
radar.instrument_name         # e.g., 'WSR-88D'
radar.platform_name           # e.g., 'NEXRAD'
```

### Shape Convention
- **rays** (first dimension): Individual azimuth measurements
- **gates** (second dimension): Range bins along each ray
- **Typical shape**: `(n_rays, n_gates)` — e.g., (720, 1000) for a full 360° scan

---

## 4. Accessing Reflectivity Data

### Direct Access
```python
# Get the reflectivity field dictionary
refl_field = radar.fields['reflectivity']

# Extract numpy array
refl_array = refl_field['data']  # shape: (n_rays, n_gates)

# Get metadata
units = refl_field['units']          # 'dBZ'
long_name = refl_field['long_name']  # Descriptive name

# Metadata dict
print(radar.fields['reflectivity'].keys())
# Typical keys: 'data', 'units', 'long_name', 'standard_name', '_FillValue'
```

### Handling Missing Data
```python
import numpy as np

refl_array = radar.fields['reflectivity']['data']
fill_value = radar.fields['reflectivity'].get('_FillValue', np.nan)

# Mask invalid data
masked_refl = np.ma.masked_equal(refl_array, fill_value)
```

### Extract Single Sweep
```python
# Get sweep index
sweep_idx = 0
start_ray = radar.sweep_start_ray_index['data'][sweep_idx]
end_ray = radar.sweep_end_ray_index['data'][sweep_idx] + 1

# Extract data for this sweep
sweep_refl = radar.fields['reflectivity']['data'][start_ray:end_ray, :]
sweep_azimuth = radar.azimuth['data'][start_ray:end_ray]
sweep_elevation = radar.elevation['data'][start_ray:end_ray]
```

---

## 5. Coordinate Transforms

### 5.1 Polar to Cartesian (Cartesian Radar Coordinates)

Convert from polar (azimuth, range, elevation) to Cartesian (x, y, z) in radar-relative coordinates.

#### Using `pyart.core.transforms`
```python
from pyart.core.transforms import geographic_to_cartesian, cartesian_to_geographic
import numpy as np

# Radar-relative Cartesian (azimuth-based)
azimuth = radar.azimuth['data']      # degrees [0-360]
elevation = radar.elevation['data']  # degrees above horizon
range_gates = radar.range['data']    # meters

# Create 2D meshgrids (rays × gates)
az_grid, rng_grid = np.meshgrid(azimuth, range_gates, indexing='ij')
el_grid = np.full_like(az_grid, fill_value=elevation[0])
el_grid = np.tile(elevation[:, np.newaxis], (1, len(range_gates)))

# Convert to Cartesian (using standard radar convention)
x, y, z = pyart.core.transforms.antenna_vectors_to_cartesian(
    rng_grid, az_grid, el_grid,
    radar.latitude['data'][0],
    radar.longitude['data'][0]
)
# Returns: x, y, z in meters relative to radar
```

#### Manual Calculation (Antenna Convention)
```python
import numpy as np

def polar_to_cartesian_radar(azimuth_deg, elevation_deg, range_m):
    """
    Convert polar to Cartesian radar coordinates.
    azimuth: 0° = North, 90° = East
    elevation: angle above horizon
    """
    az_rad = np.radians(azimuth_deg)
    el_rad = np.radians(elevation_deg)

    # Project range to horizontal distance
    r_horizontal = range_m * np.cos(el_rad)

    # Cartesian components
    x = r_horizontal * np.sin(az_rad)      # East
    y = r_horizontal * np.cos(az_rad)      # North
    z = range_m * np.sin(el_rad)           # Up

    return x, y, z
```

### 5.2 Geographic Coordinates (Lat/Lon/Alt)

Convert radar-relative Cartesian to geographic coordinates.

#### Using `pyart.core.transforms`
```python
from pyart.core.transforms import cartesian_to_geographic

radar_lat = radar.latitude['data'][0]    # degrees
radar_lon = radar.longitude['data'][0]   # degrees
radar_alt = radar.altitude['data'][0]    # meters above sea level

# With computed x, y, z from polar_to_cartesian_radar()
lats, lons, alts = cartesian_to_geographic(
    x, y, z,
    radar_lat, radar_lon, radar_alt
)
# Returns: latitude, longitude, altitude above sea level
```

#### Alternative: `pyart.io.nexrad_common`
```python
from pyart.io.nexrad_common import get_nscatterer_ray

# Lower-level access to NEXRAD-specific coordinate functions
# (used internally; direct use is less common)
```

### 5.3 Complete Example: Reflectivity to Lat/Lon/Alt
```python
import pyart
import numpy as np
from pyart.core.transforms import antenna_vectors_to_cartesian, cartesian_to_geographic

# Read data
radar = pyart.io.read_nexrad_archive('NEXRAD_file.gz')
refl = radar.fields['reflectivity']['data']

# Get coordinates
azimuth = radar.azimuth['data']
elevation = radar.elevation['data']
range_gates = radar.range['data']

# Create 2D grids
az_2d, rng_2d = np.meshgrid(azimuth, range_gates, indexing='ij')
el_2d = np.tile(elevation[:, np.newaxis], (1, len(range_gates)))

# Antenna vectors → Cartesian
x, y, z = antenna_vectors_to_cartesian(rng_2d, az_2d, el_2d)

# Cartesian → Geographic
radar_lat = radar.latitude['data'][0]
radar_lon = radar.longitude['data'][0]
radar_alt = radar.altitude['data'][0]

lats, lons, alts = cartesian_to_geographic(x, y, z, radar_lat, radar_lon, radar_alt)

# Now: refl[ray, gate], lats[ray, gate], lons[ray, gate], alts[ray, gate]
```

---

## 6. Handling Multiple Elevation Sweeps

NEXRAD PPI (Plan Position Indicator) scans contain multiple elevation sweeps.

### Sweep Structure
```python
n_sweeps = len(radar.sweep_start_ray_index['data'])

for sweep_idx in range(n_sweeps):
    start = radar.sweep_start_ray_index['data'][sweep_idx]
    end = radar.sweep_end_ray_index['data'][sweep_idx] + 1
    fixed_angle = radar.fixed_angle['data'][sweep_idx]

    print(f"Sweep {sweep_idx}: rays {start}-{end}, elevation {fixed_angle:.2f}°")

    # Extract data for this sweep
    sweep_refl = radar.fields['reflectivity']['data'][start:end, :]
    sweep_az = radar.azimuth['data'][start:end]
    sweep_el = radar.elevation['data'][start:end]
```

### Extract All Sweeps
```python
sweeps = {}

for sweep_idx in range(len(radar.sweep_start_ray_index['data'])):
    start = radar.sweep_start_ray_index['data'][sweep_idx]
    end = radar.sweep_end_ray_index['data'][sweep_idx] + 1

    sweeps[sweep_idx] = {
        'reflectivity': radar.fields['reflectivity']['data'][start:end, :],
        'azimuth': radar.azimuth['data'][start:end],
        'elevation': radar.elevation['data'][start:end],
        'fixed_angle': radar.fixed_angle['data'][sweep_idx],
        'range': radar.range['data'],
    }
```

### Accessing Specific Elevation
```python
# Find sweep closest to desired elevation (e.g., 1.0°)
target_elevation = 1.0
sweep_idx = np.argmin(np.abs(radar.fixed_angle['data'] - target_elevation))

start = radar.sweep_start_ray_index['data'][sweep_idx]
end = radar.sweep_end_ray_index['data'][sweep_idx] + 1

# Extract single sweep
refl_sweep = radar.fields['reflectivity']['data'][start:end, :]
az_sweep = radar.azimuth['data'][start:end]
el_sweep = radar.elevation['data'][start:end]
```

---

## 7. Known Gotchas & Pitfalls

### 7.1 Compressed Files Require Manual Decompression
**Issue:** Some systems require explicit decompression.
**Solution:** Py-ART handles `.gz` and `.bz2` automatically. If issues arise:
```bash
# Decompress manually
gunzip -c NEXRAD_file.gz > NEXRAD_file
# Then read
radar = pyart.io.read_nexrad_archive('NEXRAD_file')
```

### 7.2 Variable Elevation in Sweeps
**Issue:** Elevation angle may vary slightly across a sweep due to antenna motion.
**Solution:** Use `fixed_angle` for nominal elevation; use `elevation['data']` for actual values per ray.
```python
nominal_el = radar.fixed_angle['data'][sweep_idx]
actual_els = radar.elevation['data'][start:end]  # May vary ±0.1°
```

### 7.3 Reflectivity Data Types & Missing Values
**Issue:** Missing/invalid data represented as specific values (often -32768 or NaN).
**Solution:** Always check for fill values and mask appropriately.
```python
refl = radar.fields['reflectivity']['data']
fill_value = radar.fields['reflectivity'].get('_FillValue', -32768)

# Mask invalid values
masked_refl = np.ma.masked_equal(refl, fill_value)
# OR
masked_refl = np.ma.masked_where(refl < -30, refl)  # Typical reflectivity floor
```

### 7.4 Azimuth Wrapping at 360°
**Issue:** Azimuth values near 360° may wrap to 0° in some operations.
**Solution:** Be careful with azimuth differences; consider using circular mean/median.
```python
# For averaging azimuths near 0°/360°
from scipy import stats
mean_az = stats.circmean(azimuth, high=360, low=0)
```

### 7.5 Field Names Vary by NEXRAD Type
**Issue:** Newer NEXRAD radars (with dual-pol) have different fields than older models.
**Solution:** Check available fields before accessing.
```python
available_fields = list(radar.fields.keys())
print(available_fields)

if 'differential_reflectivity' in available_fields:
    zdr = radar.fields['differential_reflectivity']['data']
```

### 7.6 Coordinate Transform Caveats
**Issue:** Elevation angle approximation; Earth curvature ignored at short ranges.
**Solution:** For processed data with known accuracy requirements, consider higher-order corrections.
```python
# Py-ART uses simplified geometric projection
# For millimeter-wave or precise meteorological studies, consider:
# - 4/3 Earth radius approximation (already built-in)
# - Atmospheric refraction (not built-in)
```

### 7.7 Large File Memory Usage
**Issue:** Reading full Level II file loads all sweeps into memory.
**Solution:** Use `delay_field_loading=True` or read sweeps selectively.
```python
# Lazy loading
radar = pyart.io.read_nexrad_archive('file.gz', delay_field_loading=True)

# Access triggers load
refl = radar.fields['reflectivity']['data']  # Loaded on first access
```

### 7.8 Time Coordinate Complexity
**Issue:** `radar.time['data']` is seconds since start of first ray; absolute time requires metadata.
**Solution:** Reconstruct datetime from metadata.
```python
import datetime

# Get epoch from metadata
time_origin = radar.time['calendar']
time_units = radar.time['units']  # e.g., 'seconds since ...'

# Parse and convert
start_time = datetime.datetime.fromisoformat(
    radar.metadata.get('time_coverage_start', '')
)
```

### 7.9 Reflectivity Below Noise Floor
**Issue:** Low reflectivity values may represent noise, not true atmospheric signal.
**Solution:** Apply noise filtering or use known thresholds.
```python
# Typical noise floor: -30 to -20 dBZ
refl = radar.fields['reflectivity']['data']
refl_filtered = np.ma.masked_where(refl < -25, refl)
```

### 7.10 Interpolation Across Sweeps
**Issue:** Sweeps at different elevations create irregular grid; interpolation needed for 3D analysis.
**Solution:** Use Py-ART's gridding functions.
```python
from pyart.core import Grid
from pyart.util import grid_from_radars

# Create uniform Cartesian grid from radar
grid = pyart.map.grid_from_radars(
    (radar,),
    grid_shape=(20, 100, 100),  # z, y, x
    grid_limits=((0, 10000), (-50000, 50000), (-50000, 50000)),
)
```

---

## 8. Useful Utility Functions

### Check Available Fields
```python
print(radar.fields.keys())
```

### Get Radar Info
```python
print(radar)  # Prints summary of radar structure
```

### Extract Metadata
```python
metadata = radar.metadata
print(metadata)
```

### Get Scan Time
```python
# Approximate scan time from time array
scan_duration = radar.time['data'][-1] - radar.time['data'][0]  # seconds
```

---

## 9. Common Workflow Template

```python
import pyart
import numpy as np
from pyart.core.transforms import antenna_vectors_to_cartesian, cartesian_to_geographic

# 1. Read file
radar = pyart.io.read_nexrad_archive('NEXRAD_file.gz')

# 2. Check what's available
print("Fields:", list(radar.fields.keys()))
print("Sweeps:", len(radar.sweep_start_ray_index['data']))

# 3. Extract single sweep
sweep_idx = 0
start = radar.sweep_start_ray_index['data'][sweep_idx]
end = radar.sweep_end_ray_index['data'][sweep_idx] + 1

refl = radar.fields['reflectivity']['data'][start:end, :]
azimuth = radar.azimuth['data'][start:end]
elevation = radar.elevation['data'][start:end]
range_gates = radar.range['data']

# 4. Convert to Cartesian
az_2d, rng_2d = np.meshgrid(azimuth, range_gates, indexing='ij')
el_2d = np.full_like(az_2d, elevation[0])
x, y, z = antenna_vectors_to_cartesian(rng_2d, az_2d, el_2d)

# 5. Convert to geographic
lats, lons, alts = cartesian_to_geographic(
    x, y, z,
    radar.latitude['data'][0],
    radar.longitude['data'][0],
    radar.altitude['data'][0]
)

# 6. Process/visualize
# Now use: refl, lats, lons, alts
```

---

## References

- **Py-ART GitHub:** https://github.com/ARM-DOE/pyart
- **Documentation:** https://arm-doe.github.io/pyart/
- **NEXRAD Level II Format:** https://www.ncei.noaa.gov/products/weather-radar-data-next-generation-nexrad
- **DOE ARM Project:** https://www.arm.gov/

---

**Document Version:** 1.0
**Created:** 2026-03-15
**Target Py-ART Version:** 1.15+
