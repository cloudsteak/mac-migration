"""Tests for restore manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESTORER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESTORER_DIR))

from manifest import build_manifest, write_manifest  # noqa: E402


def test_build_manifest_includes_aliases(tmp_path: Path):
    inv = tmp_path / "inventory"
    inv.mkdir()
    (inv / "environment-snapshot.json").write_text(
        json.dumps(
            {
                "aliases": {"count": 2, "items": [{"name": "k", "raw": "alias k='kubectl'"}]},
                "shell_config_lines": {"/x/.zshrc": [".zshrc:1: eval \"$(pyenv init - zsh)\""]},
                "homebrew": {"shellenv_lines": ['eval "$(/opt/homebrew/bin/brew shellenv)"']},
            }
        ),
        encoding="utf-8",
    )
    (inv / "Brewfile").write_text('brew "git"\n', encoding="utf-8")
    (inv / "homebrew-inventory.json").write_text(
        json.dumps({"formula_count": 1, "cask_count": 0}),
        encoding="utf-8",
    )
    (inv / "vscode-extensions.json").write_text(
        json.dumps({"editors": [{"extensions": [{"id": "ms-python.python"}]}]}),
        encoding="utf-8",
    )

    manifest = build_manifest(inv, tmp_path / "mac-migration-root")
    ids = {c["id"] for c in manifest["components"]}
    assert "aliases" in ids
    assert "shell" in ids
    assert "homebrew" in ids
    assert "vscode" in ids
    assert "restore all" in manifest["restore_command"]


def test_write_manifest_creates_restore_sh(tmp_path: Path):
    inv = tmp_path / "inventory"
    inv.mkdir()
    (inv / "environment-snapshot.json").write_text(
        json.dumps({"aliases": {"count": 1, "items": []}, "homebrew": {}}),
        encoding="utf-8",
    )
    tool = tmp_path / "tool"
    tool.mkdir()
    write_manifest(inv, tool)
    assert (inv / "restore-manifest.json").exists()
    wrapper = (inv / "restore.sh").read_text(encoding="utf-8")
    assert "mac-migration" in wrapper
    assert "restore all" in wrapper
