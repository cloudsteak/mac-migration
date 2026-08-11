#!/usr/bin/env python3
"""Capture VS Code, Cursor, and compatible editor extensions (CLI + on-disk)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()


def run(cmd: list[str], timeout: int = 60) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def which(name: str) -> str:
    return run(["/usr/bin/which", name])


def parse_extension_folder(name: str) -> dict:
    """Parse publisher.extension-version folder names."""
    match = re.match(r"^(.+)-(\d+\.\d+\.\d+.*)$", name)
    if match:
        ext_id, version = match.group(1), match.group(2)
        if "." in ext_id:
            return {"id": ext_id, "version": version, "source": "disk"}
    return {"id": name, "version": "", "source": "disk"}


def extensions_from_disk(ext_root: Path) -> list[dict]:
    if not ext_root.is_dir():
        return []
    items: list[dict] = []
    try:
        for entry in sorted(ext_root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            info = parse_extension_folder(entry.name)
            info["path"] = str(entry)
            pkg = entry / "package.json"
            if pkg.is_file():
                try:
                    meta = json.loads(pkg.read_text(encoding="utf-8"))
                    info["display_name"] = meta.get("displayName", "")
                    info["publisher"] = meta.get("publisher", "")
                except (json.JSONDecodeError, OSError):
                    pass
            items.append(info)
    except OSError:
        pass
    return items


def extensions_from_cli(cli: str) -> list[dict]:
    if not which(cli):
        return []
    lines = run([cli, "--list-extensions", "--show-versions"]).splitlines()
    items: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "@" in line:
            ext_id, version = line.rsplit("@", 1)
        else:
            ext_id, version = line, ""
        items.append({"id": ext_id, "version": version, "source": "cli"})
    return items


def merge_extensions(*sources: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for items in sources:
        for ext in items:
            ext_id = ext.get("id", "")
            if not ext_id:
                continue
            if ext_id not in by_id:
                by_id[ext_id] = ext
                continue
            existing = by_id[ext_id]
            if ext.get("version") and not existing.get("version"):
                existing["version"] = ext["version"]
            if ext.get("path") and not existing.get("path"):
                existing["path"] = ext["path"]
            if ext.get("display_name") and not existing.get("display_name"):
                existing["display_name"] = ext["display_name"]
    return sorted(by_id.values(), key=lambda e: e.get("id", "").lower())


EDITORS = (
    {
        "key": "vscode",
        "name": "Visual Studio Code",
        "cli": "code",
        "app_support": HOME / "Library/Application Support/Code",
        "ext_dirs": (
            HOME / ".vscode/extensions",
            HOME / ".vscode-insiders/extensions",
        ),
    },
    {
        "key": "vscode_insiders",
        "name": "VS Code Insiders",
        "cli": "code-insiders",
        "app_support": HOME / "Library/Application Support/Code - Insiders",
        "ext_dirs": (HOME / ".vscode-insiders/extensions",),
    },
    {
        "key": "cursor",
        "name": "Cursor",
        "cli": "cursor",
        "app_support": HOME / "Library/Application Support/Cursor",
        "ext_dirs": (HOME / ".cursor/extensions",),
    },
    {
        "key": "vscodium",
        "name": "VSCodium",
        "cli": "codium",
        "app_support": HOME / "Library/Application Support/VSCodium",
        "ext_dirs": (HOME / ".vscode-oss/extensions",),
    },
)


def capture_editor(editor: dict) -> dict | None:
    cli_exts = extensions_from_cli(editor["cli"])
    disk_exts: list[dict] = []
    for ext_dir in editor["ext_dirs"]:
        disk_exts.extend(extensions_from_disk(ext_dir))

    extensions = merge_extensions(cli_exts, disk_exts)
    if not extensions and not editor["app_support"].is_dir():
        return None

    user_dir = editor["app_support"] / "User"
    paths = {
        "app_support": str(editor["app_support"]) if editor["app_support"].is_dir() else "",
        "user_settings": str(user_dir / "settings.json") if (user_dir / "settings.json").is_file() else "",
        "keybindings": str(user_dir / "keybindings.json") if (user_dir / "keybindings.json").is_file() else "",
        "snippets": str(user_dir / "snippets") if (user_dir / "snippets").is_dir() else "",
        "global_storage": str(user_dir / "globalStorage") if (user_dir / "globalStorage").is_dir() else "",
    }

    return {
        "editor": editor["key"],
        "name": editor["name"],
        "cli": editor["cli"],
        "cli_found": bool(which(editor["cli"])),
        "extension_count": len(extensions),
        "extensions": extensions,
        "paths": paths,
        "reinstall_script_lines": [
            f"# Restore {editor['name']} extensions on new Mac:",
            f"# {editor['cli']} --install-extension <publisher.extension>",
        ]
        + [f"{editor['cli']} --install-extension {e['id']}" for e in extensions],
    }


def build_snapshot() -> dict:
    editors: list[dict] = []
    for ed in EDITORS:
        captured = capture_editor(ed)
        if captured:
            editors.append(captured)

    total = sum(e["extension_count"] for e in editors)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "editor_count": len(editors),
        "total_extensions": total,
        "editors": editors,
    }


def render_markdown(data: dict) -> str:
    lines = [
        f"# VS Code / Cursor extensions — {data.get('generated_at', '')}",
        "",
        f"**{data.get('total_extensions', 0)}** extensions across "
        f"**{data.get('editor_count', 0)}** editor(s). JSON: `vscode-extensions.json`.",
        "",
    ]
    for ed in data.get("editors", []):
        lines.extend(
            [
                f"## {ed.get('name', '?')} (`{ed.get('cli', '')}`)",
                "",
                f"Extensions: **{ed.get('extension_count', 0)}** | CLI available: {ed.get('cli_found')}",
                "",
            ]
        )
        for key, path in (ed.get("paths") or {}).items():
            if path:
                lines.append(f"- {key}: `{path}`")
        lines.append("")
        lines.append("| Extension | Version |")
        lines.append("|---|---|")
        for ext in ed.get("extensions", []):
            name = ext.get("display_name") or ext.get("id", "")
            ver = ext.get("version", "")
            lines.append(f"| `{ext.get('id', name)}` | {ver} |")
        lines.append("")
        lines.append("### Reinstall commands (copy to new Mac)")
        lines.append("```bash")
        for ln in ed.get("reinstall_script_lines", [])[2:]:
            lines.append(ln)
        lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HOME / "migration-inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = build_snapshot()
    json_path = out_dir / "vscode-extensions.json"
    md_path = out_dir / "11-vscode-extensions.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")
    print(f"==> VS Code extensions: {json_path} ({data['total_extensions']} extensions)")
    print(f"==> Report: {md_path}")


if __name__ == "__main__":
    main()
