#!/usr/bin/env python3
"""Full Homebrew inventory — every formula, cask, tap (non-Apple package manager)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()


def run(cmd: list[str], timeout: int = 120) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def which(name: str) -> str:
    return run(["/usr/bin/which", name])


def parse_versions_output(raw: str) -> list[dict]:
    items: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            name, version = parts[0], parts[1]
        else:
            name, version = line, ""
        items.append({"name": name, "version": version})
    return items


def build_snapshot(inventory_dir: Path) -> dict:
    brew = which("brew")
    if not brew:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "installed": False,
        }

    prefix = run(["brew", "--prefix"])
    formulae = parse_versions_output(run(["brew", "list", "--formula", "--versions"]))
    casks = parse_versions_output(run(["brew", "list", "--cask", "--versions"]))
    taps = [t for t in run(["brew", "tap"]).splitlines() if t.strip()]
    leaves = [t for t in run(["brew", "leaves"]).splitlines() if t.strip()]
    services_raw = run(["brew", "services", "list"])
    services = [ln for ln in services_raw.splitlines() if ln.strip()]

    brewfile = inventory_dir / "Brewfile"
    if brewfile.is_file():
        run(["brew", "bundle", "dump", f"--file={brewfile}", "--force"])

    bundle_violations = run(["brew", "bundle", "check", f"--file={brewfile}"]) if brewfile.is_file() else ""

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "installed": True,
        "prefix": prefix,
        "executable": brew,
        "brew_version": run(["brew", "--version"]).splitlines()[:1],
        "config": run(["brew", "config"]),
        "shellenv": run([brew, "shellenv"]),
        "brewfile": str(brewfile) if brewfile.is_file() else None,
        "formula_count": len(formulae),
        "cask_count": len(casks),
        "tap_count": len(taps),
        "formulae": formulae,
        "casks": casks,
        "taps": taps,
        "leaves": leaves,
        "services": services,
        "bundle_check": bundle_violations,
        "note": "All Homebrew packages are user-installed (not part of stock macOS).",
    }


def render_markdown(data: dict) -> str:
    if not data.get("installed"):
        return "# Homebrew full inventory\n\nHomebrew not installed.\n"

    lines = [
        f"# Homebrew full inventory — {data.get('generated_at', '')}",
        "",
        data.get("note", ""),
        "",
        f"Prefix: `{data.get('prefix', '')}` | Formulae: **{data.get('formula_count', 0)}** | "
        f"Casks: **{data.get('cask_count', 0)}** | Taps: **{data.get('tap_count', 0)}**",
        "",
        "Machine-readable: `homebrew-inventory.json`",
        "",
        "## Taps",
        "```",
        "\n".join(data.get("taps", [])),
        "```",
        "",
        "## Formulae (all)",
        "",
        "| Package | Version |",
        "|---|---|",
    ]
    for f in data.get("formulae", []):
        lines.append(f"| `{f.get('name', '')}` | {f.get('version', '')} |")

    lines.extend(["", "## Casks (all)", "", "| Cask | Version |", "|---|---|"])
    for c in data.get("casks", []):
        lines.append(f"| `{c.get('name', '')}` | {c.get('version', '')} |")

    lines.extend(["", "## Top-level formulae (brew leaves)", "```"])
    lines.extend(data.get("leaves", []))
    lines.extend(["```", "", "## Brew services", "```"])
    lines.extend(data.get("services", []))
    lines.extend(
        [
            "```",
            "",
            "## Restore on new Mac",
            "```bash",
            f"eval \"$({data.get('prefix', '/opt/homebrew')}/bin/brew shellenv)\"",
            "brew bundle install --file=~/migration-inventory/Brewfile",
            "```",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HOME / "migration-inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = build_snapshot(out_dir)
    json_path = out_dir / "homebrew-inventory.json"
    md_path = out_dir / "12-homebrew-full.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")

    if data.get("installed"):
        print(
            f"==> Homebrew inventory: {json_path} "
            f"({data.get('formula_count', 0)} formulae, {data.get('cask_count', 0)} casks)"
        )
    else:
        print("==> Homebrew not installed — skipped")
    print(f"==> Report: {md_path}")


if __name__ == "__main__":
    main()
