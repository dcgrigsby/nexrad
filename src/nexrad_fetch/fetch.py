"""Core S3 listing and download logic for NEXRAD Level II files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import boto3
from botocore import UNSIGNED
from botocore.config import Config

# NEXRAD site codes: 4-letter uppercase ICAO identifiers
SITE_RE = re.compile(r"^[A-Z]{4}$")

# Complete list of operational WSR-88D NEXRAD sites (ICAO codes)
KNOWN_NEXRAD_SITES = frozenset(
    [
        "KABR",
        "KABX",
        "KAKQ",
        "KAMA",
        "KAMX",
        "KAPX",
        "KARX",
        "KATX",
        "KBBX",
        "KBGM",
        "KBHX",
        "KBIS",
        "KBLX",
        "KBMX",
        "KBOX",
        "KBRO",
        "KBUF",
        "KBYX",
        "KCAE",
        "KCBW",
        "KCBX",
        "KCCX",
        "KCLE",
        "KCLX",
        "KCRP",
        "KCXX",
        "KCYS",
        "KDAX",
        "KDDC",
        "KDFX",
        "KDGX",
        "KDIX",
        "KDLH",
        "KDMX",
        "KDOX",
        "KDTX",
        "KDVN",
        "KDYX",
        "KEAX",
        "KEMX",
        "KENX",
        "KEOX",
        "KEPZ",
        "KESX",
        "KEVX",
        "KEWX",
        "KEYX",
        "KFCX",
        "KFDR",
        "KFDX",
        "KFFC",
        "KFSD",
        "KFSX",
        "KFTG",
        "KFWS",
        "KGGW",
        "KGJX",
        "KGLD",
        "KGRB",
        "KGRK",
        "KGRR",
        "KGSP",
        "KGWX",
        "KGYX",
        "KHDX",
        "KHGX",
        "KHNX",
        "KHPX",
        "KHTX",
        "KICT",
        "KICX",
        "KILN",
        "KILX",
        "KIND",
        "KINX",
        "KIWA",
        "KIWX",
        "KJAX",
        "KJGX",
        "KJKL",
        "KLBB",
        "KLCH",
        "KLGX",
        "KLIX",
        "KLNX",
        "KLOT",
        "KLRX",
        "KLSX",
        "KLTX",
        "KLVX",
        "KLWX",
        "KLZK",
        "KMAF",
        "KMAX",
        "KMBX",
        "KMHX",
        "KMKX",
        "KMLB",
        "KMOB",
        "KMPX",
        "KMQT",
        "KMRX",
        "KMSX",
        "KMTX",
        "KMUX",
        "KMVX",
        "KMXX",
        "KNKX",
        "KNQA",
        "KOAX",
        "KOHX",
        "KOKX",
        "KOTX",
        "KPAH",
        "KPBZ",
        "KPDT",
        "KPOE",
        "KPUX",
        "KRAX",
        "KRGX",
        "KRIW",
        "KRLX",
        "KSFX",
        "KSGF",
        "KSHV",
        "KSJT",
        "KSOX",
        "KSRX",
        "KTBW",
        "KTFX",
        "KTLX",
        "KTWX",
        "KTYX",
        "KUDX",
        "KUEX",
        "KVAX",
        "KVBX",
        "KVNX",
        "KVTX",
        "KVWX",
        "KYUX",
        "PABC",
        "PACG",
        "PAEC",
        "PAHG",
        "PAIH",
        "PAKC",
        "PAPD",
        "PGUA",
        "PHKI",
        "PHKM",
        "PHMO",
        "PHWA",
        "TJUA",
    ]
)

# S3 bucket and prefix format
BUCKET = "noaa-nexrad-level2"


@dataclass
class ScanInfo:
    """Metadata about a single NEXRAD scan file on S3."""

    key: str
    filename: str
    last_modified: datetime
    size_bytes: int

    @property
    def scan_time(self) -> Optional[datetime]:
        """Parse scan time from filename (e.g. KTLX20130520_201643_V06)."""
        m = re.search(r"(\d{8})_(\d{6})", self.filename)
        if not m:
            return None
        try:
            return datetime.strptime(f"{m.group(1)}{m.group(2)}", "%Y%m%d%H%M%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None


def _s3_client():
    """Return an anonymous S3 client (NOAA bucket is public)."""
    return boto3.client(
        "s3",
        config=Config(signature_version=UNSIGNED),
        region_name="us-east-1",
    )


def validate_site(site: str) -> None:
    """Raise ValueError if site code is not a valid 4-letter ICAO identifier."""
    if not SITE_RE.match(site):
        raise ValueError(
            f"Invalid site code '{site}'. Expected a 4-letter uppercase ICAO "
            f"identifier (e.g. KTLX, KFWS)."
        )
    if site not in KNOWN_NEXRAD_SITES:
        raise ValueError(
            f"Unknown NEXRAD site code '{site}'. Use a valid WSR-88D site code (e.g. KTLX, KFWS)."
        )


def list_scans(site: str, dt: datetime, window_minutes: int = 30) -> list[ScanInfo]:
    """List NEXRAD scan files on S3 near the requested datetime.

    Args:
        site: 4-letter ICAO site code (e.g. 'KTLX').
        dt: Target datetime (UTC). Window is ±window_minutes around this time.
        window_minutes: Half-width of the time window to search.

    Returns:
        List of ScanInfo objects, sorted by scan time.

    Raises:
        ValueError: If site code format is invalid.
        RuntimeError: If S3 listing fails.
    """
    validate_site(site)

    s3 = _s3_client()
    prefix = f"{dt.year}/{dt.month:02d}/{dt.day:02d}/{site}/"

    try:
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=BUCKET, Prefix=prefix)
        all_objects = []
        for page in pages:
            all_objects.extend(page.get("Contents", []))
    except Exception as exc:
        raise RuntimeError(f"Failed to list S3 objects: {exc}") from exc

    if not all_objects:
        return []

    window = timedelta(minutes=window_minutes)
    dt_utc = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    start = dt_utc - window
    end = dt_utc + window

    scans = []
    for obj in all_objects:
        key = obj["Key"]
        filename = key.split("/")[-1]
        # Skip metadata/index files
        if filename.endswith(".gz") or "_MDM" not in filename:
            if not filename.endswith("_MDM"):
                info = ScanInfo(
                    key=key,
                    filename=filename,
                    last_modified=obj["LastModified"],
                    size_bytes=obj["Size"],
                )
                t = info.scan_time
                if t is not None and start <= t <= end:
                    scans.append(info)

    scans.sort(key=lambda s: s.scan_time or datetime.min.replace(tzinfo=timezone.utc))
    return scans


def find_closest_scan(scans: list[ScanInfo], dt: datetime) -> Optional[ScanInfo]:
    """Return the scan closest in time to dt."""
    if not scans:
        return None
    dt_utc = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return min(scans, key=lambda s: abs((s.scan_time or dt_utc) - dt_utc))


def download_scan(scan: ScanInfo, output_path: Path) -> Path:
    """Download a scan file from S3 to output_path.

    Args:
        scan: ScanInfo object with the S3 key to download.
        output_path: Local path to write the file to.

    Returns:
        The output_path after successful download.

    Raises:
        RuntimeError: If download fails.
    """
    s3 = _s3_client()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        s3.download_file(BUCKET, scan.key, str(output_path))
    except Exception as exc:
        raise RuntimeError(f"Failed to download {scan.key}: {exc}") from exc

    return output_path
