"""Component-centric migration report from interactive decisions."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

DECISION_ORDER = ("migrate", "reinstall", "later", "skip")

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "title": "# Migration review — components, folders & install steps",
        "intro": (
            "Per-component decisions from interactive review. "
            "Each section lists related paths and concrete steps for the new Mac."
        ),
        "summary": "## Summary",
        "section_migrate": "## Migrate — copy data / config",
        "section_reinstall": "## Reinstall — fresh install on new Mac",
        "section_later": "## Decide later",
        "section_skip": "## Skip — leave on old Mac",
        "decision": "Decision",
        "confidence": "Confidence",
        "type": "Type",
        "related_paths": "### Related folders & paths",
        "config": "### Settings & config files",
        "steps": "### Installation / migration steps",
        "members": "### Grouped items",
        "path_header": "| Path | Size |",
        "path_sep": "|---|---|",
        "no_paths": "_(no paths captured)_",
        "no_steps": "_(no steps — review manually)_",
        "lang_link": "> **Language:** English | [Magyar]({other})",
    },
    "hu": {
        "title": "# Migrációs áttekintés — komponensek, mappák és telepítési lépések",
        "intro": (
            "Interaktív felülvizsgálat komponensenkénti döntései. "
            "Minden szekció tartalmazza a kapcsolódó útvonalakat és az új Mac-en végrehajtandó lépéseket."
        ),
        "summary": "## Összefoglaló",
        "section_migrate": "## Migrálás — adat/config másolása",
        "section_reinstall": "## Újratelepítés — friss telepítés az új Mac-en",
        "section_later": "## Később eldöntendő",
        "section_skip": "## Kihagyás — marad a régi gépen",
        "decision": "Döntés",
        "confidence": "Bizalom",
        "type": "Típus",
        "related_paths": "### Kapcsolódó mappák és útvonalak",
        "config": "### Beállítások és config fájlok",
        "steps": "### Telepítés / migráció lépései",
        "members": "### Csoportosított tételek",
        "path_header": "| Útvonal | Méret |",
        "path_sep": "|---|---|",
        "no_paths": "_(nincs rögzített útvonal)_",
        "no_steps": "_(nincs lépés — kézi ellenőrzés)_",
        "lang_link": "> **Nyelv:** [English]({other}) | Magyar",
    },
}

DECISION_SECTION = {
    "migrate": "section_migrate",
    "reinstall": "section_reinstall",
    "later": "section_later",
    "skip": "section_skip",
}

BREW_DISPLAY_NAMES = {
    "awscli": "AWS CLI",
    "gcloud-cli": "Google Cloud CLI",
    "azure-cli": "Azure CLI",
    "kubectl": "kubectl",
    "helm": "Helm",
    "terraform": "Terraform",
    "gh": "GitHub CLI",
}


def _display_component_name(comp: dict) -> str:
    name = comp.get("component_name") or comp.get("component_id") or "?"
    if comp.get("type") in ("homebrew_formula", "homebrew_cask"):
        return BREW_DISPLAY_NAMES.get(name, name)
    return name


STEP_TEXT = {
    "en": {
        "skip": "No action required on the new Mac.",
        "later": "Review this component manually before migrating.",
        "copy_path": "Copy to the same path on the new Mac: `{path}`",
        "rsync": "Example: `rsync -aH '{path}/' NEW_MAC:'{path}/'`",
        "brew_cask": "Install via Homebrew: `brew install --cask {name}`",
        "brew_formula": "Install via Homebrew: `brew install {name}`",
        "brew_bundle": "Restore all Homebrew packages: `brew bundle install --file=~/migration-inventory/Brewfile`",
        "vscode_ext_reinstall": "Reinstall extension: `{cli} --install-extension {ext_id}`",
        "vscode_ext_copy": "Or copy extension folder: `{path}`",
        "vscode_restore": "Restore all VS Code/Cursor extensions: `bash ~/migration-inventory/restore.sh` (vscode step)",
        "vscode_settings": "Copy editor settings/snippets from Application Support (paths above).",
        "app_reinstall": "Download and install `{name}` on the new Mac (App Store, vendor site, or Homebrew cask).",
        "app_migrate": "Copy application data / preferences (paths above) after installing the app.",
        "restore_all": "Automated restore: `bash ~/migration-inventory/restore.sh`",
        "quick_actions": "Restore Quick Actions: `./mac-migration restore quick-actions`",
        "aliases": "Restore shell aliases: `./mac-migration restore aliases`",
        "audio": "Reinstall audio driver (e.g. BlackHole): `./mac-migration restore audio`",
        "group_reinstall": "Reinstall grouped items using Brewfile, restore.sh, or per-item commands below.",
        "group_skip": "Skip all grouped items unless you change this decision.",
    },
    "hu": {
        "skip": "Az új Mac-en nincs teendő.",
        "later": "Migráció előtt manuálisan dönts erről a komponensről.",
        "copy_path": "Másold ugyanerre az útvonalra az új Mac-en: `{path}`",
        "rsync": "Példa: `rsync -aH '{path}/' UJ_MAC:'{path}/'`",
        "brew_cask": "Homebrew telepítés: `brew install --cask {name}`",
        "brew_formula": "Homebrew telepítés: `brew install {name}`",
        "brew_bundle": "Összes Homebrew csomag: `brew bundle install --file=~/migration-inventory/Brewfile`",
        "vscode_ext_reinstall": "Extension újratelepítés: `{cli} --install-extension {ext_id}`",
        "vscode_ext_copy": "Vagy másold az extension mappát: `{path}`",
        "vscode_restore": "VS Code/Cursor extensionök: `bash ~/migration-inventory/restore.sh` (vscode lépés)",
        "vscode_settings": "Másold az editor beállításokat/snippets-et az Application Support útvonalakról (fent).",
        "app_reinstall": "Telepítsd az új Mac-en: `{name}` (App Store, gyártó oldal, vagy Homebrew cask).",
        "app_migrate": "Telepítés után másold az app adatait/beállításait (fenti útvonalak).",
        "restore_all": "Automatikus restore: `bash ~/migration-inventory/restore.sh`",
        "quick_actions": "Quick Actions visszaállítás: `./mac-migration restore quick-actions`",
        "aliases": "Shell aliasok: `./mac-migration restore aliases`",
        "audio": "Audio driver (pl. BlackHole): `./mac-migration restore audio`",
        "group_reinstall": "Csoportos tételek: Brewfile, restore.sh, vagy alábbi parancsok.",
        "group_skip": "A csoport minden eleme kihagyva, hacsak nem módosítod a döntést.",
    },
}


def _label(lang: str, key: str) -> str:
    return LABELS.get(lang, LABELS["en"]).get(key, key)


def _step(lang: str, key: str, **kwargs: str) -> str:
    text = STEP_TEXT.get(lang, STEP_TEXT["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def _load_inventory_json(inventory_dir: Path, name: str) -> dict:
    path = inventory_dir / name
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _editor_cli_for_source(source: str, inventory_dir: Path) -> str:
    vscode = _load_inventory_json(inventory_dir, "vscode-extensions.json")
    source_l = source.lower()
    for ed in vscode.get("editors") or []:
        ed_name = (ed.get("name") or "").lower()
        if source_l in ed_name or ed_name in source_l:
            return ed.get("cli") or "code"
    if "cursor" in source_l:
        return "cursor"
    return "code"


def _extension_id_from_entry(entry: dict) -> str:
    profile = entry.get("profile") or {}
    if profile.get("id"):
        return str(profile["id"])
    comp_id = entry.get("component_id") or ""
    if comp_id.startswith("vscode_ext:"):
        return comp_id.removeprefix("vscode_ext:")
    path = (entry.get("paths") or [""])[0]
    if "/extensions/" in path:
        part = path.split("/extensions/")[-1].split("/")[0]
        match = part.rsplit("-", 1)
        if len(match) == 2 and match[0].count(".") >= 1:
            return match[0]
    return ""


def collect_related_paths(entry: dict, lang: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()

    def add(path: str, size_human: str = "?") -> None:
        if not path or path in seen:
            return
        seen.add(path)
        rows.append({"path": path, "size_human": size_human or "?"})

    for folder in entry.get("related_folders") or []:
        add(folder.get("path", ""), folder.get("size_human", "?"))

    for path in entry.get("related_paths") or []:
        add(path, entry.get("total_size_human", "?"))

    for path in entry.get("paths") or []:
        add(path, entry.get("total_size_human", "?"))

    analysis = entry.get("analysis") or {}
    config_key = "settings_and_config_en" if lang == "en" else "settings_and_config_hu"
    files_key = "local_files_en" if lang == "en" else "local_files_hu"
    for path in analysis.get(files_key) or analysis.get("local_files_en") or []:
        add(path)
    for path in analysis.get(config_key) or analysis.get("settings_and_config_en") or []:
        if path.startswith("/") or path.startswith("~"):
            add(path)

    profile = entry.get("profile") or {}
    for member in profile.get("members_preview") or []:
        name = member.get("name") or member.get("id") or "?"
        rows.append({"path": f"[member] {name}", "size_human": member.get("type", "?")})

    return rows


def _filter_related_paths(rows: list[dict], comp_type: str) -> list[dict]:
    if comp_type != "application":
        return rows
    filtered: list[dict] = []
    for row in rows:
        path = row.get("path", "")
        if ".app/Contents/" in path:
            continue
        filtered.append(row)
    return filtered


def collect_config_paths(entry: dict, lang: str) -> list[str]:
    analysis = entry.get("analysis") or {}
    key = "settings_and_config_en" if lang == "en" else "settings_and_config_hu"
    items = list(analysis.get(key) or analysis.get("settings_and_config_en") or [])
    return [item for item in items if item]


def build_install_steps(entry: dict, inventory_dir: Path, lang: str) -> list[str]:
    decision = entry.get("decision") or "later"
    comp_type = entry.get("type") or ""
    name = entry.get("component_name") or "?"
    paths = entry.get("paths") or []
    analysis = entry.get("analysis") or {}
    steps: list[str] = []

    if decision == "skip":
        if comp_type.endswith("_group"):
            return [_step(lang, "group_skip")]
        return [_step(lang, "skip")]

    if decision == "later":
        return [_step(lang, "later")]

    guidance_key = f"migration_guidance_{lang}" if lang == "hu" else "migration_guidance_en"
    guidance = analysis.get(guidance_key) or analysis.get("migration_guidance_en") or ""

    if comp_type == "homebrew_cask":
        pkg = name.lower().replace(" ", "-")
        steps.append(_step(lang, "brew_cask", name=pkg))
    elif comp_type == "homebrew_formula":
        steps.append(_step(lang, "brew_formula", name=name))
    elif comp_type == "homebrew_group":
        if decision == "reinstall":
            steps.append(_step(lang, "brew_bundle"))
        steps.append(_step(lang, "group_reinstall"))
    elif comp_type == "vscode_extension":
        ext_id = _extension_id_from_entry(entry)
        cli = _editor_cli_for_source(entry.get("source") or name, inventory_dir)
        if decision == "reinstall" and ext_id:
            steps.append(_step(lang, "vscode_ext_reinstall", cli=cli, ext_id=ext_id))
        elif decision == "migrate" and paths:
            steps.append(_step(lang, "vscode_ext_copy", path=paths[0]))
        if not ext_id and decision == "reinstall":
            steps.append(_step(lang, "vscode_restore"))
    elif comp_type == "vscode_editor":
        steps.append(_step(lang, "vscode_settings"))
        if decision == "reinstall":
            steps.append(_step(lang, "vscode_restore"))
        for path in paths[:5]:
            if "Application Support" in path or path.endswith(".json"):
                steps.append(_step(lang, "copy_path", path=path))
    elif comp_type == "vscode_extensions_group":
        steps.append(_step(lang, "vscode_restore"))
    elif comp_type == "application":
        app_name = name if name.endswith(".app") else f"{name}.app"
        if decision == "reinstall":
            steps.append(_step(lang, "app_reinstall", name=app_name))
        else:
            steps.append(_step(lang, "app_migrate"))
            for path in paths[:3]:
                steps.append(_step(lang, "copy_path", path=path))
    elif comp_type == "applications_group":
        if decision == "reinstall":
            steps.append(_step(lang, "brew_bundle"))
        steps.append(_step(lang, "group_reinstall"))
    elif comp_type == "shell_aliases_group":
        steps.append(_step(lang, "aliases"))
    elif comp_type in ("quick_action_workflow", "shortcuts_app"):
        steps.append(_step(lang, "quick_actions"))
    elif comp_type == "audio_device":
        steps.append(_step(lang, "audio"))
    elif comp_type == "profiled_folder":
        for path in paths[:1]:
            steps.append(_step(lang, "copy_path", path=path))
            steps.append(_step(lang, "rsync", path=path))
    elif comp_type == "profiled_folders_group":
        steps.append(_step(lang, "group_reinstall"))
        for path in paths[:3]:
            steps.append(_step(lang, "copy_path", path=path))
    elif comp_type == "browser_extensions_group":
        browser = (entry.get("profile") or {}).get("browser") or name.split()[0]
        steps.append(f"Reinstall {browser} extensions via browser sync or extension IDs from inventory.")
    elif comp_type.startswith("tool_"):
        steps.append(_step(lang, "brew_bundle"))
        steps.append(_step(lang, "app_reinstall", name=name))

    if decision == "migrate":
        for path in paths:
            if path and path not in {s for s in steps} and "Application Support" not in path:
                if path.startswith("/") and comp_type not in ("vscode_extension", "profiled_folder"):
                    steps.append(_step(lang, "rsync", path=path))

    if guidance:
        for sentence in _split_guidance(guidance):
            if sentence and sentence not in steps:
                steps.append(sentence)

    profile = entry.get("profile") or {}
    for line in profile.get("reinstall_script_lines") or []:
        if line.strip() and line not in steps:
            steps.append(line.strip())

    if not steps:
        steps.append(_step(lang, "restore_all"))

    return _dedupe_steps(steps)


def _split_guidance(text: str) -> list[str]:
    parts: list[str] = []
    for chunk in text.replace("\n", " ").split(". "):
        chunk = chunk.strip()
        if chunk:
            if not chunk.endswith("."):
                chunk += "."
            parts.append(chunk)
    return parts


def _dedupe_steps(steps: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for step in steps:
        key = step.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(step.strip())
    return result


def _infer_source(entry: dict) -> str:
    if entry.get("source"):
        return str(entry["source"])
    paths = entry.get("paths") or []
    if any("/.cursor/" in p for p in paths):
        return "Cursor"
    if any("/.vscode/" in p for p in paths):
        return "Visual Studio Code"
    return ""


def decisions_to_report_entries(store: dict) -> list[dict]:
    entries: list[dict] = []
    for comp_id, raw in store.get("decisions", {}).items():
        decision = raw.get("decision")
        if not decision or decision == "quit":
            continue
        entry = {
            **raw,
            "component_id": raw.get("component_id") or comp_id,
            "component_name": raw.get("component_name") or comp_id,
            "type": raw.get("type") or "",
            "decision": decision,
            "source": _infer_source(raw),
        }
        entries.append(entry)
    entries.sort(
        key=lambda e: (
            DECISION_ORDER.index(e["decision"]) if e["decision"] in DECISION_ORDER else 99,
            e.get("component_name", "").lower(),
        )
    )
    return entries


def enrich_entry_for_report(entry: dict, inventory_dir: Path, lang: str) -> dict:
    report_entry = dict(entry)
    report_entry["component_name"] = _display_component_name(entry)
    report_entry["related_paths"] = _filter_related_paths(
        collect_related_paths(entry, lang), entry.get("type", "")
    )
    report_entry["config_paths"] = collect_config_paths(entry, lang)
    report_entry["install_steps"] = build_install_steps(entry, inventory_dir, lang)
    what_key = f"what_it_is_{lang}" if lang == "hu" else "what_it_is_en"
    report_entry["summary"] = (entry.get("analysis") or {}).get(what_key) or (
        (entry.get("analysis") or {}).get("what_it_is_en")
    )
    return report_entry


def write_interactive_markdown(
    store: dict,
    inventory_dir: Path,
    out_path: Path,
    lang: str,
    other_path: Path,
) -> None:
    entries = decisions_to_report_entries(store)
    counts = Counter(e["decision"] for e in entries)
    lines = [
        _label(lang, "lang_link").format(other=other_path.name),
        "",
        _label(lang, "title"),
        "",
        _label(lang, "intro"),
        "",
        _label(lang, "summary"),
        "",
    ]
    for decision in DECISION_ORDER:
        if counts.get(decision):
            lines.append(f"- **{decision}**: {counts[decision]}")
    lines.append("")

    current_section = ""
    for entry in entries:
        decision = entry["decision"]
        section_key = DECISION_SECTION.get(decision, "section_later")
        section_title = _label(lang, section_key)
        if section_title != current_section:
            lines.extend(["", section_title, ""])
            current_section = section_title

        enriched = enrich_entry_for_report(entry, inventory_dir, lang)
        name = _display_component_name(enriched)
        comp_type = enriched["type"]
        conf = enriched.get("confidence")
        conf_str = str(conf) if conf is not None else "?"

        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"- **{_label(lang, 'decision')}:** `{decision}`")
        lines.append(f"- **{_label(lang, 'type')}:** `{comp_type}`")
        lines.append(f"- **{_label(lang, 'confidence')}:** {conf_str}")
        if enriched.get("summary"):
            lines.append(f"- **Summary:** {enriched['summary']}")
        lines.append("")

        lines.append(_label(lang, "related_paths"))
        lines.append("")
        related = enriched["related_paths"]
        if related:
            lines.append(_label(lang, "path_header"))
            lines.append(_label(lang, "path_sep"))
            for row in related[:40]:
                lines.append(f"| `{row['path']}` | {row['size_human']} |")
            if len(related) > 40:
                lines.append(f"| ... | +{len(related) - 40} more |")
        else:
            lines.append(_label(lang, "no_paths"))
        lines.append("")

        config_paths = enriched["config_paths"]
        if config_paths:
            lines.append(_label(lang, "config"))
            lines.append("")
            for path in config_paths[:20]:
                lines.append(f"- `{path}`")
            lines.append("")

        lines.append(_label(lang, "steps"))
        lines.append("")
        steps = enriched["install_steps"]
        if steps:
            for idx, step in enumerate(steps, start=1):
                lines.append(f"{idx}. {step}")
        else:
            lines.append(_label(lang, "no_steps"))
        lines.append("")

    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_interactive_json(
    store: dict,
    inventory_dir: Path,
    out_path: Path,
    meta: dict,
) -> None:
    from interactive import decision_to_folder_results

    entries = decisions_to_report_entries(store)
    folder_results = decision_to_folder_results(store)
    enriched_en = [enrich_entry_for_report(e, inventory_dir, "en") for e in entries]
    enriched_hu = [enrich_entry_for_report(e, inventory_dir, "hu") for e in entries]
    payload = {
        **meta,
        "summary": dict(Counter(e["decision"] for e in entries)),
        "component_count": len(entries),
        "result_count": len(folder_results),
        "results": folder_results,
        "components_en": enriched_en,
        "components_hu": enriched_hu,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    hu_payload = {**payload, "lang": "hu"}
    from paths import report_paths

    json_paths = report_paths(out_path)
    json_paths["hu"].write_text(json.dumps(hu_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_interactive_reports(
    store: dict,
    inventory_dir: Path,
    md_base: Path,
    json_base: Path,
    meta: dict,
) -> None:
    from paths import report_paths

    md_paths = report_paths(md_base)
    json_paths = report_paths(json_base)
    inventory_dir = Path(inventory_dir)

    for lang in ("en", "hu"):
        other_md = md_paths["hu"] if lang == "en" else md_paths["en"]
        write_interactive_markdown(store, inventory_dir, md_paths[lang], lang, other_md)

    write_interactive_json(store, inventory_dir, json_paths["en"], {**meta, "lang": "en"})
