"""Unit tests for nexrad_transform color mapping and PLY structure."""
from __future__ import annotations

import io
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import pytest

from src.nexrad_transform.colors import dbz_to_rgb_vectorized
from src.nexrad_transform.ply_writer import write_ply_ascii, write_ply_binary


class TestColorMapping:
    def test_returns_correct_shape(self):
        dbz = np.array([5.0, 20.0, 35.0, 50.0, 65.0], dtype=np.float32)
        rgb = dbz_to_rgb_vectorized(dbz)
        assert rgb.shape == (5, 3)
        assert rgb.dtype == np.uint8

    def test_below_minimum_clamps_to_first_color(self):
        dbz = np.array([1.0], dtype=np.float32)
        rgb = dbz_to_rgb_vectorized(dbz)
        assert rgb.shape == (1, 3)
        # Should clamp to first color entry
        assert all(v >= 0 for v in rgb[0])

    def test_different_dbz_bins_give_different_colors(self):
        dbz = np.array([10.0, 30.0, 50.0], dtype=np.float32)
        rgb = dbz_to_rgb_vectorized(dbz)
        # Not all the same color
        assert not np.all(rgb[0] == rgb[1])
        assert not np.all(rgb[1] == rgb[2])

    def test_colors_are_valid_rgb_range(self):
        dbz = np.linspace(5, 75, 100, dtype=np.float32)
        rgb = dbz_to_rgb_vectorized(dbz)
        assert np.all(rgb >= 0)
        assert np.all(rgb <= 255)


class TestPlyWriterAscii:
    def _make_data(self, n=5):
        x = np.zeros(n, dtype=np.float32)
        y = np.zeros(n, dtype=np.float32)
        z = np.arange(n, dtype=np.float32)
        r = np.full(n, 255, dtype=np.uint8)
        g = np.zeros(n, dtype=np.uint8)
        b = np.zeros(n, dtype=np.uint8)
        return x, y, z, r, g, b

    def test_writes_correct_vertex_count(self, tmp_path):
        x, y, z, r, g, b = self._make_data(10)
        out = tmp_path / "test.ply"
        n = write_ply_ascii(out, x, y, z, r, g, b)
        assert n == 10
        assert out.exists()

    def test_ply_header_has_required_properties(self, tmp_path):
        x, y, z, r, g, b = self._make_data(3)
        out = tmp_path / "test.ply"
        write_ply_ascii(out, x, y, z, r, g, b)
        content = out.read_text()
        assert "ply" in content
        assert "element vertex 3" in content
        assert "property float x" in content
        assert "property float y" in content
        assert "property float z" in content
        assert "property uchar red" in content
        assert "property uchar green" in content
        assert "property uchar blue" in content
        assert "end_header" in content

    def test_vertex_count_matches_data_lines(self, tmp_path):
        x, y, z, r, g, b = self._make_data(7)
        out = tmp_path / "test.ply"
        write_ply_ascii(out, x, y, z, r, g, b)
        content = out.read_text()
        lines = content.split("\n")
        header_end = next(i for i, l in enumerate(lines) if l.strip() == "end_header")
        data_lines = [l for l in lines[header_end + 1 :] if l.strip()]
        assert len(data_lines) == 7


class TestPlyWriterBinary:
    def test_binary_header_is_correct(self, tmp_path):
        x = np.array([1.0, 2.0], dtype=np.float32)
        y = np.array([0.0, 0.0], dtype=np.float32)
        z = np.array([0.0, 0.0], dtype=np.float32)
        r = np.array([255, 0], dtype=np.uint8)
        g = np.array([0, 255], dtype=np.uint8)
        b = np.array([0, 0], dtype=np.uint8)
        out = tmp_path / "test.ply"
        n = write_ply_binary(out, x, y, z, r, g, b)
        assert n == 2
        header = out.read_bytes().split(b"end_header\n")[0].decode("ascii")
        assert "binary_little_endian" in header
        assert "element vertex 2" in header

    def test_binary_file_size_is_correct(self, tmp_path):
        n_pts = 100
        x = np.zeros(n_pts, dtype=np.float32)
        y = np.zeros(n_pts, dtype=np.float32)
        z = np.arange(n_pts, dtype=np.float32)
        r = np.full(n_pts, 128, dtype=np.uint8)
        g = np.full(n_pts, 64, dtype=np.uint8)
        b = np.zeros(n_pts, dtype=np.uint8)
        out = tmp_path / "test.ply"
        write_ply_binary(out, x, y, z, r, g, b)
        content = out.read_bytes()
        header, data = content.split(b"end_header\n", 1)
        # Each point: 3×float32 (12 bytes) + 3×uint8 (3 bytes) = 15 bytes
        assert len(data) == n_pts * 15
