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


def test_detect_tool_includes_home_config(monkeypatch, tmp_path: Path):
    import detect_tools as dt

    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text("[default]", encoding="utf-8")

    monkeypatch.setattr(dt, "HOME", tmp_path)
    monkeypatch.setattr(dt, "find_apps_matching", lambda p: [])
    monkeypatch.setattr(dt, "find_app_support", lambda p: [])
    monkeypatch.setattr(
        dt,
        "find_cli",
        lambda bins: {"aws": "/opt/homebrew/bin/aws (aws-cli/2.36.0)"} if "aws" in bins else {},
    )
    monkeypatch.setattr(dt, "dir_size_human", lambda p: "4K")

    item = detect_tool("AWS CLI", "devops", (), (), ("aws",), (".aws",))
    assert item is not None
    assert str(aws_dir) in item["paths"]
    assert item["config_paths"] == [str(aws_dir)]


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
