"""Tests for shell alias parsing."""

from __future__ import annotations

import sys
from pathlib import Path

COLLECTOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COLLECTOR_DIR))

from shell_aliases import (  # noqa: E402
    extract_aliases_from_file,
    merge_aliases,
    parse_alias_line,
    render_aliases_fragment,
)


def test_parse_single_quoted_alias():
    parsed = parse_alias_line("alias ll='ls -la'")
    assert parsed is not None
    assert parsed["name"] == "ll"
    assert parsed["definition"] == "ls -la"
    assert parsed["raw"] == "alias ll='ls -la'"


def test_parse_double_quoted_alias():
    parsed = parse_alias_line('alias gs="git status"')
    assert parsed is not None
    assert parsed["name"] == "gs"
    assert parsed["definition"] == "git status"


def test_parse_unquoted_alias():
    parsed = parse_alias_line("alias l=ls")
    assert parsed is not None
    assert parsed["name"] == "l"
    assert parsed["definition"] == "ls"


def test_skip_comments_and_blanks():
    assert parse_alias_line("# alias x=1") is None
    assert parse_alias_line("") is None


def test_extract_from_file(tmp_path: Path):
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(
        "# config\nalias ll='ls -la'\nalias gs='git status'\n",
        encoding="utf-8",
    )
    items = extract_aliases_from_file(zshrc)
    assert len(items) == 2
    assert items[0]["line"] == 2
    assert items[0]["source_file"] == ".zshrc"


def test_merge_later_overrides():
    first = {"name": "ll", "definition": "ls", "raw": "alias ll=ls"}
    second = {"name": "ll", "definition": "ls -la", "raw": "alias ll='ls -la'"}
    merged = merge_aliases([first, second])
    assert len(merged) == 1
    assert merged[0]["definition"] == "ls -la"


def test_extract_follows_source_from_zshrc(tmp_path: Path):
    zsh_dir = tmp_path / ".zsh"
    zsh_dir.mkdir()
    fragment = zsh_dir / "cloud-prompt.zsh"
    fragment.write_text("alias k='kubectl'\n", encoding="utf-8")
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(f"source {fragment}\n", encoding="utf-8")

    from shell_aliases import extract_aliases  # noqa: WPS433

    data = extract_aliases(tmp_path)
    assert data["count"] == 1
    assert data["items"][0]["name"] == "k"
    assert str(fragment) in data["scanned_files"]


def test_render_fragment():
    body = render_aliases_fragment(
        [{"raw": "alias ll='ls -la'"}],
        header="# mac-migration aliases",
    )
    assert "alias ll='ls -la'" in body
    assert body.endswith("\n")
