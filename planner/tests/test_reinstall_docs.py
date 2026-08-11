"""Tests for reinstall guide generation."""

from __future__ import annotations

import sys
from pathlib import Path

PLANNER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLANNER_DIR))

from reinstall_docs import build_aliases_section, build_homebrew_section, build_pyenv_section, build_reinstall_guide  # noqa: E402


def test_pyenv_guide_includes_shims_and_init():
    snapshot = {
        "shell_config_lines": {
            "/Users/x/.zprofile": [
                '.zprofile:12: eval "$(pyenv init - zsh)"',
            ]
        },
        "python": {
            "pyenv": {
                "installed": True,
                "which_python": "/Users/x/.pyenv/shims/python",
                "uses_pyenv_shims": True,
                "global": "3.12.9",
                "versions": ["3.12.9", "3.11.8"],
                "python_version": "Python 3.12.9",
                "version": "3.12.9 (set by /Users/x/.pyenv/version)",
                "root": "/Users/x/.pyenv",
            }
        },
        "homebrew": {"installed": False},
        "node": {"nvm": {}},
        "pipx": {},
    }
    lines = build_pyenv_section(snapshot, "en")
    text = "\n".join(lines)
    assert "pyenv init" in text
    assert "3.12.9" in text
    assert "shims" in text.lower()
    assert "which python" in text


def test_homebrew_guide_includes_bundle():
    snapshot = {
        "homebrew": {
            "installed": True,
            "prefix": "/opt/homebrew",
            "formula_count": 42,
            "cask_count": 3,
            "brewfile": "/Users/x/migration-inventory/Brewfile",
            "shellenv_lines": ['eval "$(/opt/homebrew/bin/brew shellenv)"'],
        },
        "python": {"pyenv": {"installed": False}},
        "node": {"nvm": {}},
        "pipx": {},
    }
    text = "\n".join(build_homebrew_section(snapshot, "en"))
    assert "brew bundle install" in text
    assert "/opt/homebrew" in text
    assert "shellenv" in text


def test_aliases_section_one_step_restore():
    snapshot = {
        "aliases": {
            "count": 2,
            "items": [
                {
                    "name": "ll",
                    "definition": "ls -la",
                    "source_file": ".zshrc",
                    "line": 3,
                    "raw": "alias ll='ls -la'",
                },
            ],
        },
    }
    manifest = {"restore_command": "/tmp/mac-migration restore all --inventory-dir /tmp/inv"}
    text = "\n".join(build_aliases_section(snapshot, "en", manifest))
    assert "restore.sh" in text
    assert "automatic" in text.lower()
    assert "`ll`" in text


def test_full_guide_self_contained():
    snapshot = {
        "shell_config_lines": {},
        "python": {"pyenv": {"installed": False}},
        "homebrew": {"installed": True, "prefix": "/opt/homebrew", "shellenv_lines": [], "formula_count": 1, "cask_count": 0},
        "node": {"nvm": {}},
        "pipx": {},
    }
    guide = build_reinstall_guide(snapshot, "en")
    assert "self-contained" in guide.lower()
    assert "Brewfile" in guide
