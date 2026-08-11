"""Parse shell alias definitions from zsh/bash profile files."""

from __future__ import annotations

import os
import re
from pathlib import Path

# alias name='value' | alias name="value" | alias name=value
ALIAS_RE = re.compile(
    r"^\s*alias\s+"
    r"(?P<name>[\w.-]+)="
    r"(?:'(?P<sq>[^']*)'|\"(?P<dq>[^\"]*)\"|(?P<uq>[^\s#]+))"
    r"\s*(?:#.*)?$"
)

SOURCE_LINE_RE = re.compile(
    r"(?:^|\]\s*&&\s*)(?:source|\.\s+)\s*"
    r"(?:\"(?P<dq>[^\"]+)\"|'(?P<sq>[^']+)'|(?P<bare>[^\s#;]+))"
)

SHELL_FILES = (
    ".zshenv",
    ".zprofile",
    ".zshrc",
    ".zlogin",
    ".bash_profile",
    ".bashrc",
    ".profile",
)

MAX_SOURCED_FILES = 64


def resolve_source_path(raw: str, referrer: Path, home: Path) -> Path | None:
    value = raw.strip().strip('"').strip("'")
    if not value:
        return None
    value = os.path.expandvars(value)
    if value.startswith("~/"):
        candidate = home / value[2:]
    elif value.startswith("$HOME/"):
        candidate = home / value[len("$HOME/") :]
    else:
        path = Path(value)
        candidate = path if path.is_absolute() else referrer.parent / path
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    return resolved if resolved.is_file() else None


def find_sourced_paths(path: Path, home: Path) -> list[Path]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    found: list[Path] = []
    seen: set[Path] = set()
    for line in text.splitlines():
        for match in SOURCE_LINE_RE.finditer(line):
            raw = match.group("dq") or match.group("sq") or match.group("bare") or ""
            resolved = resolve_source_path(raw, path, home)
            if resolved and resolved not in seen:
                seen.add(resolved)
                found.append(resolved)
    return found


def walk_shell_files(home: Path) -> list[Path]:
    """Depth-first walk of shell profiles and files they source."""
    ordered: list[Path] = []
    visited: set[Path] = set()

    def add_file(path: Path) -> None:
        if path in visited or not path.is_file() or len(visited) >= MAX_SOURCED_FILES:
            return
        visited.add(path)
        ordered.append(path)
        for sourced in find_sourced_paths(path, home):
            add_file(sourced)

    for name in SHELL_FILES:
        add_file(home / name)
    return ordered


def parse_alias_line(line: str) -> dict | None:
    """Return alias dict from a single line, or None if not an alias."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    match = ALIAS_RE.match(line)
    if not match:
        return None
    definition = match.group("sq")
    if definition is None:
        definition = match.group("dq")
    if definition is None:
        definition = match.group("uq") or ""
    return {
        "name": match.group("name"),
        "definition": definition,
        "raw": stripped,
    }


def extract_aliases_from_file(path: Path) -> list[dict]:
    items: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return items
    for line_no, line in enumerate(lines, 1):
        parsed = parse_alias_line(line)
        if not parsed:
            continue
        items.append(
            {
                **parsed,
                "source_file": path.name,
                "source_path": str(path),
                "line": line_no,
            }
        )
    return items


def merge_aliases(items: list[dict]) -> list[dict]:
    """Later files override earlier ones (zsh load order)."""
    by_name: dict[str, dict] = {}
    for item in items:
        by_name[item["name"]] = item
    return sorted(by_name.values(), key=lambda x: x["name"].lower())


def extract_aliases(home: Path | None = None) -> dict:
    root = home or Path.home()
    scanned = walk_shell_files(root)
    all_items: list[dict] = []
    by_file: dict[str, list[dict]] = {}
    sourced_from: dict[str, list[str]] = {}
    for path in scanned:
        file_items = extract_aliases_from_file(path)
        if file_items:
            by_file[str(path)] = file_items
            all_items.extend(file_items)
        for sourced in find_sourced_paths(path, root):
            sourced_from.setdefault(str(sourced), [])
            if str(path) not in sourced_from[str(sourced)]:
                sourced_from[str(sourced)].append(str(path))
    merged = merge_aliases(all_items)
    return {
        "count": len(merged),
        "items": merged,
        "by_file": by_file,
        "sourced_from": sourced_from,
        "scanned_files": [str(p) for p in scanned],
    }


def render_aliases_fragment(items: list[dict], *, header: str) -> str:
    lines = [header, ""]
    for item in items:
        lines.append(item["raw"])
    return "\n".join(lines).rstrip() + "\n"
