"""Tests for component discovery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ANALYZER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYZER_DIR))

from discovery import (  # noqa: E402
    components_from_collector_folders,
    discover_components,
    discovery_summary,
    merge_components,
    parse_applications_md,
    scan_home_all_entries,
)


def test_parse_applications_md(tmp_path: Path):
    md = tmp_path / "01-applications.md"
    md.write_text(
        "## /Applications\n"
        "drwxr-xr-x  Foo.app\n"
        "## ~/Applications (user-scope)\n"
        "drwxr-xr-x  Bar.app\n",
        encoding="utf-8",
    )
    apps = parse_applications_md(md)
    assert len(apps) == 2
    assert apps[0]["name"] == "Foo.app"


def test_scan_home_all_entries(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".zshrc").write_text("# zsh", encoding="utf-8")
    (tmp_path / "Documents").mkdir()
    items = scan_home_all_entries(tmp_path)
    names = {i["name"] for i in items}
    assert ".git" in names
    assert ".zshrc" in names
    assert "Documents" in names


def test_all_collector_folders_become_components(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    inventory = tmp_path / "inventory"
    inventory.mkdir()
    folders = [
        {"path": str(home / "Documents"), "size_bytes": 1000, "size_human": "1K"},
        {"path": str(home / "dev"), "size_bytes": 2000, "size_human": "2K"},
        {"path": "/Applications/Foo.app", "size_bytes": 3000, "size_human": "3K"},
    ]
    (inventory / "collector-output.json").write_text(
        json.dumps({"folders": folders}),
        encoding="utf-8",
    )
    components = discover_components(inventory, folders, home=home)
    profiled = [c for c in components if c["type"] == "profiled_folder"]
    assert len(profiled) == 3
    summary = discovery_summary(components)
    assert summary["profiled_folders"] == 3
    assert summary["total_components"] >= 3


def test_merge_components_prefers_existing():
    a = {"id": "x", "paths": ["/a"], "profile": {"size_bytes": 1}, "tags": ["t1"]}
    b = {"id": "x", "paths": ["/b"], "profile": {}, "tags": ["t2"], "sensitive": True}
    merged = merge_components([a, b])
    assert len(merged) == 1
    assert merged[0]["sensitive"] is True
    assert set(merged[0]["paths"]) == {"/a", "/b"}
