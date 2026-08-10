#!/usr/bin/env python3
"""Capture macOS Quick Actions — Automator workflows and Shortcuts.app."""

from __future__ import annotations

import json
import plistlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
SERVICES_DIRS = (
    HOME / "Library" / "Services",
    HOME / "Library" / "Workflows",
)


def run(cmd: list[str], timeout: int = 60) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def read_plist(path: Path) -> dict | list | None:
    if not path.is_file():
        return None
    try:
        with path.open("rb") as fh:
            return plistlib.load(fh)
    except (OSError, plistlib.InvalidFileException):
        return None


def parse_workflow(workflow_path: Path) -> dict:
    info_path = workflow_path / "Contents" / "Info.plist"
    doc_path = workflow_path / "Contents" / "document.wflow"
    info = read_plist(info_path) or {}
    doc = read_plist(doc_path) or {}

    menu_label = workflow_path.stem
    file_types: list[str] = []
    services = info.get("NSServices") or []
    if services and isinstance(services, list):
        service = services[0] if services else {}
        if isinstance(service, dict):
            menu = service.get("NSMenuItem") or {}
            if isinstance(menu, dict):
                menu_label = menu.get("default") or menu_label
            send_types = service.get("NSSendFileTypes") or []
            if isinstance(send_types, list):
                file_types = [str(t) for t in send_types]

    actions: list[str] = []
    for action in doc.get("actions") or []:
        if not isinstance(action, dict):
            continue
        inner = action.get("action") or {}
        name = inner.get("ActionName")
        if name:
            actions.append(str(name))

    shell_script = ""
    for action in doc.get("actions") or []:
        inner = (action or {}).get("action") or {}
        params = inner.get("ActionParameters") or {}
        cmd = params.get("COMMAND_STRING")
        if cmd:
            shell_script = str(cmd)
            break

    return {
        "name": menu_label,
        "path": str(workflow_path),
        "bundle_name": workflow_path.name,
        "type": "automator_workflow",
        "source_dir": workflow_path.parent.name,
        "file_types": file_types,
        "actions": actions,
        "shell_script_preview": shell_script[:500] if shell_script else "",
        "restore_method": "copy_to_library_services",
    }


def discover_workflows() -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for root in SERVICES_DIRS:
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or not entry.name.endswith(".workflow"):
                continue
            if entry.name in seen:
                continue
            seen.add(entry.name)
            items.append(parse_workflow(entry))
    return items


def discover_shortcuts() -> list[dict]:
    if not run(["/usr/bin/which", "shortcuts"]):
        return []
    names = [ln.strip() for ln in run(["shortcuts", "list"]).splitlines() if ln.strip()]
    return [
        {
            "name": name,
            "type": "shortcuts_app",
            "restore_method": "shortcuts_icloud_or_manual",
            "restore_note": (
                "Enable in Shortcuts app: open shortcut → Info → "
                "'Use as Quick Action' / Finder. With same Apple ID, iCloud may sync automatically."
            ),
        }
        for name in names
    ]


def copy_workflows(workflows: list[dict], out_dir: Path) -> list[str]:
    dest_root = out_dir / "quick-actions" / "workflows"
    dest_root.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for wf in workflows:
        src = Path(wf["path"])
        if not src.is_dir():
            continue
        dest = dest_root / wf["bundle_name"]
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        wf["inventory_copy"] = str(dest)
        copied.append(wf["bundle_name"])
    return copied


def build_snapshot(out_dir: Path) -> dict:
    workflows = discover_workflows()
    shortcuts = discover_shortcuts()
    copied = copy_workflows(workflows, out_dir) if workflows else []
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "automator_workflows": workflows,
        "shortcuts_app": shortcuts,
        "workflow_count": len(workflows),
        "shortcuts_count": len(shortcuts),
        "copied_workflows": copied,
        "restore_command": "./mac-migration restore quick-actions",
        "restore_steps": {
            "automator": "Copies .workflow bundles to ~/Library/Services/ (Finder Quick Actions)",
            "shortcuts": "Lists shortcuts — enable Quick Action in Shortcuts app or rely on iCloud sync",
        },
    }


def render_markdown(data: dict) -> str:
    lines = [
        f"# Quick Actions — {data.get('generated_at', '')}",
        "",
        f"**{data.get('workflow_count', 0)}** Automator workflow(s), "
        f"**{data.get('shortcuts_count', 0)}** Shortcuts.app shortcut(s).",
        "",
        "JSON: `quick-actions-inventory.json`",
        "",
        "Restore on new Mac:",
        "```bash",
        "bash ~/migration-inventory/restore.sh",
        "# or:",
        "./mac-migration restore quick-actions",
        "```",
        "",
    ]

    if data.get("automator_workflows"):
        lines.extend(["## Automator Quick Actions (~/Library/Services)", ""])
        for wf in data["automator_workflows"]:
            lines.append(f"### {wf.get('name', '?')}")
            lines.append(f"- Bundle: `{wf.get('bundle_name', '')}`")
            if wf.get("file_types"):
                lines.append(f"- Input types: {', '.join(wf['file_types'])}")
            if wf.get("actions"):
                lines.append(f"- Actions: {', '.join(wf['actions'])}")
            if wf.get("shell_script_preview"):
                lines.append("- Shell script preview:")
                lines.append("```bash")
                lines.append(wf["shell_script_preview"])
                lines.append("```")
            lines.append("")

    if data.get("shortcuts_app"):
        lines.extend(["## Shortcuts.app", ""])
        lines.append("These may appear as Quick Actions when enabled in Shortcuts:")
        lines.append("")
        for sc in data["shortcuts_app"]:
            lines.append(f"- **{sc.get('name', '?')}**")
        lines.append("")
        lines.append(
            "On new Mac: sign in with same Apple ID for iCloud sync, or recreate and enable "
            "'Use as Quick Action' in each shortcut's settings."
        )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HOME / "migration-inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = build_snapshot(out_dir)
    json_path = out_dir / "quick-actions-inventory.json"
    md_path = out_dir / "14-quick-actions.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")

    print(f"==> Quick Actions: {json_path} ({data['workflow_count']} workflows, {data['shortcuts_count']} shortcuts)")
    print(f"==> Report: {md_path}")
    if data.get("copied_workflows"):
        print(f"==> Workflow copies: {out_dir / 'quick-actions/workflows'}")


if __name__ == "__main__":
    main()
