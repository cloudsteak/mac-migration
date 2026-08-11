"""Tests for custom path discovery."""

from __future__ import annotations

import sys
from pathlib import Path

COLLECTOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COLLECTOR_DIR))

from capture_custom_paths import classify_home_entry, classify_library_entry  # noqa: E402


def test_home_custom_detected(tmp_path: Path):
    (tmp_path / "dev").mkdir()
    (tmp_path / "Documents").mkdir()
    assert classify_home_entry(tmp_path / "dev") == "home_dir"
    assert classify_home_entry(tmp_path / "Documents") is None


def test_library_custom_detected(tmp_path: Path):
    (tmp_path / "MyCustomApp").mkdir()
    (tmp_path / "Safari").mkdir()
    assert classify_library_entry(tmp_path / "MyCustomApp") == "library_custom"
    assert classify_library_entry(tmp_path / "Safari") is None
