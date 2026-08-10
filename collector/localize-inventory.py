#!/usr/bin/env python3
"""Create Hungarian (_HU.md) inventory reports from English collector output."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Order matters: longer phrases first
REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("# Migration Inventory — Summary index", "# Migration Inventory — Összegző index"),
    ("Generated:", "Generálva:"),
    ("| # | Category | File |", "| # | Kategória | Fájl |"),
    ("| 1 | Applications | 01-applications.md |", "| 1 | Alkalmazások | 01-applications_HU.md |"),
    ("| 2 | Package managers | 02-package-managers.md |", "| 2 | Csomagkezelők | 02-package-managers_HU.md |"),
    ("| 3 | Version-managed runtimes | 03-version-managers.md |", "| 3 | Verziókezelt runtime-ok | 03-version-managers_HU.md |"),
    ("| 4 | Background services | 04-background-services.md |", "| 4 | Háttérszolgáltatások | 04-background-services_HU.md |"),
    ("| 5 | Configs / dotfiles | 05-configs-dotfiles.md |", "| 5 | Konfigurációk/dotfiles | 05-configs-dotfiles_HU.md |"),
    ("| 6 | System customizations | 06-system-customizations.md |", "| 6 | Rendszer testreszabások | 06-system-customizations_HU.md |"),
    ("| 7 | Auth / CLI configs | 07-auth-cli-configs.md |", "| 7 | Hitelesítés / CLI configok | 07-auth-cli-configs_HU.md |"),
    ("| 8 | Editors / IDEs | 08-editors-ides.md |", "| 8 | Editorok / IDE-k | 08-editors-ides_HU.md |"),
    (
        "Next step: run collector/02-folder-profiler.sh, then analyzer/analyze.py for LLM categorization.",
        "Következő lépés: futtasd a collector/02-folder-profiler.sh scriptet, majd az analyzer/analyze.py-t LLM kategorizáláshoz.",
    ),
    ("# Applications —", "# Alkalmazások —"),
    ("## App Store purchases (requires mas-cli: brew install mas)", "## App Store vásárlások (mas-cli szükséges: brew install mas)"),
    ("mas not installed — run: brew install mas, then re-run this section", "mas nincs telepítve — telepítsd: brew install mas, majd futtasd újra ezt a szekciót"),
    ("## pkgutil receipts (non-App Store / non-brew installers)", "## pkgutil receiptek (nem App Store / nem brew telepítők nyoma)"),
    ("# Package managers —", "# Csomagkezelők —"),
    ("## Homebrew (formula + cask + tap — reusable via Brewfile)", "## Homebrew (formula + cask + tap — Brewfile-lal újrafelhasználható)"),
    ("Brewfile written:", "Brewfile kiírva:"),
    ("Homebrew not installed.", "Homebrew nincs telepítve."),
    ("## npm global packages", "## npm globális csomagok"),
    ("## pip (global/user — informational; pyenv versions differ)", "## pip (globális/user — tájékoztató; pyenv verziónként külön)"),
    ("## binaries installed via go install", "## go install-lal telepített binárisok"),
    ("# Version-managed runtimes —", "# Verziókezelt runtime-ok —"),
    ("# Background services (LaunchAgents/Daemons) —", "# Háttérszolgáltatások (LaunchAgents/Daemons) —"),
    ("# Configs and dotfiles —", "# Konfigurációk és dotfile-ok —"),
    ("## Hidden files in home (dotfiles)", "## Home könyvtár rejtett fájljai (dotfiles)"),
    ("## ~/.config subfolders", "## ~/.config almappák"),
    ("## ~/Library/Application Support — by size (TOP 50)", "## ~/Library/Application Support — méret szerint (TOP 50)"),
    ("## ~/Library/Preferences (.plist list — apps storing settings)", "## ~/Library/Preferences (.plist lista — beállítást tároló appok)"),
    ("# System customizations —", "# Rendszer testreszabások —"),
    ("## Shortcuts.app stored shortcuts", "## Shortcuts.app tárolt shortcutjai"),
    ("## Dock layout (raw plist for analysis)", "## Dock elrendezés (nyers plist, elemzésre)"),
    ("## Custom keyboard shortcuts / global settings export", "## Egyéni billentyűparancsok / globális beállítások export"),
    ("(defaults read com.apple.symbolichotkeys AppleSymbolicHotKeys — large; review manually)", "(defaults read com.apple.symbolichotkeys AppleSymbolicHotKeys — nagy; manuálisan érdemes átnézni)"),
    ("# Authentication / keys / CLI configs —", "# Hitelesítés / kulcsok / CLI configok —"),
    ("## known_hosts line count (count only — no content)", "## known_hosts sorok száma (csak darabszám, tartalom nélkül)"),
    ("## Git global config (key names only — values/secrets redacted)", "## Git globális config (csak kulcsnevek — értékek/secretek redaktálva)"),
    ("(unreadable)", "(nem olvasható)"),
    ("## Cloud CLI configs (existence + file count only — no secrets)", "## Felhő CLI konfigok (csak létezés + darabszám — secretek nélkül)"),
    (" -> exists, ", " -> létezik, "),
    (" files", " fájl"),
    ("# Editors / IDEs —", "# Editorok / IDE-k —"),
    ("## VSCode extension list", "## VSCode extension lista"),
    ("## VSCode user settings path/size", "## VSCode user settings elérési út/méret"),
    ("## iTerm2 profile plist", "## iTerm2 profil plist"),
    ("## JetBrains / other IDE traces", "## JetBrains / egyéb IDE nyomok"),
)

LANG_LINK_EN = "> **Language:** English | [Magyar]({base}_HU.md)\n\n"
LANG_LINK_HU = "> **Nyelv:** [English]({base}.md) | Magyar\n\n"


def to_hungarian(text: str) -> str:
    for en, hu in REPLACEMENTS:
        text = text.replace(en, hu)
    return text


def localize_file(en_path: Path) -> Path:
    base = en_path.stem
    hu_path = en_path.with_name(f"{base}_HU{en_path.suffix}")
    content = en_path.read_text(encoding="utf-8")

    # Strip existing lang link if re-run
    content = re.sub(r"^> \*\*Language.*?\n\n", "", content, flags=re.MULTILINE)

    hu_body = to_hungarian(content)
    hu_path.write_text(LANG_LINK_HU.format(base=base) + hu_body, encoding="utf-8")

    en_path.write_text(LANG_LINK_EN.format(base=base) + content, encoding="utf-8")
    return hu_path


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "migration-inventory")
    if not out_dir.is_dir():
        print(f"ERROR: directory not found: {out_dir}", file=sys.stderr)
        sys.exit(1)

    for en_file in sorted(out_dir.glob("*.md")):
        if en_file.stem.endswith("_HU"):
            continue
        localize_file(en_file)
        print(f"Localized: {en_file.name} -> {en_file.stem}_HU.md")


if __name__ == "__main__":
    main()
