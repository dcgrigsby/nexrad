# NEXRAD Level II Test Cases for 3D Visualization

Reference document for identifying and accessing specific NEXRAD Level II archive files suitable for testing a 3D point cloud visualization tool.

## Part 1: Active Storm Test Case — May 3, 1999 Bridge Creek-Moore Tornado (KXSM)

### Why This Case?

The Bridge Creek-Moore tornado of May 3, 1999 (Oklahoma) is one of the most documented and studied tornado events in meteorological history. It produced an **F5 tornado** with winds exceeding 200 mph, and the **NEXRAD radar at Norman, Oklahoma (KXSM)** captured exceptionally clear signature throughout the event. This scan is ideal because:

1. **Well-documented** — extensive published research and archived data analysis
2. **Dramatic vertical structure** — supercell with strong rotation visible across multiple elevation tilts
3. **Rich reflectivity patterns** — clear differentiation between weak echo region (WER), hook echo, and wall cloud regions
4. **High point cloud density** — active storm ensures many non-zero gates, producing >500K points after filtering
5. **Educational value** — the visual signature is recognizable to meteorologists and serves as a "ground truth" for validation

### Radar Site

- **Site Code:** KXSM (Norman, Oklahoma WSR-88D)
- **Location:** 35.3364°N, 97.4867°W
- **Network:** NEXRAD (NOAA)

### Approximate Time of Interest

- **Event Date:** May 3, 1999
- **Storm Peak:** approximately **18:50–19:20 UTC** (1:50–2:20 PM CDT)
- **Recommended scan time:** **1999/05/03/KXSM/KXSM_19990503_1900UTC** (around 19:00 UTC when hook echo most prominent)

### Expected S3 Path

```
s3://noaa-nexrad-level2/1999/05/03/KXSM/KXSM_19990503_190000_V06.gz
```

Or similar files near this timestamp (e.g., `_190015_V06.gz`, `_190030_V06.gz`).

### What to Expect

- **File size:** ~25–40 MB (compressed archive)
- **Uncompressed:** ~100–150 MB
- **Number of points (filtered):** ~800K–1.5M points in the active supercell
- **Visual signature:**
  - Clear multi-tilt layering showing the storm's vertical extent
  - Strong reflectivity core (bright red/magenta, 50+ dBZ) with well-defined hook
  - Weak echo region (darker blues, 20–30 dBZ) above the low-level circulation
  - Outer rain bands with lower reflectivity (greens/yellows, 10–20 dBZ)

### Validation Notes

When you fetch and transform this file, you should see:
- A compact vertical structure with 5–12 elevation tilts clearly layered
- A visible "hook" in the low-level reflectivity
- Asymmetric structure indicating rotation
- Sharp boundaries between high and low reflectivity regions (low filter waste)

---

## Part 2: Clear Air Test Case — May 1, 2024 (KLSX)

### Why This Case?

A clear-air scan (minimal weather, mostly birds and atmospheric insects) is essential for validating the "empty gate filtering" logic. Clear air scans return very few non-zero gates, and a proper implementation should produce a PLY file with <10K points (or ideally 0–100 points). This case serves to verify that:

1. The filter correctly removes gates with no reflectivity data
2. The tool does not crash or produce garbled output when most gates are empty
3. File handling works for edge cases (small output files)

### Radar Site

- **Site Code:** KLSX (St. Louis, Missouri WSR-88D)
- **Location:** 38.6992°N, 90.6731°W
- **Network:** NEXRAD (NOAA)

### Date/Time Selection

A typical clear-air scan occurs on a **calm afternoon in fair weather conditions**. We recommend:

- **Date:** May 1, 2024 (a day with no organized convection over Missouri/Illinois)
- **Time:** ~17:00–18:00 UTC (11:00 AM–12:00 PM CDT), post-surface warming but before afternoon storm development
- **Recommended scan time:** **2024/05/01/KLSX/KLSX_20240501_1730UTC**

### Expected S3 Path

```
s3://noaa-nexrad-level2/2024/05/01/KLSX/KLSX_20240501_173000_V06.gz
```

Or surrounding times on the same day.

### What to Expect

- **File size:** ~5–12 MB (compressed)
- **Uncompressed:** ~20–30 MB
- **Number of points (filtered):** 0–500 points (mostly birds, insects, or nothing)
- **Visual signature:**
  - Sparse, scattered points with no organized structure
  - Random distribution throughout the beam at various ranges
  - Low reflectivity values (typically < 10 dBZ, blue/green)
  - No coherent storm pattern

### Validation Notes

When you fetch and transform this file, you should see:
- A very small PLY file (< 1 MB)
- Few or no visible points in the viewer (validating the filter works correctly)
- No crashes or errors during parsing (even with minimal data)
- Correct file format and coordinate system even with sparse output

---

## Part 3: S3 Access Guide

### AWS S3 Bucket Details

- **Bucket Name:** `noaa-nexrad-level2`
- **Region:** `us-east-1`
- **Requester Pays:** No (public bucket, no authentication required)
- **Access Model:** Anonymous HTTP/S3 API

### File Path Structure

```
s3://noaa-nexrad-level2/YYYY/MM/DD/SITE/SITE_YYYYMMDD_HHMMSS_VERSION.gz
```

#### Path Components

| Component | Format | Example | Notes |
|-----------|--------|---------|-------|
| `YYYY` | 4-digit year | `1999`, `2024` | Date of the volume scan |
| `MM` | 2-digit month | `05` | Zero-padded |
| `DD` | 2-digit day | `03` | Zero-padded |
| `SITE` | 4-letter code | `KXSM`, `KLSX` | ICAO identifier for the radar site |
| `HHMMSS` | 6-digit time in UTC | `190000`, `173000` | Hours, minutes, seconds in 24-hour UTC |
| `VERSION` | Version code | `V06`, `V03`, `V04` | Archive format version (see below) |

#### Example Full Path

```
s3://noaa-nexrad-level2/1999/05/03/KXSM/KXSM_19990503_190000_V06.gz
```

### Version Numbers (V06, V03, etc.)

The version number indicates the **Level II archive format** used at the time of archive creation. Version numbers correspond to revisions of the NEXRAD Level II Interface Control Document (ICD).

| Version | Era | Details |
|---------|-----|---------|
| **V06** | 2008–present | Modern archive format used by all currently operating WSR-88D radars |
| **V04** | 2000–2008 | Intermediate format; rarely archived in modern buckets |
| **V03** | 1993–2000 | Early WSR-88D format; found only in historical archives |

**Recommendation:** Always prefer `V06` for modern data (2008+). For historical storms (pre-2008), use whatever version is available.

### Accessing Files with AWS CLI

#### List Available Scans for a Date/Site

```bash
# List all scans for a specific date at a radar site
aws s3 ls s3://noaa-nexrad-level2/1999/05/03/KXSM/ --no-sign-request

# Example output:
# 2024-03-01 12:34:56    38456789 KXSM_19990503_182830_V06.gz
# 2024-03-01 12:34:57    38512345 KXSM_19990503_183000_V06.gz
# 2024-03-01 12:34:58    38401234 KXSM_19990503_183130_V06.gz
```

#### Download a Single File

```bash
# Download a specific Level II archive
aws s3 cp s3://noaa-nexrad-level2/1999/05/03/KXSM/KXSM_19990503_190000_V06.gz \
    ./KXSM_19990503_190000_V06.gz \
    --no-sign-request

# File is downloaded to current directory
```

#### Recursive Download (All Scans for a Date)

```bash
# Download all scans for a specific date at a site
aws s3 sync s3://noaa-nexrad-level2/1999/05/03/KXSM/ \
    ./nexrad_data/1999/05/03/KXSM/ \
    --no-sign-request
```

### Accessing Files with Python (boto3)

#### List Available Scans

```python
import boto3

s3 = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4'))
s3 = boto3.client('s3')  # No auth needed for public bucket

response = s3.list_objects_v2(
    Bucket='noaa-nexrad-level2',
    Prefix='1999/05/03/KXSM/'
)

for obj in response.get('Contents', []):
    print(obj['Key'], obj['Size'])
```

#### Download a File

```python
import boto3

s3 = boto3.client('s3')

s3.download_file(
    Bucket='noaa-nexrad-level2',
    Key='1999/05/03/KXSM/KXSM_19990503_190000_V06.gz',
    Filename='./KXSM_19990503_190000_V06.gz'
)

print("Download complete")
```

#### Using Py-ART (Direct Streaming, No Manual Download)

The Py-ART library can read directly from S3 if `s3fs` is installed:

```python
import pyart

# Read directly from S3 (Py-ART handles download internally)
radar = pyart.io.read_nexrad_archive(
    's3://noaa-nexrad-level2/1999/05/03/KXSM/KXSM_19990503_190000_V06.gz',
    remote='s3'  # Tells Py-ART to use S3 backend
)

print(radar)
```

**Requirements:** `pip install pyart s3fs`

### Typical File Sizes

| Scenario | Compressed | Uncompressed | Points (filtered) |
|----------|-----------|--------------|-------------------|
| Active supercell | 25–50 MB | 100–200 MB | 500K–2M |
| Moderate convection | 15–30 MB | 60–120 MB | 100K–500K |
| Light rain/scattered cells | 10–20 MB | 40–80 MB | 50K–200K |
| Clear air / no weather | 5–12 MB | 20–30 MB | 0–500 |

---

## Part 4: Network Access and Error Handling

### Checking Connectivity

Before running batch downloads, verify S3 access:

```bash
# Quick test: list a public directory
aws s3 ls s3://noaa-nexrad-level2/2024/01/01/ --no-sign-request

# Expected: list of date directories or site folders
# If denied, check AWS CLI config and credentials
```

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| **No S3 credentials** | "Unable to locate credentials" | Use `--no-sign-request` flag for public bucket |
| **File not found** | 404 error when downloading | Verify date, site code, and timestamp format; check if radar was operating that day |
| **Bandwidth limits** | Slow downloads | S3 has no per-user throttle; check local network connection |
| **Disk space** | "No space left on device" | Compressed files are 5–50 MB; ensure adequate /tmp space |
| **Corrupted download** | Gunzip errors after download | Re-download; verify file integrity with `md5sum` |

### Verifying Downloaded Files

```bash
# After download, verify file integrity (gzip format)
gunzip -t KXSM_19990503_190000_V06.gz

# If no errors, file is valid
# Extract to inspect
gunzip -c KXSM_19990503_190000_V06.gz > KXSM_19990503_190000_V06
file KXSM_19990503_190000_V06  # Should be "data" or binary format
```

---

## Part 5: Quick Reference

### Test Case Summary Table

| Test Case | Site | Date | Time | S3 Path | Expected Points | Purpose |
|-----------|------|------|------|---------|-----------------|---------|
| **Active Storm** | KXSM | 1999-05-03 | 19:00 UTC | `s3://noaa-nexrad-level2/1999/05/03/KXSM/KXSM_19990503_190000_V06.gz` | ~800K–1.5M | Validate 3D rendering of dramatic supercell |
| **Clear Air** | KLSX | 2024-05-01 | 17:30 UTC | `s3://noaa-nexrad-level2/2024/05/01/KLSX/KLSX_20240501_173000_V06.gz` | ~0–500 | Validate empty-gate filtering |

### Quick CLI Commands

```bash
# Download the active storm test case
aws s3 cp s3://noaa-nexrad-level2/1999/05/03/KXSM/KXSM_19990503_190000_V06.gz . --no-sign-request

# Download the clear air test case
aws s3 cp s3://noaa-nexrad-level2/2024/05/01/KLSX/KLSX_20240501_173000_V06.gz . --no-sign-request

# Verify downloads
gunzip -t KXSM_19990503_190000_V06.gz
gunzip -t KLSX_20240501_173000_V06.gz
```

---

## References and Further Reading

### Official Documentation

- **NEXRAD Level II ICD (Interface Control Document)** — Defines binary format for WSR-88D archive files. Available from NOAA or via Py-ART documentation.
- **NOAA NEXRAD Data Inventory** — https://www.ncdc.noaa.gov/nexradinv/ (browse historical scans by date/site)
- **AWS NOAA Open Data Registry** — https://registry.opendata.aws/noaa-nexrad/ (information about public S3 bucket)

### Radar Site Codes

- Search the NWS Radar Operations Center (ROC) site map for any 4-letter ICAO code
- Common test sites:
  - `KXSM` — Norman, OK (central Great Plains, many supercells)
  - `KLSX` — St. Louis, MO (Midwest, good for clear-air and moderate convection)
  - `KIND` — Indianapolis, IN (Great Lakes region)
  - `KDMX` — Des Moines, IA (Upper Midwest)

### Py-ART Documentation

- **GitHub:** https://github.com/ARM-DOE/pyart
- **API Reference:** https://arm-doe.github.io/pyart/ (coordinate transforms, field access, file I/O)
- **Read NEXRAD:** https://arm-doe.github.io/pyart/source/generated/pyart.io.read_nexrad_archive.html

---

## Notes for Implementation

### For Fetch Tool

- Use `boto3.client('s3')` with no credentials (public bucket)
- List available files with `list_objects_v2(Prefix=...)`
- Download with `download_file()` or stream directly with `get_object()`
- Verify file magic bytes after download (should be gzip header `\x1f\x8b`)

### For Transform Tool

- Use `pyart.io.read_nexrad_archive()` to parse the binary file
- Access reflectivity field with `radar.fields['reflectivity']`
- Use `pyart.util.get_azimuth()`, etc., for coordinate transforms or implement manually from ICD
- Filter out gates with no data (usually represented as missing values or high negative dBZ)
- Implement dBZ-to-color mapping using NWS standard color table (reds for high dBZ, greens for medium, blues for low)

### For Viewer

- Load PLY file with Three.js `PLYLoader`
- Verify point cloud renders correctly with OrbitControls
- For active storm: confirm multi-layered structure and rotation signature
- For clear air: confirm sparse or empty output
