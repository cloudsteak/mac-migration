"""Generate self-contained reinstall documentation from environment snapshot."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _shell_block(lines: list[str]) -> str:
    if not lines:
        return "_(none captured — check shell files manually)_\n"
    body = "\n".join(lines)
    return f"```bash\n{body}\n```\n"


def _unique_shell_init_lines(snapshot: dict) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for file_lines in (snapshot.get("shell_config_lines") or {}).values():
        for entry in file_lines:
            line = entry.split(": ", 1)[-1].strip()
            if line and line not in seen:
                seen.add(line)
                result.append(line)
    return result


def build_homebrew_section(snapshot: dict, lang: str) -> list[str]:
    brew = snapshot.get("homebrew") or {}
    if not brew.get("installed"):
        if lang == "hu":
            return ["## Homebrew", "", "A régi Mac-en nem volt Homebrew telepítve.", ""]
        return ["## Homebrew", "", "Homebrew was not installed on the old Mac.", ""]

    prefix = brew.get("prefix", "/opt/homebrew")
    brewfile = brew.get("brewfile") or "~/migration-inventory/Brewfile"
    shellenv = brew.get("shellenv_lines") or [f'eval "$({prefix}/bin/brew shellenv)"']

    if lang == "hu":
        return [
            "## Homebrew — telepítés és csomagok visszaállítása",
            "",
            f"A régi gépen a Homebrew prefix: `{prefix}`",
            f"Formula: **{brew.get('formula_count', 0)}**, cask: **{brew.get('cask_count', 0)}**",
            "",
            "### 1. Homebrew telepítése az új Mac-en (egyszer, hálózattal)",
            "",
            "Apple Silicon (M1/M2/M3):",
            "```bash",
            "/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"",
            "```",
            "",
            "### 2. Shell környezet — másold be a profilodba (`~/.zprofile` vagy `~/.zshrc`)",
            "",
            "A régi gépről exportált sorok:",
            _shell_block(shellenv),
            "",
            "Ellenőrzés új session után:",
            "```bash",
            "which brew",
            "brew --version",
            "```",
            "",
            "### 3. Csomagok visszaállítása a Brewfile-ból",
            "",
            "Másold át a `migration-inventory` mappát az új Mac-re, majd:",
            "```bash",
            "brew bundle install --file=~/migration-inventory/Brewfile",
            "```",
            "",
            "Ellenőrzés (minden csomag telepítve?):",
            "```bash",
            "brew bundle check --file=~/migration-inventory/Brewfile",
            "```",
            "",
            "### 4. Tipikus hiba: brew parancs nem található",
            "",
            f"Futtasd újra: `eval \"$({prefix}/bin/brew shellenv)\"` vagy nyiss új terminált.",
            "",
        ]

    return [
        "## Homebrew — install and restore packages",
        "",
        f"Old Mac Homebrew prefix: `{prefix}`",
        f"Formulae: **{brew.get('formula_count', 0)}**, casks: **{brew.get('cask_count', 0)}**",
        "",
        "### 1. Install Homebrew on the new Mac (once, requires network)",
        "",
        "Apple Silicon (M1/M2/M3):",
        "```bash",
        "/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"",
        "```",
        "",
        "### 2. Shell setup — add to `~/.zprofile` or `~/.zshrc`",
        "",
        "Lines exported from your old Mac:",
        _shell_block(shellenv),
        "",
        "Verify in a new terminal session:",
        "```bash",
            f"which brew",
            "brew --version",
        "```",
        "",
        "### 3. Restore packages from Brewfile",
        "",
        "Copy the `migration-inventory` folder to the new Mac, then:",
        "```bash",
        "brew bundle install --file=~/migration-inventory/Brewfile",
        "```",
        "",
        "Verify everything is installed:",
        "```bash",
        "brew bundle check --file=~/migration-inventory/Brewfile",
        "```",
        "",
        "### 4. Troubleshooting: `brew: command not found`",
        "",
        f"Run: `eval \"$({prefix}/bin/brew shellenv)\"` or open a new terminal.",
        "",
    ]


def build_pyenv_section(snapshot: dict, lang: str) -> list[str]:
    pyenv = (snapshot.get("python") or {}).get("pyenv") or {}
    if not pyenv.get("installed"):
        if lang == "hu":
            return [
                "## Python (pyenv)",
                "",
                "pyenv nem volt aktív a régi gépen (vagy nem PATH-on).",
                "Ha a rendszer Python-t használtad, az új Mac-en is `/usr/bin/python3` elérhető.",
                "",
            ]
        return [
            "## Python (pyenv)",
            "",
            "pyenv was not active on the old Mac (or not on PATH).",
            "If you used system Python, `/usr/bin/python3` is available on a fresh Mac too.",
            "",
        ]

    root = pyenv.get("root", "$HOME/.pyenv")
    global_ver = pyenv.get("global", "").strip().split()[0] if pyenv.get("global") else ""
    version_re = re.compile(r"^\d+\.\d+\.\d+$")
    versions = [v for v in pyenv.get("versions", []) if version_re.match(str(v).strip())]
    init_lines = _unique_shell_init_lines(snapshot)
    pyenv_lines = [ln for ln in init_lines if "pyenv" in ln.lower() or "PYENV" in ln]
    uses_pyenv = pyenv.get("uses_pyenv_python") or pyenv.get("uses_pyenv_shims", False)

    install_versions = sorted(set(versions), key=lambda s: [int(x) for x in s.split(".")])
    ver_cmds = "\n".join(f"pyenv install {v}" for v in install_versions)

    if lang == "hu":
        lines = [
            "## Python — pyenv (ne a beépített rendszer Python legyen az alapértelmezett)",
            "",
            f"A régi gépen az aktív Python: `{pyenv.get('which_python', '')}`",
            f"Verzió: `{pyenv.get('python_version', pyenv.get('version', ''))}`",
            f"pyenv shims használata (nem system python): **{'igen' if uses_pyenv else 'NEM — ellenőrizd a shell init sorokat!'}**",
            f"Globális pyenv verzió: `{global_ver}`",
            "",
            "### 1. pyenv telepítése",
            "",
            "Homebrew-val (ajánlott, miután a Brewfile-ból visszaállt a brew):",
            "```bash",
            "brew install pyenv pyenv-virtualenv",
            "```",
            "",
            "Vagy git clone (ha nem brew-ből jött a régi gépen):",
            "```bash",
            f"git clone https://github.com/pyenv/pyenv.git {root}",
            "```",
            "",
        ]
        if pyenv.get("plugins"):
            lines.extend(["pyenv pluginok a régi gépen: " + ", ".join(pyenv["plugins"]), ""])
        lines.extend(
            [
                "### 2. Shell init — másold be (pontosan ezek voltak a régi `.zprofile` / `.zshrc` fájlban)",
                "",
                _shell_block(pyenv_lines or init_lines),
                "",
                "Majd indíts új terminált, vagy:",
                "```bash",
                "source ~/.zprofile  # vagy ~/.zshrc",
                "```",
                "",
                "### 3. Ugyanazok a Python verziók telepítése",
                "",
                "```bash",
                ver_cmds or (f"pyenv install {global_ver}" if global_ver else "# pyenv install X.Y.Z"),
                f"pyenv global {global_ver or 'X.Y.Z'}",
                "pyenv rehash",
                "```",
                "",
                "### 4. Ellenőrzés — pyenv-nek kell nyernie, nem a system pythonnak",
                "",
                "```bash",
                "which python    # elvárt: ~/.pyenv/shims/python",
                "which python3   # elvárt: ~/.pyenv/shims/python3",
                "python --version",
                "pyenv version",
                "```",
                "",
                "Ha még mindig `/usr/bin/python3`: a pyenv init sorok hiányoznak vagy a PATH sorrend rossz.",
                "A `eval \"$(pyenv init - zsh)\"` sor legyen a PATH beállítások **után**.",
                "",
            ]
        )
        return lines

    lines = [
        "## Python — pyenv (use pyenv Python, not built-in system Python)",
        "",
        f"Active Python on old Mac: `{pyenv.get('which_python', '')}`",
        f"Version: `{pyenv.get('python_version', pyenv.get('version', ''))}`",
        f"Using pyenv (not system python): **{'yes' if uses_pyenv else 'NO — fix shell init lines!'}**",
        f"pyenv global version: `{global_ver}`",
        "",
        "### 1. Install pyenv",
        "",
        "Via Homebrew (recommended, after Brewfile restore):",
        "```bash",
        "brew install pyenv pyenv-virtualenv",
        "```",
        "",
        "Or git clone (if old Mac did not use brew for pyenv):",
        "```bash",
        f"git clone https://github.com/pyenv/pyenv.git {root}",
        "```",
        "",
    ]
    if pyenv.get("plugins"):
        lines.extend(["pyenv plugins on old Mac: " + ", ".join(pyenv["plugins"]), ""])
    lines.extend(
        [
            "### 2. Shell init — copy these lines into `~/.zprofile` or `~/.zshrc`",
            "",
            "Exact lines from your old Mac:",
            _shell_block(pyenv_lines or init_lines),
            "",
            "Reload shell:",
            "```bash",
            "source ~/.zprofile  # or ~/.zshrc",
            "```",
            "",
            "### 3. Install the same Python versions",
            "",
            "```bash",
            ver_cmds or f"pyenv install {global_ver}",
            f"pyenv global {global_ver or 'X.Y.Z'}",
            "pyenv rehash",
            "```",
            "",
            "### 4. Verify — pyenv must win over system Python",
            "",
            "```bash",
            "which python    # expected: ~/.pyenv/shims/python",
            "which python3   # expected: ~/.pyenv/shims/python3",
            "python --version",
            "pyenv version",
            "```",
            "",
            "If you still get `/usr/bin/python3`: pyenv init is missing or PATH order is wrong.",
            "Place `eval \"$(pyenv init - zsh)\"` **after** PATH exports in your shell file.",
            "",
        ]
    )
    return lines


def build_nvm_section(snapshot: dict, lang: str) -> list[str]:
    nvm = (snapshot.get("node") or {}).get("nvm") or {}
    if not nvm.get("installed") and not nvm.get("versions"):
        return []

    versions = nvm.get("versions") or []
    init_lines = [ln for ln in _unique_shell_init_lines(snapshot) if "nvm" in ln.lower()]

    if lang == "hu":
        return [
            "## Node.js (nvm)",
            "",
            f"Telepített verziók: {', '.join(versions) if versions else '(nézd a 03-version-managers.md-t)'}",
            "",
            "### Shell init a régi gépről",
            _shell_block(init_lines),
            "",
            "### Telepítés az új Mac-en",
            "```bash",
            "# Ha brew-ből jött: brew install nvm",
            *[f"nvm install {v}" for v in versions[:5]],
            "```",
            "",
        ]

    return [
        "## Node.js (nvm)",
        "",
        f"Installed versions: {', '.join(versions) if versions else '(see 03-version-managers.md)'}",
        "",
        "### Shell init from old Mac",
        _shell_block(init_lines),
        "",
        "### Restore on new Mac",
        "```bash",
        "# If from brew: brew install nvm",
        *[f"nvm install {v}" for v in versions[:5]],
        "```",
        "",
    ]


def build_pipx_section(snapshot: dict, lang: str) -> list[str]:
    pipx = snapshot.get("pipx") or {}
    if not pipx.get("installed") or not pipx.get("list"):
        return []

    if lang == "hu":
        return [
            "## pipx (globális Python CLI eszközök)",
            "",
            "Régi gépen telepített pipx csomagok:",
            "```",
            pipx.get("list", "").strip(),
            "```",
            "",
            "Új Mac-en (pyenv + pip után): telepítsd újra ugyanazokat `pipx install <csomag>` paranccsal.",
            "",
        ]

    return [
        "## pipx (global Python CLI tools)",
        "",
        "Packages on old Mac:",
        "```",
        pipx.get("list", "").strip(),
        "```",
        "",
        "On new Mac (after pyenv + pip): reinstall with `pipx install <package>`.",
        "",
    ]


def build_order_section(lang: str) -> list[str]:
    if lang == "hu":
        return [
            "# Újratelepítési útmutató — önálló dokumentáció",
            "",
            "Ez a dokumentum a **régi Mac-ed tényleges állapotából** készült. "
            "Nem kell hozzá böngésző vagy külső dokumentáció — csak ezt a fájlt és a `migration-inventory` mappát.",
            "",
            "## Ajánlott sorrend az új Mac-en",
            "",
            "1. **macOS alap** — Apple ID, iCloud (ha kell), Xcode Command Line Tools: `xcode-select --install`",
            "2. **Homebrew** — lásd alább, shellenv beállítás",
            "3. **Brewfile** — `brew bundle install`",
            "4. **pyenv / nvm / rbenv** — shell init sorok, majd verziók telepítése",
            "5. **Aliasok + shell + Homebrew + VS Code** — egy lépés: `bash ~/migration-inventory/restore.sh`",
            "6. **pipx / npm global** — csomagok újratelepítése",
            "7. **AI eszközök** — Cursor, Claude, Copilot bővítmények (lásd alább)",
            "8. **DevOps** — Terraform/tenv, Go, Docker, **AWS CLI**, gcloud",
            "9. **Kreatív appok** — Ableton, Rekordbox adatmappák",
            "10. **Dotfile-ok** — csak amit az interaktív elemzés `migrate` döntéssel jelölt",
            "11. **Appok** — App Store / brew cask / kézi telepítés",
            "12. **Auth** — SSH, gcloud, AWS CLI újra bejelentkezés",
            "",
        ]

    return [
        "# Reinstall guide — self-contained documentation",
        "",
        "Generated from **your old Mac's actual state**. "
        "You should not need a browser or external docs — only this file and the `migration-inventory` folder.",
        "",
        "## Recommended order on the new Mac",
        "",
        "1. **macOS base** — Apple ID, iCloud if needed, Xcode CLT: `xcode-select --install`",
        "2. **Homebrew** — see below, configure shellenv",
        "3. **Brewfile** — `brew bundle install`",
        "4. **pyenv / nvm / rbenv** — shell init lines, then install versions",
        "5. **Aliases + shell + Homebrew + VS Code** — one step: `bash ~/migration-inventory/restore.sh`",
        "6. **pipx / npm global** — reinstall packages",
        "7. **AI tools** — Cursor, Claude, Copilot extensions (see below)",
        "8. **DevOps** — Terraform/tenv, Go, Docker, **AWS CLI**, gcloud",
        "9. **Creative apps** — Ableton, Rekordbox data folders",
        "10. **Dotfiles** — only paths marked `migrate` in interactive review",
        "11. **Apps** — App Store / brew cask / manual install",
        "12. **Auth** — re-login SSH, gcloud, AWS CLI (copy keys securely)",
        "",
    ]


def build_tools_sections(tools_data: dict | None, lang: str) -> list[str]:
    if not tools_data or not tools_data.get("tools"):
        if lang == "hu":
            return [
                "## AI, dev & kreatív eszközök",
                "",
                "Futtasd újra: `./mac-migration collect` (tools-inventory.json hiányzik).",
                "",
            ]
        return [
            "## AI, dev & creative tools",
            "",
            "Re-run `./mac-migration collect` (tools-inventory.json missing).",
            "",
        ]

    tools = tools_data.get("tools", [])
    by_cat: dict[str, list[dict]] = {}
    for t in tools:
        by_cat.setdefault(t.get("category", "other"), []).append(t)

    if lang == "hu":
        lines = [
            "## AI asszisztensek és kódoló AI eszközök",
            "",
            "Az alábbi eszközök **telepítve voltak** a régi Mac-en. "
            "Az új Mac-en telepítsd újra az appot, majd másold vissza a jelölt adatmappákat (ha `migrate` döntés).",
            "",
        ]
    else:
        lines = [
            "## AI assistants & coding AI tools",
            "",
            "These tools **were installed** on your old Mac. "
            "On the new Mac: reinstall each app, then restore marked data folders (if you chose `migrate`).",
            "",
        ]

    cat_titles_hu = {
        "ai_assistant": "AI asszisztensek",
        "ai_coding": "AI kódolás / IDE",
        "ai_local": "Helyi LLM (Ollama, LM Studio)",
        "ai_config": "AI config mappák",
        "devops": "DevOps / IaC",
        "runtime": "Runtime-ok",
        "creative": "Kreatív / DJ / DAW",
        "editor": "Editorok",
    }
    cat_titles_en = {
        "ai_assistant": "AI assistants",
        "ai_coding": "AI coding / IDE",
        "ai_local": "Local LLM",
        "ai_config": "AI config directories",
        "devops": "DevOps / IaC",
        "runtime": "Runtimes",
        "creative": "Creative / DJ / DAW",
        "editor": "Editors",
    }
    titles = cat_titles_hu if lang == "hu" else cat_titles_en

    for cat in (
        "ai_assistant",
        "ai_coding",
        "ai_local",
        "ai_config",
        "devops",
        "runtime",
        "creative",
        "editor",
    ):
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(f"### {titles.get(cat, cat)}")
        lines.append("")
        for t in items:
            lines.append(f"**{t.get('name', '?')}**")
            for app in t.get("applications") or []:
                lines.append(f"- App: `{app}` → reinstall from vendor / App Store / brew cask")
            for p in t.get("app_support_paths") or []:
                sz = (t.get("support_sizes") or {}).get(p, "")
                lines.append(f"- User data: `{p}`" + (f" ({sz})" if sz else ""))
            for cli_name, loc in (t.get("cli") or {}).items():
                lines.append(f"- CLI: `{cli_name}` — {loc}")
            for p in t.get("paths") or []:
                if p not in (t.get("applications") or []) and p not in (
                    t.get("app_support_paths") or []
                ):
                    lines.append(f"- Path: `{p}`")
            lines.append("")

    ext = tools_data.get("ai_extensions") or {}
    if ext:
        lines.append("### IDE AI extensions" if lang == "en" else "### IDE AI bővítmények")
        lines.append("")
        for editor, info in ext.items():
            if not isinstance(info, dict):
                continue
            ai = info.get("ai_related") or []
            if ai:
                lines.append(f"**{editor}** — reinstall extensions on new Mac:")
                for e in ai:
                    install_cmd = f"{editor} --install-extension {e}" if editor == "vscode" else f"cursor --install-extension {e}"
                    lines.append(f"- `{e}` → `{install_cmd}`")
                lines.append("")

    tenv = tools_data.get("tenv") or {}
    if tenv.get("installed"):
        if lang == "hu":
            lines.extend(
                [
                    "### Terraform / Terragrunt / OpenTofu (tenv)",
                    "",
                    "Régi gépen tenv volt telepítve. Új Mac-en:",
                    "```bash",
                    "brew install tenv",
                    "# majd ugyanazok a verziók — lásd tools-inventory.json tenv szekció",
                    "```",
                    "",
                ]
            )
            for key in ("active_tf", "terraform", "terragrunt"):
                if tenv.get(key):
                    lines.extend([f"**{key}:**", "```", tenv[key], "```", ""])
        else:
            lines.extend(
                [
                    "### Terraform / Terragrunt / OpenTofu (tenv)",
                    "",
                    "tenv was installed on the old Mac. On the new Mac:",
                    "```bash",
                    "brew install tenv",
                    "# install same versions — see tools-inventory.json tenv section",
                    "```",
                    "",
                ]
            )
            for key in ("active_tf", "terraform", "terragrunt"):
                if tenv.get(key):
                    lines.extend([f"**{key}:**", "```", tenv[key], "```", ""])

    go = tools_data.get("go") or {}
    if go.get("installed"):
        if lang == "hu":
            lines.extend(
                [
                    "### Go",
                    "",
                    f"- {go.get('version', '')}",
                    f"- GOROOT: `{go.get('goroot', '')}`",
                    f"- GOPATH: `{go.get('gopath', '')}`",
                    "- Új Mac-en: `brew install go`, majd `go install` a binárisok listájából.",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "### Go",
                    "",
                    f"- {go.get('version', '')}",
                    f"- GOROOT: `{go.get('goroot', '')}`",
                    f"- GOPATH: `{go.get('gopath', '')}`",
                    "- New Mac: `brew install go`, then `go install` for binaries you need.",
                    "",
                ]
            )
        bins = go.get("go_install_binaries") or []
        if bins:
            lines.append("Installed via `go install` on old Mac:")
            for b in bins[:20]:
                lines.append(f"- `{b}`")
            lines.append("")

    return lines


def build_vscode_sections(vscode_data: dict | None, lang: str) -> list[str]:
    if not vscode_data or not vscode_data.get("editors"):
        return []
    if lang == "hu":
        lines = [
            "## VS Code / Cursor bővítmények",
            "",
            "Az alábbi parancsokat futtasd az új Mac-en (előbb telepítsd az editort).",
            "",
        ]
    else:
        lines = [
            "## VS Code / Cursor extensions",
            "",
            "Run these commands on the new Mac (install the editor first).",
            "",
        ]
    for ed in vscode_data.get("editors", []):
        lines.append(f"### {ed.get('name', '?')}")
        lines.append("")
        if ed.get("paths", {}).get("user_settings"):
            lines.append(f"Settings backup path: `{ed['paths']['user_settings']}`")
        lines.append("```bash")
        for cmd in ed.get("reinstall_script_lines", [])[2:]:
            lines.append(cmd)
        lines.append("```")
        lines.append("")
    return lines


def build_homebrew_inventory_section(homebrew_data: dict | None, lang: str) -> list[str]:
    if not homebrew_data or not homebrew_data.get("installed"):
        return []
    if lang == "hu":
        return [
            "## Homebrew — teljes csomaglista",
            "",
            f"Összes formula: **{homebrew_data.get('formula_count', 0)}**, "
            f"cask: **{homebrew_data.get('cask_count', 0)}**. "
            "Részletes lista: `12-homebrew-full.md` és `homebrew-inventory.json`.",
            "",
            "Minden Homebrew csomag felhasználói telepítés — nem része az alap macOS-nek.",
            "",
        ]
    return [
        "## Homebrew — complete package list",
        "",
        f"Total formulae: **{homebrew_data.get('formula_count', 0)}**, "
        f"casks: **{homebrew_data.get('cask_count', 0)}**. "
        "Full list: `12-homebrew-full.md` and `homebrew-inventory.json`.",
        "",
        "Every Homebrew package is user-installed — not part of stock macOS.",
        "",
    ]


def build_aliases_section(snapshot: dict, lang: str, manifest: dict | None = None) -> list[str]:
    alias_data = snapshot.get("aliases") or {}
    items = alias_data.get("items") or []
    if not items:
        return []

    restore_cmd = "bash ~/migration-inventory/restore.sh"
    if lang == "hu":
        lines = [
            "## Shell aliasok — automatikus visszaállítás",
            "",
            f"A régi Mac shell fájljaiból **{len(items)}** alias lett felderítve (`.zshrc` + `source`-olt fájlok).",
            "Nem kell kézzel másolgatni — a tool dinamikusan alkalmazza.",
            "",
            "### Egy lépés az új Mac-en",
            "",
            "```bash",
            restore_cmd,
            "```",
            "",
            "Vagy csak az aliasok:",
            "",
            "```bash",
            "./mac-migration restore aliases",
            "```",
            "",
            "### Alias lista",
            "",
        ]
    else:
        lines = [
            "## Shell aliases — automatic restore",
            "",
            f"**{len(items)}** alias(es) discovered from shell files (`.zshrc` + sourced files).",
            "No manual copy/paste — the tool applies them dynamically.",
            "",
            "### One step on the new Mac",
            "",
            "```bash",
            "bash ~/migration-inventory/restore.sh",
            "```",
            "",
            "Or aliases only:",
            "",
            "```bash",
            "./mac-migration restore aliases",
            "```",
            "",
            "### Alias list",
            "",
        ]

    for item in items:
        lines.append(f"- `{item['name']}` → `{item['definition']}` _({item['source_file']}:{item['line']})_")
    lines.append("")
    lines.append("Raw fragment: `aliases.zsh` (managed by `mac-migration restore`)")
    lines.append("")
    return lines


def build_restore_automation_section(manifest: dict | None, lang: str) -> list[str]:
    if not manifest or not manifest.get("components"):
        return []

    restore_cmd = manifest.get("restore_command", "bash ~/migration-inventory/restore.sh")
    if lang == "hu":
        lines = [
            "## Automatikus visszaállítás (új Mac)",
            "",
            "A collector mindent JSON-ba mentett. Egy parancs visszaállítja, amit lehet:",
            "",
            "```bash",
            "bash ~/migration-inventory/restore.sh",
            "```",
            "",
            "Komponensek:",
            "",
        ]
    else:
        lines = [
            "## Automatic restore (new Mac)",
            "",
            "The collector saved everything to JSON. One command restores what can be automated:",
            "",
            "```bash",
            "bash ~/migration-inventory/restore.sh",
            "```",
            "",
            "Components:",
            "",
        ]

    for comp in manifest.get("components") or []:
        lines.append(
            f"- **{comp.get('label', comp.get('id', '?'))}** — {comp.get('count', 0)} item(s) "
            f"(`{comp.get('source', '')}`)"
        )
    lines.append("")
    lines.append(f"Full command: `{restore_cmd}`")
    lines.append("")
    lines.append("Preview without changes: `./mac-migration restore all --dry-run`")
    lines.append("")
    return lines


def build_quick_actions_section(quick_actions_data: dict | None, lang: str) -> list[str]:
    if not quick_actions_data:
        return []
    workflows = quick_actions_data.get("automator_workflows") or []
    shortcuts = quick_actions_data.get("shortcuts_app") or []
    if not workflows and not shortcuts:
        return []

    if lang == "hu":
        lines = [
            "## Quick Actions — automatikus visszaállítás",
            "",
            f"**{len(workflows)}** Automator workflow, **{len(shortcuts)}** Shortcuts.app shortcut felderítve.",
            "",
            "### Automator (Finder jobb klikk) — automatikus",
            "",
            "A `.workflow` fájlok másolva lettek a `quick-actions/workflows/` mappába.",
            "Az új Mac-en:",
            "",
            "```bash",
            "./mac-migration restore quick-actions",
            "```",
            "",
            "Ez bemásolja a `~/Library/Services/` mappába — megjelennek a Finder Quick Actions menüben.",
            "",
        ]
    else:
        lines = [
            "## Quick Actions — automatic restore",
            "",
            f"**{len(workflows)}** Automator workflow(s), **{len(shortcuts)}** Shortcuts.app shortcut(s) discovered.",
            "",
            "### Automator (Finder right-click) — automatic",
            "",
            "`.workflow` bundles were copied to `quick-actions/workflows/`.",
            "On the new Mac:",
            "",
            "```bash",
            "./mac-migration restore quick-actions",
            "```",
            "",
            "This copies them to `~/Library/Services/` — they appear in Finder Quick Actions.",
            "",
        ]

    for wf in workflows:
        lines.append(f"- **{wf.get('name', '?')}** (`{wf.get('bundle_name', '')}`)")
        if wf.get("file_types"):
            lines.append(f"  - Input: {', '.join(wf['file_types'])}")
        if wf.get("shell_script_preview"):
            lines.append(f"  - Script: `{wf['shell_script_preview'][:80]}...`" if len(wf.get("shell_script_preview", "")) > 80 else f"  - Script: `{wf.get('shell_script_preview')}`")

    if shortcuts:
        lines.append("")
        if lang == "hu":
            lines.extend([
                "### Shortcuts.app — iCloud vagy kézi beállítás",
                "",
                "A Shortcuts CLI nem exportál fájlokat. Lehetőségek az új Mac-en:",
                "1. **Ugyanaz az Apple ID** — iCloud szinkronizálhatja a shortcutokat",
                "2. **Kézi** — Shortcuts app → shortcut → Info → „Használat Quick Action-ként” / Finder",
                "",
                "Felderített shortcutok:",
            ])
        else:
            lines.extend([
                "### Shortcuts.app — iCloud or manual setup",
                "",
                "The Shortcuts CLI cannot export files. On the new Mac:",
                "1. **Same Apple ID** — iCloud may sync shortcuts automatically",
                "2. **Manual** — Shortcuts app → shortcut → Info → 'Use as Quick Action' / Finder",
                "",
                "Discovered shortcuts:",
            ])
        for sc in shortcuts:
            lines.append(f"- {sc.get('name', '?')}")
    lines.append("")
    return lines


def build_audio_section(audio_data: dict | None, lang: str) -> list[str]:
    if not audio_data or not audio_data.get("devices"):
        return []

    devices = audio_data.get("devices") or []
    hal = audio_data.get("hal_plugins") or []
    hints = audio_data.get("restore_hints") or []

    if lang == "hu":
        lines = [
            "## Audio eszközök (BlackHole, virtuális driverek)",
            "",
            f"**{len(devices)}** eszköz, **{len(hal)}** HAL plugin felderítve.",
            "",
            "### Visszaállítás az új Mac-en",
            "",
            "```bash",
            "./mac-migration restore audio",
            "```",
            "",
        ]
    else:
        lines = [
            "## Audio devices (BlackHole, virtual drivers)",
            "",
            f"**{len(devices)}** device(s), **{len(hal)}** HAL plugin(s) discovered.",
            "",
            "### Restore on new Mac",
            "",
            "```bash",
            "./mac-migration restore audio",
            "```",
            "",
        ]

    for d in devices:
        if d.get("transport", "").lower() == "virtual" or "blackhole" in d.get("name", "").lower():
            lines.append(
                f"- **{d.get('name', '?')}** — {d.get('transport', '')} "
                f"({d.get('input_channels', '?')} in / {d.get('output_channels', '?')} out)"
            )
    lines.append("")
    for hint in hints:
        lines.append(f"**{hint.get('product', '?')}:**")
        lines.append("```bash")
        lines.append(hint.get("install_command", ""))
        lines.append("```")
        if hint.get("note"):
            lines.append(f"_{hint['note']}_")
        lines.append("")
    return lines


def build_cloud_cli_section(homebrew_data: dict | None, lang: str) -> list[str]:
    formulae = {
        pkg.get("name", "")
        for pkg in (homebrew_data or {}).get("formulae") or []
        if pkg.get("name")
    }
    casks = {
        pkg.get("name", "")
        for pkg in (homebrew_data or {}).get("casks") or []
        if pkg.get("name")
    }
    has_aws = "awscli" in formulae or "aws-vault-binary" in casks
    has_gcloud = "gcloud-cli" in casks or "google-cloud-sdk" in formulae
    if not has_aws and not has_gcloud:
        return []

    if lang == "hu":
        lines = [
            "## AWS CLI és Google Cloud CLI",
            "",
            "A régi gépen ezek telepítve voltak. **Ne másold** a Cellar/bin mappákat — csak a configot.",
            "",
        ]
        if has_aws:
            lines.extend(
                [
                    "### AWS CLI",
                    "",
                    "```bash",
                    "brew install awscli",
                    "aws --version",
                    "aws configure list",
                    "```",
                    "",
                    "Config migrálása (ha `migrate` döntés):",
                    "",
                    "```bash",
                    "rsync -a ~/.aws/ NEW_MAC:~/.aws/",
                    "```",
                    "",
                    "Fájlok: `~/.aws/config`, `~/.aws/credentials` (profilok, SSO, access key).",
                    "",
                ]
            )
        if has_gcloud:
            lines.extend(
                [
                    "### Google Cloud CLI",
                    "",
                    "```bash",
                    "brew install --cask gcloud-cli",
                    "gcloud --version",
                    "gcloud auth list",
                    "```",
                    "",
                    "Config: `~/.config/gcloud/` — másold csak ha szükséges; SSO-t újra be kell jelentkezni.",
                    "",
                ]
            )
        return lines

    lines = [
        "## AWS CLI & Google Cloud CLI",
        "",
        "These were installed on the old Mac. **Do not copy** Cellar binaries — migrate config only.",
        "",
    ]
    if has_aws:
        lines.extend(
            [
                "### AWS CLI",
                "",
                "```bash",
                "brew install awscli",
                "aws --version",
                "aws configure list",
                "```",
                "",
                "Migrate config (if you chose `migrate`):",
                "",
                "```bash",
                "rsync -a ~/.aws/ NEW_MAC:~/.aws/",
                "```",
                "",
                "Files: `~/.aws/config`, `~/.aws/credentials` (profiles, SSO, access keys).",
                "",
            ]
        )
    if has_gcloud:
        lines.extend(
            [
                "### Google Cloud CLI",
                "",
                "```bash",
                "brew install --cask gcloud-cli",
                "gcloud --version",
                "gcloud auth list",
                "```",
                "",
                "Config: `~/.config/gcloud/` — copy only if needed; re-login for SSO.",
                "",
            ]
        )
    return lines


def build_reinstall_guide(
    snapshot: dict,
    lang: str,
    *,
    interactive: dict | None = None,
    tools_data: dict | None = None,
    vscode_data: dict | None = None,
    homebrew_data: dict | None = None,
    manifest: dict | None = None,
    quick_actions_data: dict | None = None,
    audio_data: dict | None = None,
) -> str:
    parts: list[str] = []
    parts.extend(build_order_section(lang))
    parts.extend(build_restore_automation_section(manifest, lang))
    parts.extend(build_homebrew_section(snapshot, lang))
    parts.extend(build_pyenv_section(snapshot, lang))
    parts.extend(build_nvm_section(snapshot, lang))
    parts.extend(build_pipx_section(snapshot, lang))
    parts.extend(build_aliases_section(snapshot, lang, manifest))
    parts.extend(build_tools_sections(tools_data, lang))
    parts.extend(build_cloud_cli_section(homebrew_data, lang))
    parts.extend(build_vscode_sections(vscode_data, lang))
    parts.extend(build_quick_actions_section(quick_actions_data, lang))
    parts.extend(build_audio_section(audio_data, lang))
    parts.extend(build_homebrew_inventory_section(homebrew_data, lang))

    if lang == "hu":
        parts.extend(
            [
                "## További fájlok ebben a mappában",
                "",
                "| Fájl | Miért |",
                "|------|-------|",
                "| `Brewfile` | Homebrew csomaglista |",
                "| `03-version-managers.md` | pyenv/nvm/rbenv verziók |",
                "| `02-package-managers.md` | npm, pipx, gem |",
                "| `10-ai-dev-creative-tools.md` | AI, Terraform, Ableton, stb. |",
                "| `tools-inventory.json` | Géppel olvasható tool lista |",
                "| `14-quick-actions.md` | Quick Actions felderítés + visszaállítás |",
                "| `quick-actions-inventory.json` | Automator + Shortcuts lista |",
                "| `restore-manifest.json` | Dinamikus visszaállítási terv |",
                "| `restore.sh` | Egy lépés az új Mac-en |",
                "| `aliases.zsh` | Exportált alias definíciók |",
                "| `migration-plan_HU.md` | Teljes migrációs checklist |",
                "| `interactive-decisions.json` | Interaktív döntéseid |",
                "",
            ]
        )
    else:
        parts.extend(
            [
                "## Other files in this folder",
                "",
                "| File | Purpose |",
                "|------|---------|",
                "| `Brewfile` | Homebrew package list |",
                "| `03-version-managers.md` | pyenv/nvm/rbenv versions |",
                "| `02-package-managers.md` | npm, pipx, gem |",
                "| `10-ai-dev-creative-tools.md` | AI, Terraform, Ableton, etc. |",
                "| `tools-inventory.json` | Machine-readable tool list |",
                "| `14-quick-actions.md` | Quick Actions discovery + restore |",
                "| `quick-actions-inventory.json` | Automator + Shortcuts list |",
                "| `restore-manifest.json` | Dynamic restore plan |",
                "| `restore.sh` | One step on the new Mac |",
                "| `aliases.zsh` | Exported alias definitions |",
                "| `migration-plan.md` | Full migration checklist |",
                "| `interactive-decisions.json` | Your interactive choices |",
                "",
            ]
        )

    return "\n".join(parts).rstrip() + "\n"
