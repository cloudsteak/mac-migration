"""Tests for Quick Actions capture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

COLLECTOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COLLECTOR_DIR))

from capture_quick_actions import build_snapshot, discover_workflows, parse_workflow  # noqa: E402


def test_parse_workflow_from_fixture(tmp_path: Path):
    wf = tmp_path / "Test Action.workflow"
    contents = wf / "Contents"
    contents.mkdir(parents=True)
    (contents / "Info.plist").write_bytes(
        b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>NSServices</key>
  <array><dict>
    <key>NSMenuItem</key><dict><key>default</key><string>Do Thing</string></dict>
    <key>NSSendFileTypes</key><array><string>public.item</string></array>
  </dict></array>
</dict></plist>"""
    )
    (contents / "document.wflow").write_bytes(
        b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>actions</key>
  <array><dict><key>action</key><dict>
    <key>ActionName</key><string>Run Shell Script</string>
    <key>ActionParameters</key><dict>
      <key>COMMAND_STRING</key><string>echo hi</string>
    </dict>
  </dict></dict></array>
</dict></plist>"""
    )
    parsed = parse_workflow(wf)
    assert parsed["name"] == "Do Thing"
    assert parsed["file_types"] == ["public.item"]
    assert "Run Shell Script" in parsed["actions"]


def test_build_snapshot_copies_workflow(tmp_path: Path, monkeypatch):
    services = tmp_path / "Library" / "Services"
    services.mkdir(parents=True)
    wf = services / "Copy Me.workflow"
    contents = wf / "Contents"
    contents.mkdir(parents=True)
    (contents / "Info.plist").write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict></dict></plist>'
    )
    (contents / "document.wflow").write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict></dict></plist>'
    )

    monkeypatch.setattr("capture_quick_actions.HOME", tmp_path)
    monkeypatch.setattr("capture_quick_actions.SERVICES_DIRS", (services,))
    monkeypatch.setattr("capture_quick_actions.discover_shortcuts", lambda: [])

    inv = tmp_path / "inventory"
    data = build_snapshot(inv)
    assert data["workflow_count"] == 1
    assert (inv / "quick-actions/workflows/Copy Me.workflow").is_dir()
