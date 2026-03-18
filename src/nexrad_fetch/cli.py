"""CLI entry point for nexrad-fetch."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .fetch import download_scan, find_closest_scan, list_scans, validate_site


def parse_datetime(value: str) -> datetime:
    """Parse datetime string in YYYYMMDD_HHMMSS or YYYYMMDD_HHMM format."""
    for fmt in ("%Y%m%d_%H%M%S", "%Y%m%d_%H%M", "%Y%m%d_%H"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Cannot parse datetime '{value}'. Expected format: YYYYMMDD_HHMMSS (e.g. 20130520_201643)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nexrad-fetch",
        description=(
            "Download NEXRAD Level II archive files from s3://unidata-nexrad-level2/.\n\n"
            "Given a site code and a date/time, lists available scans near that time\n"
            "and downloads the closest matching scan."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  nexrad-fetch KTLX 20130520_201643\n"
            "  nexrad-fetch KTLX 20130520_201643 --output /tmp/ktlx_scan.gz\n"
            "  nexrad-fetch KTLX 20130520_201643 --list-only\n"
        ),
    )
    parser.add_argument(
        "site",
        help="4-letter ICAO site code (e.g. KTLX, KFWS)",
    )
    parser.add_argument(
        "datetime",
        type=parse_datetime,
        help="Target date/time in UTC (format: YYYYMMDD_HHMMSS)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path. Defaults to <site>_<datetime>.gz in current directory.",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=30,
        metavar="MINUTES",
        help="Search window in minutes around the target time (default: 30)",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List available scans without downloading",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    site = args.site.upper()

    # Validate site code format
    try:
        validate_site(site)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    dt = args.datetime
    print(f"Searching for {site} scans near {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC...")

    # List scans
    try:
        scans = list_scans(site, dt, window_minutes=args.window)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if not scans:
        print(
            f"Error: No scans found for {site} within {args.window} minutes of "
            f"{dt.strftime('%Y-%m-%d %H:%M:%S')} UTC.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Found {len(scans)} scan(s):")
    for scan in scans:
        t = scan.scan_time
        t_str = t.strftime("%Y-%m-%d %H:%M:%S UTC") if t else "unknown"
        print(f"  {scan.filename}  ({t_str}, {scan.size_bytes:,} bytes)")

    if args.list_only:
        sys.exit(0)

    # Find closest scan
    closest = find_closest_scan(scans, dt)
    if closest is None:
        print("Error: No valid scan found.", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output is not None:
        output_path = args.output
    else:
        t = closest.scan_time
        ts = t.strftime("%Y%m%d_%H%M%S") if t else "unknown"
        output_path = Path(f"{site}_{ts}.gz")

    print(f"Downloading {closest.filename} → {output_path} ...")

    try:
        download_scan(closest, output_path)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Downloaded {output_path} ({output_path.stat().st_size:,} bytes)")
    sys.exit(0)
