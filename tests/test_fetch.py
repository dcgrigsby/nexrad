"""Unit tests for nexrad_fetch core logic."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.nexrad_fetch.fetch import ScanInfo, find_closest_scan, list_scans, validate_site


def test_validate_site_valid():
    validate_site("KTLX")
    validate_site("KFWS")
    validate_site("KLSX")


def test_validate_site_invalid():
    with pytest.raises(ValueError, match="Invalid site code"):
        validate_site("ktlx")
    with pytest.raises(ValueError, match="Invalid site code"):
        validate_site("KTL")
    with pytest.raises(ValueError, match="Invalid site code"):
        validate_site("KTLXZ")


def test_scan_info_parse_time():
    scan = ScanInfo(
        key="2013/05/20/KTLX/KTLX20130520_201643_V06",
        filename="KTLX20130520_201643_V06",
        last_modified=datetime(2013, 5, 20, 20, 16, 43, tzinfo=timezone.utc),
        size_bytes=10_000_000,
    )
    t = scan.scan_time
    assert t is not None
    assert t.year == 2013
    assert t.month == 5
    assert t.day == 20
    assert t.hour == 20
    assert t.minute == 16


def test_find_closest_scan():
    dt = datetime(2013, 5, 20, 20, 16, 43, tzinfo=timezone.utc)
    scans = [
        ScanInfo(
            key="k1",
            filename="KTLX20130520_200000_V06",
            last_modified=dt,
            size_bytes=1000,
        ),
        ScanInfo(
            key="k2",
            filename="KTLX20130520_201600_V06",
            last_modified=dt,
            size_bytes=1000,
        ),
        ScanInfo(
            key="k3",
            filename="KTLX20130520_210000_V06",
            last_modified=dt,
            size_bytes=1000,
        ),
    ]
    closest = find_closest_scan(scans, dt)
    assert closest is not None
    assert "201600" in closest.filename


def test_find_closest_scan_empty():
    dt = datetime(2013, 5, 20, 20, 16, 43, tzinfo=timezone.utc)
    result = find_closest_scan([], dt)
    assert result is None


@patch("src.nexrad_fetch.fetch.boto3")
def test_list_scans_calls_s3(mock_boto3):
    """Verify list_scans constructs the correct S3 prefix and filters results."""
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3

    dt = datetime(2013, 5, 20, 20, 16, 43, tzinfo=timezone.utc)

    mock_paginator = MagicMock()
    mock_s3.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [
        {
            "Contents": [
                {
                    "Key": "2013/05/20/KTLX/KTLX20130520_201643_V06",
                    "Size": 5_000_000,
                    "LastModified": dt,
                },
                {
                    "Key": "2013/05/20/KTLX/KTLX20130520_000000_V06",
                    "Size": 5_000_000,
                    "LastModified": dt,
                },
            ]
        }
    ]

    scans = list_scans("KTLX", dt, window_minutes=30)

    # Should find the scan within the 30-minute window
    assert len(scans) == 1
    assert "201643" in scans[0].filename
