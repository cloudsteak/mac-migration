"""Tests for install group builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ANALYZER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYZER_DIR))

from install_groups import build_install_groups  # noqa: E402


def test_homebrew_group_lists_formulae(tmp_path: Path):
    inventory = tmp_path / "inventory"
    inventory.mkdir()
    (inventory / "homebrew-inventory.json").write_text(
        json.dumps(
            {
                "formulae": [
                    {"name": "awscli", "version": "2.0"},
                    {"name": "jq", "version": "1.7"},
                ],
                "casks": [{"name": "iterm2", "version": "3.5"}],
            }
        ),
        encoding="utf-8",
    )
    components = [
        {
            "component_id": "brew:formula:awscli",
            "component_name": "awscli",
            "type": "homebrew_formula",
            "decision": "reinstall",
            "install_steps": ["brew install awscli"],
        }
    ]
    groups = build_install_groups(components, inventory, "en")
    homebrew = next(g for g in groups if g["group_id"] == "homebrew")
    names = [c["name"] for c in homebrew["children"]]
    assert "AWS CLI" in names
    assert "jq" in names
    assert "iterm2" in names
    assert homebrew["group_steps"]


def test_ableton_ecosystem_groups_plugins(tmp_path: Path):
    inventory = tmp_path / "inventory"
    inventory.mkdir()
    (inventory / "homebrew-inventory.json").write_text("{}", encoding="utf-8")
    (inventory / "custom-paths.json").write_text(
        json.dumps(
            {
                "paths": [
                    {
                        "path": "/Users/x/Library/Application Support/FabFilter",
                        "name": "FabFilter",
                        "kind": "profiled_folder",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    components = [
        {
            "component_id": "tool:creative:ableton_live",
            "component_name": "Ableton Live",
            "type": "tool_creative",
            "decision": "migrate",
            "install_steps": ["Install Ableton"],
        },
        {
            "component_id": "folder:/Library/Application Support/iZotope",
            "component_name": "iZotope",
            "type": "profiled_folder",
            "decision": "migrate",
            "related_paths": [{"path": "/Library/Application Support/iZotope", "size_human": "1G"}],
            "install_steps": ["Copy iZotope"],
        },
    ]
    groups = build_install_groups(components, inventory, "en")
    ableton = next(g for g in groups if g["group_id"] == "ecosystem:ableton_live")
    child_names = [c["name"] for c in ableton["children"]]
    assert "iZotope" in child_names
    assert "FabFilter" in child_names
    assert ableton["parent"]["name"] == "Ableton Live"
