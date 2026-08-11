"""Build parent/child install groups (Homebrew, app ecosystems, editors)."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from interactive_report import BREW_DISPLAY_NAMES, _display_component_name

BREW_TYPES = {"homebrew_formula", "homebrew_cask", "homebrew_group"}
VSCODE_EXT = "vscode_extension"

# DevOps / CLI formulae shown first in Homebrew group
BREW_PRIORITY = (
    "awscli",
    "azure-cli",
    "gcloud-cli",
    "kubectl",
    "helm",
    "terraform",
    "docker",
    "gh",
    "jq",
    "yq",
    "node",
    "python",
    "go",
    "ruby",
    "pyenv",
    "nvm",
    "tenv",
    "ollama",
    "ripgrep",
    "sqlite",
)

GENERIC_FOLDER_NAMES = frozenset(
    {
        "ableton",
        "audio",
        "backup",
        "components",
        "plug-ins",
        "vst",
        "vst3",
        "application support",
        "projects",
        "export",
        "remix",
        "samples",
        "presets",
        "database",
        "factory packs",
        "preferences",
        "app-resources",
        "splice_folder",
    }
)

VENDOR_CHILD_PATTERNS = (
    r"fabfilter",
    r"izotope",
    r"native instruments",
    r"spitfire",
    r"waves",
    r"arturia",
    r"kontakt",
    r"uad\b",
    r"universal audio",
    r"/audio/plug-ins/",
    r"\.vst3",
    r"\.vst\b",
    r"\.component",
    r"paceap",
    r"valhalla",
    r"soundtoys",
    r"blackhole",
)

ECOSYSTEM_EXTRA_CHILD_IDS: dict[str, tuple[str, ...]] = {
    "ableton_live": ("tool:creative:ableton_pioneer_dj",),
}

ECOSYSTEMS: list[dict] = [
    {
        "id": "ableton_live",
        "name_en": "Ableton Live",
        "name_hu": "Ableton Live",
        "parent_ids": ("tool:creative:ableton_live", "app:Ableton Live 12 Suite.app"),
        "match": VENDOR_CHILD_PATTERNS + (r"ableton",),
        "exclude": (r"rekordbox", r"serato", r"traktor", r"pioneer dj"),
    },
    {
        "id": "rekordbox",
        "name_en": "Rekordbox",
        "name_hu": "Rekordbox",
        "parent_ids": ("tool:creative:rekordbox",),
        "match": (r"rekordbox", r"pioneer dj", r"pioneerdj"),
        "exclude": (r"ableton", r"fabfilter"),
    },
    {
        "id": "serato_dj",
        "name_en": "Serato DJ",
        "name_hu": "Serato DJ",
        "parent_ids": ("tool:creative:serato_dj",),
        "match": (r"serato",),
        "exclude": (),
    },
    {
        "id": "adobe_cc",
        "name_en": "Adobe Creative Cloud",
        "name_hu": "Adobe Creative Cloud",
        "parent_ids": ("tool:creative:adobe_creative_cloud",),
        "match": (r"adobe", r"lightroom", r"photoshop", r"illustrator", r"premiere"),
        "exclude": (),
    },
    {
        "id": "davinci",
        "name_en": "DaVinci Resolve",
        "name_hu": "DaVinci Resolve",
        "parent_ids": ("tool:creative:davinci_resolve",),
        "match": (r"davinci", r"blackmagic", r"resolve"),
        "exclude": (),
    },
]

EDITOR_GROUPS: list[dict] = [
    {
        "id": "vscode",
        "name_en": "Visual Studio Code",
        "name_hu": "Visual Studio Code",
        "source_tokens": ("visual studio code", "vscode"),
        "tool_ids": ("tool:editor:vscode",),
    },
    {
        "id": "cursor",
        "name_en": "Cursor",
        "name_hu": "Cursor",
        "source_tokens": ("cursor",),
        "tool_ids": ("tool:ai_coding:cursor", "tool:editor:cursor"),
    },
]


def _load_json(path: Path) -> dict | list:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _component_text(comp: dict) -> str:
    parts = [
        comp.get("component_id") or "",
        comp.get("component_name") or "",
        comp.get("type") or "",
        comp.get("source") or "",
        comp.get("summary") or "",
    ]
    for row in comp.get("related_paths") or []:
        parts.append(row.get("path") or "")
    for step in comp.get("install_steps") or []:
        parts.append(step)
    analysis = comp.get("analysis") or {}
    for key in ("what_it_is_en", "migration_guidance_en", "local_files_en"):
        val = analysis.get(key)
        if isinstance(val, list):
            parts.extend(str(v) for v in val)
        elif val:
            parts.append(str(val))
    return " ".join(parts).lower()


def _primary_step(comp: dict) -> str:
    steps = comp.get("install_steps") or []
    if not steps:
        return ""
    step = steps[0]
    if comp.get("type") in ("homebrew_formula", "homebrew_cask"):
        raw = (comp.get("component_id") or "").split(":")[-1]
        if raw:
            kind = comp.get("type") or "homebrew_formula"
            return _brew_install_step(raw, kind)
    return step


def _slim_child(comp: dict, *, source: str = "decision") -> dict:
    return {
        "component_id": comp.get("component_id"),
        "name": _display_component_name(comp),
        "type": comp.get("type"),
        "decision": comp.get("decision"),
        "install_step": _primary_step(comp),
        "source": source,
    }


def _inventory_child(name: str, kind: str, path: str, decision: str = "review") -> dict:
    return {
        "component_id": None,
        "name": name,
        "type": kind,
        "decision": decision,
        "install_step": "",
        "path": path,
        "source": "inventory",
    }


def _decision_summary(children: list[dict]) -> dict[str, int]:
    return dict(Counter(c.get("decision") or "review" for c in children))


def _brew_display(name: str) -> str:
    return BREW_DISPLAY_NAMES.get(name, name)


def _brew_install_step(name: str, kind: str) -> str:
    if kind == "homebrew_cask":
        return f"brew install --cask {name}"
    return f"brew install {name}"


def _brew_key(name: str, kind: str) -> str:
    return f"{kind}:{name.lower()}"


def _brew_key_from_comp(comp: dict) -> str | None:
    comp_id = comp.get("component_id") or ""
    if comp_id.startswith("brew:formula:"):
        return f"homebrew_formula:{comp_id.removeprefix('brew:formula:').lower()}"
    if comp_id.startswith("brew:cask:"):
        return f"homebrew_cask:{comp_id.removeprefix('brew:cask:').lower()}"
    if comp.get("type") in ("homebrew_formula", "homebrew_cask"):
        return _brew_key(comp.get("component_name") or "", comp["type"])
    return None


def _build_homebrew_group(
    components_by_id: dict[str, dict],
    inventory_dir: Path,
    lang: str,
) -> dict:
    brew_data = _load_json(inventory_dir / "homebrew-inventory.json")
    if not isinstance(brew_data, dict):
        brew_data = {}

    children: list[dict] = []
    seen: set[str] = set()

    def add_brew(name: str, kind: str, decision: str | None = None) -> None:
        if not name:
            return
        key = _brew_key(name, kind)
        if key in seen:
            return
        seen.add(key)
        comp_id = f"brew:cask:{name}" if kind == "homebrew_cask" else f"brew:formula:{name}"
        comp = components_by_id.get(comp_id)
        if comp:
            children.append(_slim_child(comp))
            return
        fallback_decision = decision or "reinstall"
        group = components_by_id.get("group:homebrew_other")
        if group and not decision:
            fallback_decision = group.get("decision") or "reinstall"
        children.append(
            {
                "component_id": comp_id,
                "name": _brew_display(name),
                "type": kind,
                "decision": fallback_decision,
                "install_step": _brew_install_step(name, kind),
                "source": "brewfile",
            }
        )

    for pkg in brew_data.get("formulae") or []:
        add_brew(str(pkg.get("name", "")), "homebrew_formula")
    for pkg in brew_data.get("casks") or []:
        add_brew(str(pkg.get("name", "")), "homebrew_cask")

    for comp in components_by_id.values():
        if comp.get("type") not in ("homebrew_formula", "homebrew_cask"):
            continue
        key = _brew_key_from_comp(comp)
        if not key or key in seen:
            continue
        seen.add(key)
        children.append(_slim_child(comp))

    priority_index = {n: i for i, n in enumerate(BREW_PRIORITY)}

    def sort_key(item: dict) -> tuple:
        raw = (item.get("component_id") or "").split(":")[-1].lower()
        pri = priority_index.get(raw, 999)
        return (pri, (item.get("name") or "").lower())

    children.sort(key=sort_key)

    # Collapse duplicate display names (e.g. powershell formula + cask)
    by_name: dict[str, dict] = {}
    for child in children:
        name = (child.get("name") or "").lower()
        existing = by_name.get(name)
        if not existing:
            by_name[name] = child
            continue
        if existing.get("source") == "brewfile" and child.get("source") == "decision":
            by_name[name] = child
    children = list(by_name.values())
    children.sort(key=sort_key)

    group_name = "Homebrew" if lang == "en" else "Homebrew"
    summary = _decision_summary(children)
    return {
        "group_id": "homebrew",
        "group_name": group_name,
        "group_type": "package_manager",
        "decision_summary": summary,
        "group_steps": [
            "brew bundle install --file=~/migration-inventory/Brewfile"
            if lang == "en"
            else "brew bundle install --file=~/migration-inventory/Brewfile",
        ],
        "children": children,
    }


def _matches_ecosystem(text: str, spec: dict, *, vendor_only: bool = False) -> bool:
    if any(re.search(pat, text) for pat in spec.get("exclude") or ()):
        return False
    patterns = spec.get("vendor_match") or VENDOR_CHILD_PATTERNS
    if vendor_only:
        return any(re.search(pat, text) for pat in patterns)
    return any(re.search(pat, text) for pat in spec.get("match") or patterns)


def _child_dedupe_key(child: dict) -> str:
    if child.get("component_id"):
        return str(child["component_id"])
    if child.get("path"):
        return str(child["path"])
    return f"name:{(child.get('name') or '').lower()}"


def _is_noise_ecosystem_path(path: str) -> bool:
    lower = path.lower()
    noise = (
        "/.docker/",
        "/cli-plugins",
        "/containers/com.apple.",
        "/application scripts/com.apple.",
        "/.codex/",
        "/sessionmanager",
        "/splice/",
    )
    return any(token in lower for token in noise)


def _is_noise_ecosystem_child(comp: dict) -> bool:
    name = (comp.get("component_name") or comp.get("name") or "").strip().lower()
    if name in GENERIC_FOLDER_NAMES:
        return True
    if name.endswith(".app") and "live" not in name and comp.get("type") == "profiled_folder":
        return True
    return False


def _build_ecosystem_groups(
    components: list[dict],
    components_by_id: dict[str, dict],
    inventory_dir: Path,
    lang: str,
) -> list[dict]:
    assigned: set[str] = set()
    groups: list[dict] = []

    custom = _load_json(inventory_dir / "custom-paths.json")
    custom_paths = custom.get("paths") if isinstance(custom, dict) else []

    for spec in ECOSYSTEMS:
        name = spec["name_en"] if lang == "en" else spec["name_hu"]
        parent = None
        for pid in spec.get("parent_ids") or ():
            if pid in components_by_id:
                parent = _slim_child(components_by_id[pid])
                assigned.add(pid)
                break

        children: list[dict] = []
        child_ids: set[str] = set()

        extra_ids = ECOSYSTEM_EXTRA_CHILD_IDS.get(spec["id"], ())
        for comp in components:
            cid = comp.get("component_id") or ""
            if cid in assigned or cid in child_ids:
                continue
            if comp.get("type") in BREW_TYPES:
                continue
            if comp.get("type") == VSCODE_EXT:
                continue
            if cid in (spec.get("parent_ids") or ()):
                continue
            if cid not in extra_ids:
                if _is_noise_ecosystem_child(comp):
                    continue
                if not _matches_ecosystem(_component_text(comp), spec, vendor_only=True):
                    continue
            children.append(_slim_child(comp))
            child_ids.add(_child_dedupe_key(children[-1]))
            assigned.add(cid)

        # Supplement from custom-paths (vendor folders not individually reviewed)
        for entry in custom_paths or []:
            path = str(entry.get("path") or "")
            if _is_noise_ecosystem_path(path):
                continue
            entry_name = str(entry.get("name") or Path(path).name)
            blob = f"{path} {entry_name}".lower()
            if not _matches_ecosystem(blob, spec, vendor_only=True):
                continue
            if entry_name.strip().lower() in GENERIC_FOLDER_NAMES:
                continue
            key = f"path:{path}"
            if key in child_ids:
                continue
            children.append(
                _inventory_child(
                    entry_name,
                    entry.get("kind") or "profiled_folder",
                    path,
                    decision="review",
                )
            )
            child_ids.add(key)

        if not parent and not children:
            continue

        children.sort(key=lambda c: (c.get("name") or "").lower())
        groups.append(
            {
                "group_id": f"ecosystem:{spec['id']}",
                "group_name": name,
                "group_type": "app_ecosystem",
                "parent": parent,
                "decision_summary": _decision_summary([c for c in ([parent] if parent else []) + children]),
                "children": children,
            }
        )

    return groups


def _build_editor_groups(components: list[dict], lang: str) -> list[dict]:
    groups: list[dict] = []
    for spec in EDITOR_GROUPS:
        name = spec["name_en"] if lang == "en" else spec["name_hu"]
        parent = None
        children: list[dict] = []
        tokens = spec.get("source_tokens") or ()

        for comp in components:
            if comp.get("type") != VSCODE_EXT:
                continue
            source = (comp.get("source") or "").lower()
            if not any(tok in source for tok in tokens):
                continue
            children.append(_slim_child(comp))

        for comp in components:
            cid = comp.get("component_id") or ""
            if cid in spec.get("tool_ids") or ():
                parent = _slim_child(comp)
                break

        if not parent and not children:
            continue

        children.sort(key=lambda c: (c.get("name") or "").lower())
        groups.append(
            {
                "group_id": f"editor:{spec['id']}",
                "group_name": name,
                "group_type": "editor",
                "parent": parent,
                "decision_summary": _decision_summary([c for c in ([parent] if parent else []) + children]),
                "children": children,
            }
        )
    return groups


def build_install_groups(
    components: list[dict],
    inventory_dir: Path,
    lang: str = "en",
) -> list[dict]:
    """Return ordered install groups for report, plan, and dashboard."""
    components_by_id = {
        c["component_id"]: c for c in components if c.get("component_id")
    }
    inventory_dir = Path(inventory_dir)

    groups: list[dict] = []
    homebrew = _build_homebrew_group(components_by_id, inventory_dir, lang)
    if homebrew.get("children"):
        groups.append(homebrew)

    groups.extend(_build_ecosystem_groups(components, components_by_id, inventory_dir, lang))
    groups.extend(_build_editor_groups(components, lang))
    return groups


def format_install_groups_markdown(groups: list[dict], lang: str) -> list[str]:
    title = "## Install groups — overview" if lang == "en" else "## Telepítési csoportok — áttekintés"
    intro = (
        "Grouped view: what to install or migrate together (Homebrew, DAW plugins, editors)."
        if lang == "en"
        else "Csoportosított nézet: mi tartozik együtt (Homebrew, DAW pluginek, editorok)."
    )
    lines = ["", title, "", intro, ""]

    child_label = "Items" if lang == "en" else "Tételek"
    parent_label = "Main app" if lang == "en" else "Fő alkalmazás"
    steps_label = "Group install" if lang == "en" else "Csoport telepítés"

    for group in groups:
        lines.append(f"### {group.get('group_name', '?')}")
        lines.append("")
        summary = group.get("decision_summary") or {}
        if summary:
            parts = [f"{k}: {v}" for k, v in sorted(summary.items()) if v]
            if parts:
                lines.append(f"- **Summary:** {', '.join(parts)}")
        for step in group.get("group_steps") or []:
            lines.append(f"- **{steps_label}:** `{step}`")
        parent = group.get("parent")
        if parent:
            lines.append(
                f"- **{parent_label}:** {parent.get('name')} (`{parent.get('decision')}`)"
            )
        lines.append(f"- **{child_label}:**")
        for child in group.get("children") or []:
            step = child.get("install_step") or child.get("path") or ""
            step_bit = f" — `{step}`" if step else ""
            lines.append(f"  - {child.get('name')} (`{child.get('decision')}`){step_bit}")
        lines.append("")

    return lines
