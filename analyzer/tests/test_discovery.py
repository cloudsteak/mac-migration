"""Tests for component discovery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ANALYZER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANALYZER_DIR))

from discovery import (  # noqa: E402
    components_from_collector_folders,
    consolidate_for_interactive,
    discover_components,
    discovery_summary,
    merge_components,
    parse_applications_md,
    scan_directory_children,
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


def test_scan_directory_children_permission_denied(tmp_path: Path, monkeypatch):
    blocked = tmp_path / "Mail"
    blocked.mkdir()

    def raise_permission(self):
        raise PermissionError("[Errno 1] Operation not permitted")

    monkeypatch.setattr(Path, "iterdir", raise_permission)
    assert scan_directory_children(blocked, comp_type="library_item", source="test", prefix="mail") == []


def test_consolidate_for_interactive_groups_noise(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()

    components = [
        {
            "id": "editor:vscode",
            "type": "vscode_editor",
            "name": "VS Code",
            "source": "vscode-extensions",
            "paths": [str(home / ".vscode")],
            "profile": {"extension_count": 3, "extensions": [{"id": "a"}, {"id": "b"}, {"id": "c"}]},
            "tags": ["editor"],
        },
        {
            "id": "vscode_ext:ms-python.python",
            "type": "vscode_extension",
            "name": "Python",
            "source": "Visual Studio Code",
            "paths": [str(home / ".vscode/extensions/ms-python.python")],
            "profile": {"id": "ms-python.python"},
            "tags": ["vscode_extension"],
        },
        {
            "id": "vscode_ext:random.theme-pack",
            "type": "vscode_extension",
            "name": "Neon Theme Pack",
            "source": "Visual Studio Code",
            "paths": [],
            "profile": {"id": "random.theme-pack"},
            "tags": ["vscode_extension"],
        },
        {
            "id": "brew:formula:git",
            "type": "homebrew_formula",
            "name": "git",
            "source": "homebrew-inventory",
            "paths": [],
            "profile": {},
            "tags": ["homebrew"],
        },
        {
            "id": "brew:formula:libunistring",
            "type": "homebrew_formula",
            "name": "libunistring",
            "source": "homebrew-inventory",
            "paths": [],
            "profile": {},
            "tags": ["homebrew"],
        },
        {
            "id": "brew:cask:firefox",
            "type": "homebrew_cask",
            "name": "firefox",
            "source": "homebrew-inventory",
            "paths": [],
            "profile": {},
            "tags": ["homebrew"],
        },
        {
            "id": "app:Docker.app",
            "type": "application",
            "name": "Docker.app",
            "source": "system",
            "paths": ["/Applications/Docker.app"],
            "tags": ["application"],
        },
        {
            "id": "app:App.app",
            "type": "application",
            "name": "App.app",
            "source": "system",
            "paths": ["/Applications/App.app"],
            "tags": ["application"],
        },
        {
            "id": "alias:ll",
            "type": "shell_alias",
            "name": "alias ll",
            "source": ".zshrc",
            "paths": [],
            "profile": {"definition": "ll='ls -la'"},
            "tags": ["shell"],
        },
        {
            "id": "folder:small",
            "type": "profiled_folder",
            "name": "small",
            "source": "collector",
            "paths": [str(home / "small")],
            "profile": {"size_bytes": 1024},
            "total_size_bytes": 1024,
            "tags": ["profiled"],
        },
        {
            "id": "folder:large",
            "type": "profiled_folder",
            "name": "large",
            "source": "collector",
            "paths": [str(home / "large")],
            "profile": {"size_bytes": 200 * 1024 * 1024},
            "total_size_bytes": 200 * 1024 * 1024,
            "tags": ["profiled"],
        },
        {
            "id": "browser_ext:Chrome:abc",
            "type": "browser_extension",
            "name": "Chrome: uBlock",
            "source": "system-inventory",
            "paths": [],
            "profile": {"browser": "Chrome", "name": "uBlock"},
            "tags": ["browser"],
        },
        {
            "id": "custom:/Users/x/.cache",
            "type": "custom_home_dotdir",
            "name": ".cache",
            "source": "custom-paths",
            "paths": [str(home / ".cache")],
            "profile": {},
            "tags": ["custom"],
        },
    ]

    review = consolidate_for_interactive(components, min_size_bytes=100 * 1024 * 1024)
    types = {item["type"] for item in review}
    names = {item["name"] for item in review}

    assert "vscode_extension" in types
    assert "homebrew_formula" in types
    assert "homebrew_cask" in types
    assert "application" in types
    assert "applications_group" in types
    assert "shell_alias" not in types
    assert "browser_extension" not in types
    assert "custom_home_dotdir" not in types
    assert "vscode_editor" in types
    assert "Python" in names
    assert "Docker.app" in names
    assert "App.app" not in {item["name"] for item in review if item["type"] == "application"}
    assert any("Other Homebrew formulae" in name for name in names)
    assert any("Other Visual Studio Code extensions" in name for name in names)
    assert any(item["name"] == "large" for item in review)
    assert not any(item["name"] == "small" for item in review)


def test_merge_components_prefers_existing():
    a = {"id": "x", "paths": ["/a"], "profile": {"size_bytes": 1}, "tags": ["t1"]}
    b = {"id": "x", "paths": ["/b"], "profile": {}, "tags": ["t2"], "sensitive": True}
    merged = merge_components([a, b])
    assert len(merged) == 1
    assert merged[0]["sensitive"] is True
    assert set(merged[0]["paths"]) == {"/a", "/b"}
