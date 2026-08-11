#!/usr/bin/env python3
"""
generate-reinstall-guide.py — Phase D: self-contained reinstall documentation

Reads environment-snapshot.json from collector and writes step-by-step guides
so the new Mac can be rebuilt without browsing external documentation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reinstall_docs import build_reinstall_guide

_ANALYZER_DIR = Path(__file__).resolve().parents[1] / "analyzer"
sys.path.append(str(_ANALYZER_DIR))

from paths import report_paths  # noqa: E402

INVENTORY_DIR = Path.home() / "migration-inventory"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase D — self-contained reinstall guide (Homebrew, pyenv, etc.)"
    )
    parser.add_argument(
        "--inventory-dir",
        type=Path,
        default=INVENTORY_DIR,
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="environment-snapshot.json path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=INVENTORY_DIR / "reinstall-guide.md",
    )
    args = parser.parse_args()

    snapshot_path = args.snapshot or (args.inventory_dir / "environment-snapshot.json")
    if not snapshot_path.exists():
        print(
            f"ERROR: {snapshot_path} not found.\n"
            "Run: ./mac-migration collect  (includes environment capture)",
            file=sys.stderr,
        )
        sys.exit(1)

    snapshot = load_json(snapshot_path)
    interactive_path = args.inventory_dir / "interactive-decisions.json"
    interactive = load_json(interactive_path) if interactive_path.exists() else None
    tools_path = args.inventory_dir / "tools-inventory.json"
    tools_data = load_json(tools_path) if tools_path.exists() else None
    vscode_path = args.inventory_dir / "vscode-extensions.json"
    vscode_data = load_json(vscode_path) if vscode_path.exists() else None
    homebrew_path = args.inventory_dir / "homebrew-inventory.json"
    homebrew_data = load_json(homebrew_path) if homebrew_path.exists() else None
    quick_actions_path = args.inventory_dir / "quick-actions-inventory.json"
    quick_actions_data = load_json(quick_actions_path) if quick_actions_path.exists() else None
    audio_path = args.inventory_dir / "audio-devices-inventory.json"
    audio_data = load_json(audio_path) if audio_path.exists() else None
    manifest_path = args.inventory_dir / "restore-manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else None

    md_paths = report_paths(args.output)
    for lang in ("en", "hu"):
        body = build_reinstall_guide(
            snapshot,
            lang,
            interactive=interactive,
            tools_data=tools_data,
            vscode_data=vscode_data,
            homebrew_data=homebrew_data,
            manifest=manifest,
            quick_actions_data=quick_actions_data,
            audio_data=audio_data,
        )
        link = (
            "> **Language:** English | [Magyar](reinstall-guide_HU.md)\n\n"
            if lang == "en"
            else "> **Nyelv:** [English](reinstall-guide.md) | Magyar\n\n"
        )
        md_paths[lang].write_text(link + body, encoding="utf-8")

    print(f"Done: {md_paths['en']}")
    print(f"Done: {md_paths['hu']}")


if __name__ == "__main__":
    main()
