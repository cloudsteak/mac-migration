"""Tests for interactive component report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ANALYZER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYZER_DIR))

from interactive_report import (  # noqa: E402
    build_install_steps,
    collect_related_paths,
    decisions_to_report_entries,
    write_interactive_markdown,
)


def test_collect_related_paths_merges_sources():
    entry = {
        "paths": ["/Applications/Docker.app"],
        "related_paths": ["/Users/x/Library/Application Support/Docker"],
        "related_folders": [{"path": "/Users/x/Library/Containers/com.docker", "size_human": "1G"}],
        "analysis": {
            "local_files_en": ["/Users/x/.docker"],
            "settings_and_config_en": ["/Users/x/.docker/config.json"],
        },
    }
    rows = collect_related_paths(entry, "en")
    paths = {r["path"] for r in rows}
    assert "/Applications/Docker.app" in paths
    assert "/Users/x/Library/Application Support/Docker" in paths
    assert "/Users/x/Library/Containers/com.docker" in paths
    assert "/Users/x/.docker" in paths


def test_build_install_steps_homebrew_cask():
    entry = {
        "decision": "reinstall",
        "type": "homebrew_cask",
        "component_name": "iterm2",
        "paths": [],
        "analysis": {},
    }
    steps = build_install_steps(entry, Path("/tmp/inventory"), "en")
    assert any("brew install --cask iterm2" in s for s in steps)


def test_build_install_steps_vscode_extension():
    entry = {
        "decision": "reinstall",
        "type": "vscode_extension",
        "component_name": "Python",
        "component_id": "vscode_ext:ms-python.python",
        "source": "Visual Studio Code",
        "paths": ["/Users/x/.vscode/extensions/ms-python.python-2026.4.0"],
        "analysis": {},
    }
    steps = build_install_steps(entry, Path("/tmp/inventory"), "en")
    assert any("ms-python.python" in s for s in steps)


def test_write_interactive_markdown_component_sections(tmp_path: Path):
    store = {
        "decisions": {
            "app:Docker.app": {
                "component_id": "app:Docker.app",
                "component_name": "Docker.app",
                "type": "application",
                "decision": "reinstall",
                "paths": ["/Applications/Docker.app"],
                "related_folders": [],
                "analysis": {
                    "what_it_is_en": "Container platform.",
                    "migration_guidance_en": "Install Docker Desktop from docker.com.",
                    "confidence": 0.9,
                },
            }
        }
    }
    out = tmp_path / "report.md"
    write_interactive_markdown(store, tmp_path, out, "en", Path("report_HU.md"))
    text = out.read_text(encoding="utf-8")
    assert "Docker.app" in text
    assert "Related folders & paths" in text
    assert "Installation / migration steps" in text
    assert "brew install" in text or "Install Docker" in text or "docker.com" in text


def test_write_interactive_json_includes_folder_results(tmp_path: Path):
    from interactive_report import write_interactive_json

    store = {
        "decisions": {
            "dot:.pyenv": {
                "decision": "migrate",
                "component_id": "dot:.pyenv",
                "component_name": ".pyenv",
                "type": "profiled_folder",
                "analysis": {"migration_guidance_en": "Copy pyenv."},
                "related_folders": [{"path": "/Users/x/.pyenv", "size_human": "2G", "size_bytes": 2_000_000_000}],
            }
        }
    }
    out = tmp_path / "analysis-report.json"
    write_interactive_json(store, tmp_path, out, {"mode": "interactive_report"})
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["result_count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["path"] == "/Users/x/.pyenv"
    assert data["component_count"] == 1


def test_decisions_to_report_entries_skips_quit():
    store = {"decisions": {"a": {"decision": "quit"}, "b": {"decision": "migrate", "component_name": "X"}}}
    entries = decisions_to_report_entries(store)
    assert len(entries) == 1
    assert entries[0]["component_name"] == "X"
