#!/usr/bin/env python3
"""Capture shell, PATH, pyenv, Homebrew and runtime manager configuration."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from shell_aliases import extract_aliases, render_aliases_fragment

HOME = Path.home()
OUT_DIR = HOME / "migration-inventory"

SHELL_FILES = (
    HOME / ".zprofile",
    HOME / ".zshrc",
    HOME / ".zshenv",
    HOME / ".bash_profile",
    HOME / ".bashrc",
    HOME / ".profile",
)

TOOL_PATTERNS = re.compile(
    r"pyenv|brew shellenv|nvm|rbenv|asdf|sdkman|tenv|tfenv|tgenv|"
    r"PYENV|NVM_DIR|GOPATH|cargo env|direnv|fnm|jenv|chruby",
    re.IGNORECASE,
)


def run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return (result.stdout or result.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def which(name: str) -> str:
    return run(["/usr/bin/which", name])


def extract_shell_lines() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in SHELL_FILES:
        if not path.is_file():
            continue
        lines: list[str] = []
        try:
            for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if TOOL_PATTERNS.search(line):
                    lines.append(f"{path.name}:{i}: {line.rstrip()}")
        except OSError:
            continue
        if lines:
            found[str(path)] = lines
    return found


def pyenv_snapshot() -> dict:
    info: dict = {"installed": bool(which("pyenv"))}
    if not info["installed"]:
        return info

    info["executable"] = which("pyenv")
    info["root"] = os.environ.get("PYENV_ROOT") or str(HOME / ".pyenv")
    info["global"] = run(["pyenv", "global"])
    info["version"] = run(["pyenv", "version"])
    info["versions_raw"] = run(["pyenv", "versions"])
    version_re = re.compile(r"^\*?\s*(\d+\.\d+\.\d+)\s")
    info["versions"] = []
    for line in info["versions_raw"].splitlines():
        match = version_re.match(line.strip())
        if match:
            info["versions"].append(match.group(1))
    plugins_dir = Path(info["root"]) / "plugins"
    if plugins_dir.is_dir():
        info["plugins"] = sorted(p.name for p in plugins_dir.iterdir() if p.is_dir())
    else:
        info["plugins"] = []

    info["which_python"] = which("python")
    info["which_python3"] = which("python3")
    info["python_version"] = run(["python", "--version"])
    info["python3_version"] = run(["python3", "--version"])
    wp = info.get("which_python", "")
    info["uses_pyenv_shims"] = "/.pyenv/shims/" in wp
    info["uses_pyenv_python"] = info["uses_pyenv_shims"] or "/.pyenv/versions/" in wp

    return info


def homebrew_snapshot(inventory_dir: Path) -> dict:
    brew = which("brew")
    info: dict = {"installed": bool(brew)}
    if not info["installed"]:
        return info

    info["executable"] = brew
    info["prefix"] = run(["brew", "--prefix"])
    info["version"] = run(["brew", "--version"]).splitlines()[:1]
    info["config"] = run(["brew", "config"])
    info["formula_count"] = len(run(["brew", "list", "--formula"]).splitlines())
    info["cask_count"] = len(run(["brew", "list", "--cask"]).splitlines())
    brewfile = inventory_dir / "Brewfile"
    info["brewfile"] = str(brewfile) if brewfile.exists() else None
    info["bundle_check"] = run(["brew", "bundle", "check", f"--file={brewfile}"]) if brewfile.exists() else ""

    shellenv = run([brew, "shellenv"])
    info["shellenv_command"] = shellenv
    info["shellenv_lines"] = [ln for ln in shellenv.splitlines() if ln.strip()]

    return info


def nvm_snapshot() -> dict:
    nvm_dir = os.environ.get("NVM_DIR") or str(HOME / ".nvm")
    info: dict = {"installed": (HOME / ".nvm").is_dir() or bool(os.environ.get("NVM_DIR"))}
    info["nvm_dir"] = nvm_dir
    versions_root = Path(nvm_dir) / "versions" / "node"
    if versions_root.is_dir():
        info["versions"] = sorted(p.name for p in versions_root.iterdir() if p.is_dir())
    else:
        info["versions"] = []
    info["which_node"] = which("node")
    info["node_version"] = run(["node", "--version"]) if info["which_node"] else ""
    return info


def rbenv_snapshot() -> dict:
    info: dict = {"installed": bool(which("rbenv"))}
    if info["installed"]:
        info["versions_raw"] = run(["rbenv", "versions"])
        info["global"] = run(["rbenv", "global"])
    return info


def npm_snapshot() -> dict:
    npm = which("npm")
    info: dict = {"installed": bool(npm)}
    if npm:
        info["prefix"] = run(["npm", "prefix", "-g"])
        info["global_packages"] = run(["npm", "list", "-g", "--depth=0"])
    return info


def pipx_snapshot() -> dict:
    pipx = which("pipx")
    info: dict = {"installed": bool(pipx)}
    if pipx:
        info["list"] = run(["pipx", "list"])
    return info


def build_snapshot(inventory_dir: Path) -> dict:
    alias_data = extract_aliases()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shell": os.environ.get("SHELL", ""),
        "path": os.environ.get("PATH", ""),
        "shell_config_lines": extract_shell_lines(),
        "aliases": alias_data,
        "python": {
            "system_python3": run(["/usr/bin/python3", "--version"]),
            "which_python3": which("python3"),
            "pyenv": pyenv_snapshot(),
        },
        "homebrew": homebrew_snapshot(inventory_dir),
        "node": {"nvm": nvm_snapshot(), "npm": npm_snapshot()},
        "ruby": {"rbenv": rbenv_snapshot()},
        "pipx": pipx_snapshot(),
    }


def render_markdown(snapshot: dict) -> str:
    ts = snapshot.get("generated_at", "")
    lines = [
        f"# Shell & runtime environment — {ts}",
        "",
        "Structured data: `environment-snapshot.json` (used by reinstall guide).",
        "",
        f"## Shell: `{snapshot.get('shell', '')}`",
        "",
        "### PATH (current session)",
        "```",
        snapshot.get("path", ""),
        "```",
        "",
    ]

    pyenv = snapshot.get("python", {}).get("pyenv", {})
    lines.extend(["## Python / pyenv", ""])
    if pyenv.get("installed"):
        lines.extend(
            [
                f"- pyenv executable: `{pyenv.get('executable', '')}`",
                f"- PYENV_ROOT: `{pyenv.get('root', '')}`",
                f"- global: `{pyenv.get('global', '')}`",
                f"- active: `{pyenv.get('version', '')}`",
                f"- which python: `{pyenv.get('which_python', '')}`",
                f"- which python3: `{pyenv.get('which_python3', '')}`",
                f"- uses pyenv (not system python): **{pyenv.get('uses_pyenv_python', pyenv.get('uses_pyenv_shims', False))}**",
                "",
                "### Installed pyenv versions",
                "```",
                pyenv.get("versions_raw", ""),
                "```",
                "",
            ]
        )
        if pyenv.get("plugins"):
            lines.append(f"Plugins: {', '.join(pyenv['plugins'])}")
            lines.append("")
    else:
        lines.append("pyenv not detected in PATH.")
        lines.append("")

    brew = snapshot.get("homebrew", {})
    lines.extend(["## Homebrew", ""])
    if brew.get("installed"):
        lines.extend(
            [
                f"- brew: `{brew.get('executable', '')}`",
                f"- prefix: `{brew.get('prefix', '')}`",
                f"- formulae: {brew.get('formula_count', 0)}, casks: {brew.get('cask_count', 0)}",
                f"- Brewfile: `{brew.get('brewfile', '')}`",
                "",
                "### brew shellenv (add to shell profile on new Mac)",
                "```bash",
                *brew.get("shellenv_lines", []),
                "```",
                "",
            ]
        )
    else:
        lines.append("Homebrew not installed.")
        lines.append("")

    lines.extend(["## Shell config lines (tool init)", ""])
    shell_lines = snapshot.get("shell_config_lines") or {}
    if shell_lines:
        for path, cfg_lines in shell_lines.items():
            lines.append(f"### `{path}`")
            lines.append("```bash")
            lines.extend(line.split(": ", 1)[-1] if ": " in line else line for line in cfg_lines)
            lines.append("```")
            lines.append("")
    else:
        lines.append("(no pyenv/brew/nvm/rbenv lines found in common shell files)")
        lines.append("")

    alias_data = snapshot.get("aliases") or {}
    lines.extend(["## Shell aliases", ""])
    if alias_data.get("count"):
        lines.append(f"**{alias_data['count']}** unique alias(es) captured from shell profiles.")
        scanned = alias_data.get("scanned_files") or []
        if scanned:
            lines.append("")
            lines.append("Scanned files (including `source` from `.zshrc`):")
            for path in scanned:
                lines.append(f"- `{path}`")
        lines.append("")
        lines.append("Restore on new Mac (automatic):")
        lines.append("```bash")
        lines.append("bash ~/migration-inventory/restore.sh")
        lines.append("```")
        lines.append("")
        lines.append("Or run components: `./mac-migration restore aliases`")
        lines.append("")
        lines.append("Fragment file: `aliases.zsh`")
        lines.append("")
        for item in alias_data.get("items", []):
            lines.append(f"- `{item['name']}` → `{item['definition']}` _(from {item['source_file']}:{item['line']})_")
        lines.append("")
    else:
        lines.append("(no aliases found in `.zshrc`, `.zprofile`, or other shell files)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    snapshot = build_snapshot(out_dir)
    json_path = out_dir / "environment-snapshot.json"
    md_path = out_dir / "09-shell-environment.md"
    alias_data = snapshot.get("aliases") or {}

    if alias_data.get("items"):
        header = (
            f"# mac-migration aliases — captured {snapshot.get('generated_at', '')}\n"
            "# Applied by: mac-migration restore aliases"
        )
        fragment_path = out_dir / "aliases.zsh"
        fragment_path.write_text(
            render_aliases_fragment(alias_data["items"], header=header),
            encoding="utf-8",
        )
        alias_data["fragment_path"] = str(fragment_path)
        snapshot["aliases"] = alias_data

    json_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(snapshot), encoding="utf-8")
    print(f"==> Environment snapshot: {json_path}")
    print(f"==> Environment report: {md_path}")
    if alias_data.get("count"):
        print(f"==> Aliases: {alias_data['count']} → {out_dir / 'aliases.zsh'}")


if __name__ == "__main__":
    main()
