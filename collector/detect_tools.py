#!/usr/bin/env python3
"""Detect AI assistants, dev tools, and creative apps installed on this Mac."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
OUT_DIR = HOME / "migration-inventory"

# (display name, category, patterns for .app basename, App Support folder names, CLI binaries)
TOOL_CATALOG: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = (
    # AI assistants & coding AI
    ("Cursor", "ai_coding", ("Cursor",), ("Cursor",), ("cursor",)),
    ("Claude Desktop", "ai_assistant", ("Claude",), ("Claude", "com.anthropic.claudefordesktop"), ("claude",)),
    ("ChatGPT", "ai_assistant", ("ChatGPT", "ChatGPT Atlas"), ("com.openai.chat", "ChatGPT"), ()),
    ("GitHub Copilot", "ai_coding", (), (), ("gh copilot",)),
    ("OpenAI Codex CLI", "ai_coding", (), (), ("codex",)),
    ("Grok", "ai_assistant", ("Grok",), ("Grok",), ()),
    ("DeepSeek", "ai_assistant", ("DeepSeek",), ("DeepSeek",), ("deepseek",)),
    ("Google Gemini", "ai_assistant", ("Gemini",), ("Gemini",), ()),
    ("Perplexity", "ai_assistant", ("Perplexity",), ("Perplexity",), ()),
    ("Ollama", "ai_local", ("Ollama",), ("Ollama",), ("ollama",)),
    ("LM Studio", "ai_local", ("LM Studio",), ("LM Studio",), ()),
    ("Jan", "ai_local", ("Jan",), ("Jan",), ()),
    ("Continue", "ai_coding", (), ("Continue",), ("continue",)),
    ("Tabnine", "ai_coding", (), ("Tabnine",), ()),
    ("Codeium", "ai_coding", (), ("Codeium",), ()),
    ("Aider", "ai_coding", (), (), ("aider",)),
    ("Amazon Q", "ai_coding", (), ("Amazon Q", "aws.amazonq"), ()),
    ("Windsurf", "ai_coding", ("Windsurf",), ("Windsurf",), ("windsurf",)),
    ("Zed", "editor", ("Zed",), ("Zed",), ("zed",)),
    # DevOps / IaC
    ("Terraform", "devops", (), (), ("terraform",)),
    ("Terragrunt", "devops", (), (), ("terragrunt",)),
    ("OpenTofu", "devops", (), (), ("tofu",)),
    ("tenv", "devops", (), (), ("tenv",)),
    ("tfenv", "devops", (), (), ("tfenv",)),
    ("tgenv", "devops", (), (), ("tgenv",)),
    ("kubectl", "devops", (), (), ("kubectl",)),
    ("helm", "devops", (), (), ("helm",)),
    ("docker", "devops", (), (), ("docker",)),
    ("podman", "devops", (), (), ("podman",)),
    # Runtimes
    ("Go", "runtime", (), (), ("go",)),
    ("Node.js", "runtime", (), (), ("node",)),
    ("nvm", "runtime", (), (), ("nvm",)),
    ("Rust", "runtime", (), (), ("cargo", "rustc")),
    ("Ruby", "runtime", (), (), ("ruby", "rbenv", "chruby")),
    ("Java", "runtime", (), (), ("java",)),
    # Creative / DJ / DAW
    ("Ableton Live", "creative", ("Ableton Live", "Ableton Live 12 Suite", "Ableton Live 11 Suite"), ("Ableton",), ()),
    ("Rekordbox", "creative", ("rekordbox", "Rekordbox"), ("rekordbox", "Pioneer", "PioneerDJ"), ()),
    ("Logic Pro", "creative", ("Logic Pro",), ("Logic",), ()),
    ("Ableton / Pioneer DJ", "creative", (), ("Native Instruments",), ()),
    ("Serato DJ", "creative", ("Serato DJ",), ("Serato",), ()),
    ("Traktor", "creative", ("Traktor Pro", "Traktor"), ("Native Instruments",), ()),
    ("Adobe Creative Cloud", "creative", ("Adobe",), ("Adobe",), ()),
    ("Final Cut Pro", "creative", ("Final Cut Pro",), ("Final Cut Pro",), ()),
    ("DaVinci Resolve", "creative", ("DaVinci Resolve",), ("Blackmagic Design",), ()),
)

APP_SEARCH_ROOTS = (
    Path("/Applications"),
    HOME / "Applications",
)

AI_EXTENSION_KEYWORDS = (
    "copilot",
    "github.copilot",
    "cursor",
    "continue",
    "codeium",
    "tabnine",
    "openai",
    "chatgpt",
    "claude",
    "gemini",
    "deepseek",
    "amazon.q",
    "aws-toolkit",
)


def run(cmd: list[str], timeout: int = 20) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (r.stdout or r.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def which(name: str) -> str:
    return run(["/usr/bin/which", name])


def dir_size_human(path: Path) -> str:
    if not path.exists():
        return ""
    out = run(["/usr/bin/du", "-sh", str(path)])
    return out.split()[0] if out else ""


def find_apps_matching(patterns: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for root in APP_SEARCH_ROOTS:
        if not root.is_dir():
            continue
        try:
            for entry in root.iterdir():
                if not (entry.suffix == ".app" or entry.name.endswith(".app")):
                    continue
                name = entry.name
                for pat in patterns:
                    if pat.lower() in name.lower():
                        found.append(str(entry))
                        break
        except OSError:
            continue
    return sorted(set(found))


def find_app_support(folders: tuple[str, ...]) -> list[str]:
    support = HOME / "Library/Application Support"
    if not support.is_dir():
        return []
    found: list[str] = []
    try:
        for entry in support.iterdir():
            for pat in folders:
                if pat.lower() in entry.name.lower():
                    found.append(str(entry))
                    break
    except OSError:
        pass
    return sorted(set(found))


def find_cli(binaries: tuple[str, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for b in binaries:
        b = b.split()[0]
        path = which(b)
        if path:
            ver_flag = "--version"
            if b in ("go", "terraform", "terragrunt", "kubectl", "helm", "docker"):
                ver_flag = "version" if b == "docker" else "--version"
            if b == "nvm":
                continue
            version = run([path, ver_flag]) if path else ""
            result[b] = f"{path} ({version.splitlines()[0] if version else '?'})"
    return result


def vscode_extensions(editor_cmd: str) -> list[str]:
    if not which(editor_cmd):
        return []
    lines = run([editor_cmd, "--list-extensions"]).splitlines()
    return [ln.strip() for ln in lines if ln.strip()]


def ai_extensions() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for editor, cmd in (("vscode", "code"), ("cursor", "cursor")):
        exts = vscode_extensions(cmd)
        ai = [e for e in exts if any(k in e.lower() for k in AI_EXTENSION_KEYWORDS)]
        if exts:
            out[editor] = {"all_count": len(exts), "ai_related": ai}
    return out


def tenv_snapshot() -> dict:
    if not which("tenv"):
        return {"installed": False}
    return {
        "installed": True,
        "terraform": run(["tenv", "tf", "list"]),
        "opentofu": run(["tenv", "tofu", "list"]),
        "terragrunt": run(["tenv", "tg", "list"]),
        "active_tf": run(["tenv", "tf", "version"]),
    }


def go_snapshot() -> dict:
    info: dict = {"installed": bool(which("go"))}
    if info["installed"]:
        info["version"] = run(["go", "version"])
        info["goroot"] = run(["go", "env", "GOROOT"])
        info["gopath"] = run(["go", "env", "GOPATH"])
        info["gobin"] = str(HOME / "go" / "bin")
        if (HOME / "go" / "bin").is_dir():
            info["go_install_binaries"] = sorted(
                p.name for p in (HOME / "go" / "bin").iterdir() if p.is_file()
            )[:50]
    return info


def detect_tool(
    name: str,
    category: str,
    app_patterns: tuple[str, ...],
    support_patterns: tuple[str, ...],
    cli_bins: tuple[str, ...],
) -> dict | None:
    apps = find_apps_matching(app_patterns) if app_patterns else []
    support = find_app_support(support_patterns) if support_patterns else []
    cli = find_cli(cli_bins) if cli_bins else {}

    if not apps and not support and not cli:
        return None

    paths = apps + support
    sizes = {p: dir_size_human(Path(p)) for p in support[:5]}

    return {
        "id": f"tool:{category}:{re.sub(r'[^a-zA-Z0-9]+', '_', name.lower()).strip('_')}",
        "name": name,
        "category": category,
        "applications": apps,
        "app_support_paths": support,
        "support_sizes": sizes,
        "cli": cli,
        "paths": paths,
        "detected": True,
    }


def scan_extra_ai_folders() -> list[dict]:
    """Catch AI-related config dirs not in catalog."""
    extras: list[dict] = []
    candidates = [
        (HOME / ".cursor", "Cursor config"),
        (HOME / ".continue", "Continue config"),
        (HOME / ".codex", "Codex config"),
        (HOME / ".claude", "Claude config"),
        (HOME / ".aider", "Aider config"),
        (HOME / ".ollama", "Ollama models/config"),
        (HOME / ".lmstudio", "LM Studio"),
        (HOME / ".config" / "github-copilot", "GitHub Copilot config"),
        (HOME / ".config" / "cursor", "Cursor config"),
    ]
    for path, label in candidates:
        if path.exists():
            extras.append(
                {
                    "id": f"tool:ai_config:{path.name}",
                    "name": label,
                    "category": "ai_config",
                    "paths": [str(path)],
                    "path_type": "dir" if path.is_dir() else "file",
                    "size_human": dir_size_human(path) if path.is_dir() else "",
                }
            )
    return extras


def build_inventory(out_dir: Path) -> dict:
    tools: list[dict] = []
    for entry in TOOL_CATALOG:
        item = detect_tool(*entry)
        if item:
            tools.append(item)

    tools.extend(scan_extra_ai_folders())

    by_category: dict[str, list[dict]] = {}
    for t in tools:
        by_category.setdefault(t.get("category", "other"), []).append(t)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_count": len(tools),
        "categories": sorted(by_category.keys()),
        "tools": tools,
        "by_category": by_category,
        "ai_extensions": ai_extensions(),
        "tenv": tenv_snapshot(),
        "go": go_snapshot(),
        "terraform_cli": {
            "terraform": which("terraform"),
            "terragrunt": which("terragrunt"),
            "tofu": which("tofu"),
        },
    }


def render_markdown(data: dict) -> str:
    lines = [
        f"# AI, dev & creative tools — {data.get('generated_at', '')}",
        "",
        f"Detected **{data.get('tool_count', 0)}** tools. Machine-readable: `tools-inventory.json`.",
        "",
    ]

    ext = data.get("ai_extensions") or {}
    if ext:
        lines.extend(["## IDE AI extensions", ""])
        for editor, info in ext.items():
            if isinstance(info, dict):
                lines.append(f"### {editor}")
                lines.append(f"Total extensions: {info.get('all_count', 0)}")
                ai = info.get("ai_related") or []
                if ai:
                    lines.append("AI-related:")
                    for e in ai:
                        lines.append(f"- `{e}`")
                lines.append("")

    for cat in sorted((data.get("by_category") or {}).keys()):
        items = data["by_category"][cat]
        lines.append(f"## {cat.replace('_', ' ').title()} ({len(items)})")
        lines.append("")
        for t in items:
            lines.append(f"### {t.get('name', '?')}")
            for app in t.get("applications") or []:
                lines.append(f"- App: `{app}`")
            for p in t.get("app_support_paths") or []:
                sz = (t.get("support_sizes") or {}).get(p, "")
                suffix = f" ({sz})" if sz else ""
                lines.append(f"- Data: `{p}`{suffix}")
            for bin_name, loc in (t.get("cli") or {}).items():
                lines.append(f"- CLI `{bin_name}`: {loc}")
            for p in t.get("paths") or []:
                if p not in (t.get("applications") or []) and p not in (t.get("app_support_paths") or []):
                    lines.append(f"- Path: `{p}`")
            lines.append("")

    tenv = data.get("tenv") or {}
    if tenv.get("installed"):
        lines.extend(["## tenv (Terraform / OpenTofu / Terragrunt)", ""])
        for key in ("active_tf", "terraform", "opentofu", "terragrunt"):
            if tenv.get(key):
                lines.extend([f"### {key}", "```", tenv[key], "```", ""])

    go = data.get("go") or {}
    if go.get("installed"):
        lines.extend(["## Go", "", f"- {go.get('version', '')}", f"- GOROOT: `{go.get('goroot', '')}`", f"- GOPATH: `{go.get('gopath', '')}`", ""])

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    data = build_inventory(out_dir)
    json_path = out_dir / "tools-inventory.json"
    md_path = out_dir / "10-ai-dev-creative-tools.md"

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")
    print(f"==> Tools inventory: {json_path} ({data['tool_count']} tools)")
    print(f"==> Tools report: {md_path}")


if __name__ == "__main__":
    main()
