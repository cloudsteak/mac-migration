"""Tests for tool detection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

COLLECTOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COLLECTOR_DIR))

from detect_tools import build_inventory, detect_tool  # noqa: E402


def test_detect_tool_from_cli_only(monkeypatch, tmp_path: Path):
    def fake_which(name: str) -> str:
        return f"/opt/homebrew/bin/{name}" if name == "terraform" else ""

    import detect_tools as dt

    monkeypatch.setattr(dt, "which", fake_which)
    monkeypatch.setattr(dt, "run", lambda cmd, timeout=20: "Terraform v1.9.0")
    item = detect_tool("Terraform", "devops", (), (), ("terraform",))
    assert item is not None
    assert "terraform" in item["cli"]


def test_build_inventory_structure(tmp_path: Path, monkeypatch):
    import detect_tools as dt

    monkeypatch.setattr(dt, "find_apps_matching", lambda p: [])
    monkeypatch.setattr(dt, "find_app_support", lambda p: [])
    monkeypatch.setattr(dt, "find_cli", lambda p: {})
    monkeypatch.setattr(dt, "scan_extra_ai_folders", lambda: [])
    monkeypatch.setattr(dt, "ai_extensions", lambda: {})
    monkeypatch.setattr(dt, "tenv_snapshot", lambda: {"installed": False})
    monkeypatch.setattr(dt, "go_snapshot", lambda: {"installed": False})

    data = build_inventory(tmp_path)
    assert "tools" in data
    assert "by_category" in data
    assert "tool_count" in data
