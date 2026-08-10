"""Tests for full system inventory."""

from __future__ import annotations

import sys
from pathlib import Path

COLLECTOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COLLECTOR_DIR))

from capture_system_inventory import scan_dot_directories, scan_git_config  # noqa: E402


def test_scan_dot_directories(tmp_path, monkeypatch):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".pyenv").mkdir()
    (tmp_path / "Documents").mkdir()
    monkeypatch.setattr("capture_system_inventory.HOME", tmp_path)
    items = scan_dot_directories()
    names = {i["name"] for i in items}
    assert ".cursor" in names
    assert ".pyenv" in names
    assert "Documents" not in names


def test_scan_git_config_redacts(tmp_path, monkeypatch):
    cfg = tmp_path / ".gitconfig"
    cfg.write_text(
        "[user]\n\tname = Test User\n\temail = test@example.com\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("capture_system_inventory.HOME", tmp_path)
    result = scan_git_config()
    assert result["exists"] is True
    assert result["sections"]["user"]["email"] == "[REDACTED_EMAIL]"
