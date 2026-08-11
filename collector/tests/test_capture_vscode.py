"""Tests for VS Code extension capture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

COLLECTOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COLLECTOR_DIR))

from capture_vscode import extensions_from_disk, merge_extensions, parse_extension_folder  # noqa: E402


def test_parse_extension_folder():
    info = parse_extension_folder("ms-python.python-2024.0.0")
    assert info["id"] == "ms-python.python"
    assert info["version"] == "2024.0.0"


def test_merge_extensions():
    a = [{"id": "a.b", "version": "1.0", "source": "cli"}]
    b = [{"id": "a.b", "path": "/x", "source": "disk"}]
    merged = merge_extensions(a, b)
    assert len(merged) == 1
    assert merged[0]["version"] == "1.0"
    assert merged[0]["path"] == "/x"


def test_extensions_from_disk(tmp_path: Path):
    ext = tmp_path / "ms-python.python-2024.0.0"
    ext.mkdir()
    (ext / "package.json").write_text(
        json.dumps({"displayName": "Python", "publisher": "ms-python"}),
        encoding="utf-8",
    )
    items = extensions_from_disk(tmp_path)
    assert len(items) == 1
    assert items[0]["display_name"] == "Python"
