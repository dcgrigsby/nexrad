"""CLI entry point for nexrad-transform."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .transform import transform


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nexrad-transform",
        description=(
            "Transform a NEXRAD Level II archive file into a colored PLY point cloud.\n\n"
            "Processes all elevation tilts from the volume scan and outputs a PLY file\n"
            "with Cartesian coordinates and NWS standard reflectivity colors.\n"
            "Gates with no reflectivity data are filtered out."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  nexrad-transform KTLX20130520_201643_V06 output.ply\n"
            "  nexrad-transform scan.gz output.ply --format binary_little_endian\n"
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the NEXRAD Level II archive file (gzip or uncompressed)",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Path to write the output PLY point cloud file",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["ascii", "binary_little_endian"],
        default="ascii",
        help="PLY output format (default: ascii)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_path: Path = args.input
    output_path: Path = args.output

    print(f"Reading: {input_path}")
    print(f"Output:  {output_path} (format: {args.format})")

    try:
        n = transform(input_path, output_path, fmt=args.format)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: Unexpected failure: {exc}", file=sys.stderr)
        sys.exit(1)

    # AC-3.12: report number of vertices written on success
    print(f"Written {n:,} vertices to {output_path}")
    sys.exit(0)
