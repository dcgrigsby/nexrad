# NEXRAD Level II Data Format Specification (ICD)

**Purpose:** Reference document for software engineers building a NEXRAD Level II binary parser.

**Date:** 2026-03-15
**Status:** Research Summary (for official specification, see references)

---

## 1. Official Documentation

**Primary Source:**
- **NWS NEXRAD Radar Data Interface Control Document (ICD) for Archive II Files**
  - URL: https://www.ncdc.noaa.gov/sites/default/files/attachments/rda.ucar.edu/Documents/ICD_RDA_NEXRAD_L2_ARCHIVE_II.txt
  - Maintained by: NOAA National Centers for Environmental Information (NCEI)
  - Format: Plain text technical specification
  - Content: Complete binary format definition, message types, data layouts

**Secondary References:**
- UCAR NEXRAD Archive Documentation: https://www2.mmm.ucar.edu/rt-laps/public/html/models/nexrad.html
- WSR-88D (NEXRAD) Product Definitions: https://www.ncdc.noaa.gov/wmo/
- Py-ART (Python ARM Radar Toolkit) source code: https://github.com/ARM-DOE/pyart/blob/main/pyart/io/nexrad.py
  - Reference implementation for message parsing and decompression

---

## 2. File Structure: NEXRAD Level II Archive

A Level II archive file (.gz, .bz2, or uncompressed) contains a sequence of **messages** organized as follows:

```
[Volume Header] [Message 1] [Message 2] ... [Message N]
```

### 2.1 Volume Header (120 bytes)

Located at byte offset 0 of the archive file. Provides metadata about the entire scan volume.

| Field | Offset | Size | Type | Notes |
|-------|--------|------|------|-------|
| ICAO ID | 0 | 4 | ASCII | Radar site code (e.g., "KATX") |
| Message Count | 4 | 4 | int32 BE | Number of messages in file |
| Message Type | 8 | 4 | int32 BE | Always 7 for archive II |
| Sequence Number | 12 | 4 | int32 BE | Volume scan sequence identifier |
| Volume Number | 16 | 4 | int32 BE | Volume scan number |
| Reserved | 20 | 100 | — | Padding/future use |

**Note:** The header is immediately followed by compressed or uncompressed messages. Message boundaries are determined by message size fields within each message.

### 2.2 Message Structure (Generic)

Each message begins with a **31-byte header** followed by data:

```
[Message Header (31 bytes)] [Message Data (variable length)]
```

**Message Header (31 bytes):**

| Field | Offset (within header) | Size | Type | Notes |
|-------|-------|------|------|-------|
| Redundant 1 | 0 | 4 | int32 BE | Message type identifier (duplicate) |
| Message ID | 4 | 1 | uint8 | Message type number (1, 2, 31, etc.) |
| Message Sequence | 5 | 3 | uint8[3] | Message sequence number (24-bit) |
| Message Generation Time | 8 | 4 | int32 BE | Seconds since 00:00:00 UTC today |
| Message Size | 12 | 2 | uint16 BE | Size of message (excluding first 12 bytes of header) |
| Reserved 1 | 14 | 1 | uint8 | Reserved |
| Reserved 2 | 15 | 2 | uint16 BE | Reserved |
| Message Segment Number | 17 | 2 | uint16 BE | Segment number (1st, 2nd, etc.) |
| Message Segment Count | 19 | 2 | uint16 BE | Total segments in this message |
| Reserved 3 | 21 | 10 | — | Reserved |

---

## 3. Message Type 31: Digital Radar Data (Generic Format)

Message Type 31 contains the reflectivity, velocity, and spectrum data. This is the primary message type for extracting precipitation reflectivity.

### 3.1 Message Type 31 Structure

```
[Generic Radar Data Header] [Radial Data #1] [Radial Data #2] ... [Radial Data #N]
```

**Generic Radar Data Header (102 bytes after message header):**

| Field | Offset | Size | Type | Notes |
|-------|--------|------|------|-------|
| Radar Identifier | 0 | 4 | ASCII | Site ID |
| Collection Time | 4 | 4 | int32 BE | Milliseconds since midnight UTC |
| Collection Date | 8 | 2 | uint16 BE | Days since 01/01/1970 |
| Azimuth (raw value) | 10 | 2 | uint16 BE | Azimuth × 8 (range: 0-2880 = 0°-360°) |
| Azimuth Number | 12 | 2 | uint16 BE | Radial number within elevation cut |
| Radial Status | 14 | 2 | uint16 BE | New elevation cut, intermediate, or end-of-cut |
| Elevation (raw value) | 16 | 2 | int16 BE | Elevation × 8 (range: -900 to 900 = -112.5° to +112.5°) |
| Elevation Number | 18 | 2 | uint16 BE | Elevation cut number (0-indexed) |
| Surveillance Range | 20 | 2 | uint16 BE | Range to first surveillance gate (meters) |
| Doppler Range | 22 | 2 | uint16 BE | Range to first Doppler gate (meters) |
| Surveillance Gate Size | 24 | 2 | uint16 BE | Surveillance gate spacing (meters) |
| Doppler Gate Size | 26 | 2 | uint16 BE | Doppler gate spacing (meters) |
| Number of Surveillance Gates | 28 | 2 | uint16 BE | Count of surveillance/reflectivity gates |
| Number of Doppler Gates | 30 | 2 | uint16 BE | Count of Doppler/velocity gates |
| Sector Blanking | 32 | 2 | uint16 BE | Sector blanking flags |
| ... | ... | ... | ... | Additional fields continue to byte 102 |

**Key fields for reflectivity extraction:**
- **Azimuth (raw):** Divide by 8 to get degrees (0.0° to 360.0°)
- **Elevation (raw):** Divide by 8 to get degrees (-112.5° to +112.5°)
- **Surveillance Range:** Distance to first gate in meters
- **Surveillance Gate Size:** Spacing between consecutive gates in meters
- **Number of Surveillance Gates:** Count of range gates in the radial

### 3.2 Radial Data Structure

Following the header, data is organized into **moments** (reflectivity, velocity, spectrum width, etc.). Each moment has a **moment header** describing the data:

**Moment Header (12 bytes per moment):**

| Field | Offset | Size | Type | Notes |
|-------|--------|------|------|-------|
| Data Moment Type | 0 | 1 | uint8 | 1=Reflectivity (dBZ), 2=Velocity, 3=SW, 4=ZDR, etc. |
| Data Moment Sector | 1 | 1 | uint8 | Sector within the moment |
| Gate Count | 2 | 2 | uint16 BE | Number of gates for this moment |
| Data Word Size | 4 | 2 | uint16 BE | Bits per gate (1-32) |
| Scale | 6 | 4 | int32 BE | Scale factor (as IEEE 32-bit float) |
| Offset | 10 | 4 | int32 BE | Offset factor (as IEEE 32-bit float) |

**Data Extraction:**

For each gate (raw binary value `r`):
```
physical_value = scale × r + offset
```

For reflectivity (dBZ):
- Scale typically: 0.5
- Offset typically: -32.0
- Raw range: 0-255, or 0-65535 (depending on bits per gate and compression)

The raw data immediately follows the moment header and is packed at `Data Word Size` bits per value. Values may be packed into bytes without alignment (bit-level reading required).

---

## 4. Data Organization: Gates, Radials, and Elevation Cuts

### 4.1 Spatial Structure

```
Volume Scan (one timestamp)
  └─ Elevation Cut 1 (0.5°)
      └─ Radial 1 (azimuth 0°)
          └─ Gate 1 (range 1000m) → reflectivity value
          └─ Gate 2 (range 2000m) → reflectivity value
          └─ ... (up to Number of Surveillance Gates)
      └─ Radial 2 (azimuth 0.8°)
          └─ Gate 1 (range 1000m) → reflectivity value
          └─ ...
      └─ ... (up to ~460 radials, one per 0.8° in azimuth)
  └─ Elevation Cut 2 (1.5°)
      └─ Radial 1...
  └─ ...
  └─ Elevation Cut N (up to 14 cuts)
```

### 4.2 Gate Indexing

**To locate a reflectivity value in polar coordinates:**

```
gate_index = 0 to (Number of Surveillance Gates - 1)
range_m = Surveillance Range + (gate_index × Surveillance Gate Size)
azimuth_deg = Azimuth (raw value) / 8.0
elevation_deg = Elevation (raw value) / 8.0
```

**Example:** If Surveillance Range = 500m, Surveillance Gate Size = 250m, and gate_index = 3:
```
range = 500 + (3 × 250) = 1250 meters
```

### 4.3 Message Sequence

Messages are typically ordered by elevation cut number, then by azimuth within each cut. However, parsers must handle out-of-order messages and detect elevation transitions using the radial status flag.

---

## 5. Key Fields for Reflectivity Parsing

| Purpose | Field | Extraction |
|---------|-------|-----------|
| **Angle (azimuth)** | Message Hdr: Azimuth (raw) | `azimuth_deg = value / 8.0` |
| **Angle (elevation)** | Message Hdr: Elevation (raw) | `elevation_deg = value / 8.0` |
| **Range to first gate** | Generic Hdr: Surveillance Range | Use directly in meters |
| **Gate spacing** | Generic Hdr: Surveillance Gate Size | Use directly in meters |
| **Gate count** | Generic Hdr: Number of Surveillance Gates | Use directly |
| **Reflectivity value** | Moment Data (raw) → dBZ via scale/offset | `dBZ = scale × raw + offset` |
| **No data flag** | Moment Data: raw = 0 or special value | Check before computing dBZ |
| **Time** | Message Hdr: Collection Time, Collection Date | Milliseconds since midnight + date offset |

---

## 6. Compression in Archive Files

### 6.1 Archive File Compression

NEXRAD Level II archive files are typically distributed pre-compressed at the file level (not per-message). Common formats:

| Format | File Extension | Compression Method | Usage |
|--------|----------------|-------------------|-------|
| gzip | `.gz` | DEFLATE (RFC 1951) | AWS S3 (most common) |
| bzip2 | `.bz2` | Burrows-Wheeler | Some archives |
| Uncompressed | `.tar`, `.ar` | None | Some real-time streams |

**Python decompression:**

```python
import gzip
import bz2

# For gzip
with gzip.open('KATX_file.gz', 'rb') as f:
    data = f.read()

# For bzip2
with bz2.open('KATX_file.bz2', 'rb') as f:
    data = f.read()
```

### 6.2 Per-Message Compression (Rare)

Some implementations (WSR-88D real-time) use bzip2 compression on individual messages. Compressed message indicator is in the message header. Py-ART handles this transparently; custom parsers should check for compression flags.

---

## 7. Super-Resolution vs. Legacy Resolution

### 7.1 Legacy Resolution

- **Azimuth:** ~460 radials per 360°, approximately 0.78° separation
- **Range:** Gates starting at ~1 km, spaced 250 m or 1 km
- **Elevation:** Full suite of ~14 fixed angles

### 7.2 Super-Resolution Mode

Introduced around 2013. Provides higher spatial sampling:

- **Azimuth:** ~920 radials per 360°, approximately 0.39° separation (doubled)
- **Range:** Gates at 250 m spacing (finer than 1 km legacy)
- **Elevation:** Same ~14 angles

**Detection in data:**

- Count radials in a single elevation cut. > 600 radials → super-resolution.
- Examine gate spacing (250m = super-res, 1000m = legacy for older systems).
- Check site configuration metadata (when available).

**Impact on parsing:**

- No change to binary format; parser operates identically.
- Only affects the interpretation of the total radial count and gate spacing parameters.
- Point cloud will have higher density in super-resolution data.

---

## 8. Data Quality and Special Cases

### 8.1 No-Data and Clutter

| Scenario | Indicator | Handling |
|----------|-----------|----------|
| No meteorological return | Raw moment value = 0 or 1 | Filter as "no data" |
| Clutter/noise | Low reflectivity near radar (~0 to -10 dBZ) | Often removed in quality control |
| Range folding | Velocity data only; reflectivity unaffected | Not relevant for reflectivity |
| Attenuation | Gradual dBZ decrease with range | Apply correction or accept bias |

### 8.2 Radial Status Flags

The Radial Status field in Message Type 31 indicates transition points:

| Value | Meaning | Action |
|-------|---------|--------|
| 0 | Intermediate radial | Continue collecting for current elevation |
| 1 | Beginning of elevation | New elevation cut starting |
| 2 | End of elevation | Elevation cut complete |
| 3 | End of volume | Entire volume scan complete |

Use these flags to group radials into elevation cuts and volumes.

---

## 9. Coordinate Transformation (Polar to Cartesian)

To convert from polar radar coordinates to Cartesian (x, y, z) for 3D visualization:

```python
import math

# Constants
EARTH_RADIUS_M = 6371000  # meters
REFRACTION_K = 4/3         # Effective radius factor

# Effective radius accounting for beam refraction
Re = EARTH_RADIUS_M * REFRACTION_K

# Input: azimuth_deg, elevation_deg, range_m
# Output: (x, y, z) in Cartesian space (meters)

def polar_to_cartesian(azimuth_deg, elevation_deg, range_m):
    azimuth_rad = math.radians(azimuth_deg)
    elevation_rad = math.radians(elevation_deg)

    # Radar equation (with refraction model)
    ground_range = range_m * math.cos(elevation_rad)
    height = range_m * math.sin(elevation_rad)

    # Flat-Earth approximation (valid for small ranges < 200 km)
    x = ground_range * math.sin(azimuth_rad)
    y = ground_range * math.cos(azimuth_rad)
    z = height

    # (More sophisticated models account for Earth's curvature;
    #  see pyart.core.transforms for production use)

    return (x, y, z)
```

Py-ART's coordinate functions (`pyart.io.read_nexrad_archive()` + `pyart.core.transforms`) handle full curvature and refraction models automatically.

---

## 10. Parsing Workflow (High-Level)

1. **Open archive:** Decompress gzip/bzip2 if needed.
2. **Read volume header:** Extract radar ID, message count.
3. **For each message:**
   - Read 31-byte message header.
   - Check message type.
   - If type = 31 (Digital Radar Data):
     - Read generic radar data header (102 bytes).
     - Extract azimuth, elevation, range, gate count.
     - Parse moment headers and raw data.
     - For reflectivity (moment type 1):
       - Read raw gate values (unpack from bit-packed data).
       - Convert to dBZ using `dBZ = scale × raw + offset`.
4. **Group by elevation:**
   - Use radial status flags or elevation number to organize data.
5. **Transform to Cartesian:**
   - For each gate: convert polar (azimuth, elevation, range) to (x, y, z).
6. **Export (e.g., PLY point cloud):**
   - Write (x, y, z, color) tuples for points with valid data.

---

## 11. Testing and Validation

### 11.1 Sample Data Sources

- **AWS S3:** `s3://noaa-nexrad-level2/` (public bucket, free access)
  - Browse: https://registry.opendata.aws/noaa-nexrad/
  - Typical file: `2024/03/15/KATX/KATX20240315_001200_V06`
- **NCEI Archive:** https://www.ncdc.noaa.gov/nexradinv/ (historical data)

### 11.2 Validation Checks

- File opens and volume header reads without error.
- Azimuth values range 0.0° to 360.0°.
- Elevation values reasonable for chosen radar (typically 0.5° to 19.5°).
- Range and gate count produce sensible maximum ranges (~200+ km).
- Reflectivity values (dBZ) in expected range (typically -30 to +60 dBZ).
- Radial count per elevation matches configuration (legacy: ~460, super-res: ~920).

### 11.3 Quality Assurance with Py-ART

For verification, parse the same file with Py-ART and compare:

```python
import pyart

radar = pyart.io.read_nexrad_archive('KATX_file.gz')
print(radar)  # Prints structure: elevations, gates, reflectivity field
```

---

## 12. References and Further Reading

| Resource | URL |
|----------|-----|
| **Official ICD (NOAA)** | https://www.ncdc.noaa.gov/sites/default/files/attachments/rda.ucar.edu/Documents/ICD_RDA_NEXRAD_L2_ARCHIVE_II.txt |
| **Py-ART (Reference Implementation)** | https://github.com/ARM-DOE/pyart |
| **UCAR/NCAR NEXRAD Docs** | https://www2.mmm.ucar.edu/rt-laps/public/html/models/nexrad.html |
| **AWS Open Data NEXRAD** | https://registry.opendata.aws/noaa-nexrad/ |
| **NOAA NWS Radar Info** | https://www.weather.gov/wrh/Climate |

---

## Appendix A: Byte Order

All multi-byte integer fields are **big-endian (network byte order)** unless otherwise noted. Use:
- Python: `struct.unpack('>I', bytes)` for big-endian integers
- C/C++: `htonl()`, `htons()` conversion or byte-swap on little-endian systems

---

## Appendix B: Common Gate Data Moment Types

| Type | Meaning | Typical Use |
|------|---------|------------|
| 1 | Reflectivity (dBZ) | Precipitation intensity |
| 2 | Mean Radial Velocity | Wind speed / storm motion |
| 3 | Spectrum Width | Turbulence / wind variability |
| 4 | Differential Reflectivity (ZDR) | Rain drop size / hail detection |
| 5 | Differential Phase (PhiDP) | Hail / ice detection |
| 6 | Cross-Correlation Coeff. (RhoHV) | Data quality |

Reflectivity (Type 1) is used for point cloud color mapping in most visualization applications.

---

**Document created:** 2026-03-15
**For:** NEXRAD Level II parser development
**Audience:** Software engineers implementing binary data parsing
