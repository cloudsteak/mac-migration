#!/usr/bin/env python3
"""Dynamic restore engine — apply captured inventory on a new Mac."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

COLLECTOR_DIR = Path(__file__).resolve().parents[1] / "collector"
sys.path.insert(0, str(COLLECTOR_DIR))

from shell_aliases import render_aliases_fragment  # noqa: E402

DEFAULT_INVENTORY = Path.home() / "migration-inventory"
MARKER = "# mac-migration: aliases block"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_aliases_fragment(inventory_dir: Path, snapshot: dict) -> Path:
    alias_data = snapshot.get("aliases") or {}
    items = alias_data.get("items") or []
    fragment = inventory_dir / "aliases.zsh"
    if items and not fragment.exists():
        header = (
            f"# mac-migration aliases — captured {snapshot.get('generated_at', '')}\n"
            "# Managed by: mac-migration restore aliases"
        )
        fragment.write_text(render_aliases_fragment(items, header=header), encoding="utf-8")
    return fragment


def restore_aliases(inventory_dir: Path, *, dry_run: bool = False) -> dict:
    snapshot_path = inventory_dir / "environment-snapshot.json"
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Missing {snapshot_path}")
    snapshot = load_json(snapshot_path)
    items = (snapshot.get("aliases") or {}).get("items") or []
    if not items:
        return {"applied": 0, "message": "No aliases in inventory"}

    fragment = ensure_aliases_fragment(inventory_dir, snapshot)
    zshrc = Path.home() / ".zshrc"
    source_line = f'source "{fragment}"'

    if dry_run:
        return {
            "applied": len(items),
            "zshrc": str(zshrc),
            "fragment": str(fragment),
            "source_line": source_line,
            "dry_run": True,
        }

    zshrc.touch(exist_ok=True)
    text = zshrc.read_text(encoding="utf-8", errors="replace")
    if MARKER not in text:
        zshrc.write_text(
            text.rstrip()
            + f"\n\n{MARKER}\n{source_line}\n",
            encoding="utf-8",
        )
        print(f"==> Added alias block to {zshrc}")
    else:
        print(f"==> Alias block already in {zshrc}")

    return {"applied": len(items), "fragment": str(fragment)}


def restore_shell(inventory_dir: Path, *, dry_run: bool = False) -> dict:
    snapshot_path = inventory_dir / "environment-snapshot.json"
    snapshot = load_json(snapshot_path)
    lines: list[str] = []

    brew = snapshot.get("homebrew") or {}
    for line in brew.get("shellenv_lines") or []:
        if line.strip():
            lines.append(line.strip())

    seen: set[str] = set()
    for entries in (snapshot.get("shell_config_lines") or {}).values():
        for entry in entries:
            line = entry.split(": ", 1)[-1].strip()
            if line and line not in seen:
                seen.add(line)
                lines.append(line)

    if not lines:
        return {"applied": 0, "message": "No shell init lines in inventory"}

    zshrc = Path.home() / ".zshrc"
    marker = "# mac-migration: shell init block"

    if dry_run:
        return {"applied": len(lines), "lines": lines, "dry_run": True}

    zshrc.touch(exist_ok=True)
    text = zshrc.read_text(encoding="utf-8", errors="replace")
    if marker not in text:
        block = "\n".join([marker, *lines]) + "\n"
        zshrc.write_text(text.rstrip() + "\n\n" + block, encoding="utf-8")
        print(f"==> Added {len(lines)} shell init line(s) to {zshrc}")
    else:
        print(f"==> Shell init block already in {zshrc}")

    return {"applied": len(lines)}


def restore_homebrew(inventory_dir: Path, *, dry_run: bool = False) -> dict:
    brewfile = inventory_dir / "Brewfile"
    if not brewfile.exists():
        return {"applied": 0, "message": "No Brewfile in inventory"}

    cmd = ["brew", "bundle", "install", f"--file={brewfile}"]
    if dry_run:
        return {"command": " ".join(cmd), "dry_run": True}

    print(f"==> Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=False)
    return {"applied": 1, "brewfile": str(brewfile)}


def restore_vscode(inventory_dir: Path, *, dry_run: bool = False) -> dict:
    data_path = inventory_dir / "vscode-extensions.json"
    if not data_path.exists():
        return {"applied": 0, "message": "No vscode-extensions.json in inventory"}

    data = load_json(data_path)
    installed = 0
    commands: list[str] = []
    for editor in data.get("editors") or []:
        cli = editor.get("cli") or editor.get("editor")
        if not cli:
            continue
        for ext in editor.get("extensions") or []:
            ext_id = ext.get("id")
            if not ext_id:
                continue
            cmd = [cli, "--install-extension", ext_id]
            commands.append(" ".join(cmd))
            if dry_run:
                continue
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                installed += 1
                print(f"==> Installed {ext_id} ({editor.get('name', cli)})")
            else:
                print(f"==> Skip/fail {ext_id}: {result.stderr.strip() or result.stdout.strip()}")

    if dry_run:
        return {"commands": commands, "count": len(commands), "dry_run": True}
    return {"applied": installed, "attempted": len(commands)}


def restore_quick_actions(inventory_dir: Path, *, dry_run: bool = False) -> dict:
    data_path = inventory_dir / "quick-actions-inventory.json"
    if not data_path.exists():
        return {"applied": 0, "message": "No quick-actions-inventory.json in inventory"}

    data = load_json(data_path)
    src_root = inventory_dir / "quick-actions" / "workflows"
    dest_root = Path.home() / "Library" / "Services"
    workflows = data.get("automator_workflows") or []

    if not workflows:
        return {
            "applied": 0,
            "shortcuts_listed": len(data.get("shortcuts_app") or []),
            "message": "No Automator workflows; Shortcuts.app items need manual/iCloud setup",
        }

    if dry_run:
        return {
            "workflows": [w.get("bundle_name") for w in workflows],
            "dest": str(dest_root),
            "shortcuts": [s.get("name") for s in data.get("shortcuts_app") or []],
            "dry_run": True,
        }

    dest_root.mkdir(parents=True, exist_ok=True)
    copied = 0
    for wf in workflows:
        bundle = wf.get("bundle_name")
        if not bundle:
            continue
        src = src_root / bundle
        if not src.is_dir():
            src = Path(wf.get("path", ""))
        if not src.is_dir():
            continue
        dest = dest_root / bundle
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        copied += 1
        print(f"==> Installed Quick Action: {wf.get('name', bundle)}")

    shortcuts = data.get("shortcuts_app") or []
    if shortcuts:
        print(f"==> Shortcuts.app: {len(shortcuts)} shortcut(s) listed — enable Quick Action in Shortcuts app or use iCloud sync")
        for sc in shortcuts[:10]:
            print(f"    - {sc.get('name', '?')}")
        if len(shortcuts) > 10:
            print(f"    ... and {len(shortcuts) - 10} more (see 14-quick-actions.md)")

    return {"applied": copied, "shortcuts_listed": len(shortcuts)}


def restore_audio(inventory_dir: Path, *, dry_run: bool = False) -> dict:
    data_path = inventory_dir / "audio-devices-inventory.json"
    if not data_path.exists():
        return {"applied": 0, "message": "No audio-devices-inventory.json in inventory"}

    data = load_json(data_path)
    hints = data.get("restore_hints") or []
    casks = data.get("homebrew_audio_casks") or []

    if dry_run:
        return {
            "hints": hints,
            "casks": casks,
            "devices": [d.get("name") for d in data.get("devices") or []],
            "dry_run": True,
        }

    applied = 0
    brew = run_which("brew")
    for hint in hints:
        cmd = hint.get("install_command", "")
        if not cmd.startswith("brew "):
            print(f"==> Manual: {hint.get('product', '?')} — {hint.get('note', '')}")
            continue
        if not brew:
            print(f"==> Skip (no brew): {cmd}")
            continue
        print(f"==> Running: {cmd}")
        subprocess.run(cmd.split(), check=False)
        applied += 1

    if any("blackhole" in h.get("product", "").lower() for h in hints):
        print("==> Tip: restart CoreAudio — sudo killall coreaudiod")

    return {"applied": applied, "hints": len(hints)}


def run_which(name: str) -> str:
    try:
        r = subprocess.run(["/usr/bin/which", name], capture_output=True, text=True, check=False)
        return (r.stdout or "").strip()
    except OSError:
        return ""


RESTORERS = {
    "aliases": restore_aliases,
    "shell": restore_shell,
    "homebrew": restore_homebrew,
    "vscode": restore_vscode,
    "quick-actions": restore_quick_actions,
    "audio": restore_audio,
}


def restore_all(inventory_dir: Path, *, dry_run: bool = False) -> dict:
    results: dict[str, dict] = {}
    for name, func in RESTORERS.items():
        print(f"\n==> Restore: {name}")
        try:
            results[name] = func(inventory_dir, dry_run=dry_run)
        except FileNotFoundError as exc:
            results[name] = {"error": str(exc)}
            print(f"    Skip: {exc}")
        except OSError as exc:
            results[name] = {"error": str(exc)}
            print(f"    Error: {exc}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore captured macOS environment on new Mac")
    parser.add_argument(
        "component",
        nargs="?",
        default="all",
        choices=[*RESTORERS.keys(), "all"],
        help="What to restore (default: all)",
    )
    parser.add_argument(
        "--inventory-dir",
        type=Path,
        default=DEFAULT_INVENTORY,
        help="Path to migration-inventory (default: ~/migration-inventory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be applied without changing the system",
    )
    args = parser.parse_args()
    inventory_dir = args.inventory_dir.expanduser().resolve()

    if not inventory_dir.is_dir():
        print(f"ERROR: inventory dir not found: {inventory_dir}", file=sys.stderr)
        sys.exit(1)

    manifest_path = inventory_dir / "restore-manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        print(f"==> Inventory: {inventory_dir}")
        print(f"==> Components: {len(manifest.get('components') or [])}")
    else:
        print(f"==> Inventory: {inventory_dir} (no restore-manifest.json — run collect on old Mac)")

    if args.component == "all":
        restore_all(inventory_dir, dry_run=args.dry_run)
    else:
        RESTORERS[args.component](inventory_dir, dry_run=args.dry_run)

    print("\n==> Restore complete.")


if __name__ == "__main__":
    main()
