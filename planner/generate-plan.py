#!/usr/bin/env python3
"""
generate-plan.py — Phase C: migration checklist generator

Reads:
  - ~/migration-inventory/collector-output.json
  - ~/migration-inventory/analysis-report.json

Writes:
  - ~/migration-inventory/migration-plan.md + migration-plan_HU.md
  - ~/migration-inventory/migration-plan.json + migration-plan_HU.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from i18n import pt

_ANALYZER_DIR = Path(__file__).resolve().parents[1] / "analyzer"
sys.path.append(str(_ANALYZER_DIR))

from paths import report_paths  # noqa: E402
from rule_based import reason_for_lang  # noqa: E402

INVENTORY_DIR = Path.home() / "migration-inventory"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_brewfile_formulae(brewfile: Path) -> list[str]:
    if not brewfile.exists():
        return []
    names = []
    for line in brewfile.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith('brew "') and line.endswith('"'):
            names.append(line[6:-1])
        elif line.startswith("cask "):
            m = re.match(r'cask "([^"]+)"', line)
            if m:
                names.append(m.group(1))
    return names


def parse_applications_md(path: Path) -> list[dict]:
    if not path.exists():
        return []
    apps = []
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## /Applications"):
            section = "system"
        elif line.startswith("## ~/Applications"):
            section = "user"
        elif section:
            match = re.search(r"(\S+\.app)\s*$", line)
            if match:
                apps.append({"name": match.group(1), "source": section})
    return apps


def load_interactive_decisions(inventory_dir: Path) -> dict | None:
    path = inventory_dir / "interactive-decisions.json"
    if not path.exists():
        return None
    return load_json(path)


def interactive_reason(entry: dict, lang: str) -> str:
    analysis = entry.get("analysis") or {}
    if lang == "hu":
        return (
            analysis.get("migration_guidance_hu")
            or analysis.get("what_it_is_hu")
            or entry.get("decision", "")
        )
    return (
        analysis.get("migration_guidance_en")
        or analysis.get("what_it_is_en")
        or entry.get("decision", "")
    )


def load_restore_manifest(inventory_dir: Path) -> dict | None:
    path = inventory_dir / "restore-manifest.json"
    if not path.exists():
        return None
    return load_json(path)


def restore_component_labels(manifest: dict | None, lang: str) -> str:
    if not manifest:
        return "aliases, shell, homebrew, vscode" if lang == "en" else "aliasok, shell, homebrew, vscode"
    labels = [c.get("label", c.get("id", "?")) for c in manifest.get("components") or []]
    return ", ".join(labels) if labels else ("(none)" if lang == "en" else "(nincs)")


def build_plan(
    analysis: dict,
    collector: dict,
    inventory_dir: Path,
    lang: str,
    other_md_name: str,
    interactive: dict | None = None,
    manifest: dict | None = None,
) -> tuple[list[str], dict]:
    results = analysis.get("results", [])
    by_category: dict[str, list[dict]] = {
        "user_custom": [],
        "app_data": [],
        "cache_or_temp": [],
        "uncertain": [],
    }
    for r in results:
        cat = r.get("category", "uncertain")
        by_category.setdefault(cat, []).append(r)

    link_key = "lang_link_en" if lang == "en" else "lang_link_hu"
    lines = [
        pt(lang, link_key, other=other_md_name),
        "",
        pt(lang, "title"),
        "",
        pt(lang, "intro"),
        "",
    ]

    interactive_entries = list((interactive or {}).get("decisions", {}).values())
    if interactive_entries:
        section_title = (
            "## Interactive decisions (your choices)"
            if lang == "en"
            else "## Interaktív döntések (a te választásaid)"
        )
        lines.append(section_title)
        decision_labels = {
            "migrate": "migrate" if lang == "en" else "áthozni",
            "reinstall": "reinstall" if lang == "en" else "újratelepíteni",
            "skip": "skip" if lang == "en" else "kihagyni",
            "later": "decide later" if lang == "en" else "később eldönteni",
        }
        for entry in sorted(
            interactive_entries,
            key=lambda e: (e.get("type", ""), e.get("component_name", "")),
        ):
            decision = entry.get("decision", "")
            if decision not in decision_labels:
                continue
            name = entry.get("component_name", entry.get("component_id", "?"))
            label = decision_labels[decision]
            reason = interactive_reason(entry, lang)
            lines.append(f"- [ ] **{name}** — {label}: {reason}")
        lines.append("")

    lines.append(pt(lang, "section_copy"))
    for r in sorted(by_category.get("user_custom", []), key=lambda x: x.get("path", "")):
        lines.append(
            pt(
                lang,
                "item_copy",
                path=r.get("path", ""),
                size=r.get("size_human", "?"),
                reason=reason_for_lang(r, lang),
            )
        )
    if not by_category.get("user_custom"):
        lines.append("- [ ] _(none)_")

    lines.extend(["", pt(lang, "section_reinstall")])
    apps = parse_applications_md(inventory_dir / "01-applications.md")
    brew_items = parse_brewfile_formulae(inventory_dir / "Brewfile")
    seen = set()
    for app in apps[:40]:
        key = app["name"]
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            pt(lang, "item_reinstall", name=app["name"], source=app["source"])
        )
    for name in brew_items[:30]:
        key = f"brew:{name}"
        if key in seen:
            continue
        seen.add(key)
        lines.append(pt(lang, "item_reinstall", name=name, source="homebrew"))

    app_data_sample = sorted(
        by_category.get("app_data", []),
        key=lambda x: -(x.get("size_bytes") or 0),
    )[:15]
    for r in app_data_sample:
        lines.append(
            pt(
                lang,
                "item_app_data_note",
                path=r.get("path", ""),
                size=r.get("size_human", "?"),
                reason=reason_for_lang(r, lang) or "app_data",
            )
        )

    lines.extend(["", pt(lang, "section_rebuild")])
    if manifest and manifest.get("components"):
        lines.extend(["", pt(lang, "section_restore_auto")])
        lines.append(
            pt(
                lang,
                "item_restore_auto",
                components=restore_component_labels(manifest, lang),
            )
        )
        lines.append(pt(lang, "item_restore_dry_run"))
    lines.append(pt(lang, "item_rebuild_brew"))
    lines.append(pt(lang, "item_rebuild_dotfiles"))
    lines.append(pt(lang, "item_rebuild_runtimes"))

    lines.extend(["", pt(lang, "section_skip")])
    for r in sorted(by_category.get("cache_or_temp", []), key=lambda x: x.get("path", "")):
        lines.append(
            pt(
                lang,
                "item_skip",
                path=r.get("path", ""),
                size=r.get("size_human", "?"),
                reason=reason_for_lang(r, lang),
            )
        )
    if not by_category.get("cache_or_temp"):
        lines.append("- [ ] _(none)_")

    lines.extend(["", pt(lang, "section_review")])
    for r in sorted(by_category.get("uncertain", []), key=lambda x: x.get("path", "")):
        lines.append(
            pt(
                lang,
                "item_review",
                path=r.get("path", ""),
                size=r.get("size_human", "?"),
                reason=reason_for_lang(r, lang),
            )
        )
    if not by_category.get("uncertain"):
        lines.append("- [ ] _(none)_")

    lines.extend(["", pt(lang, "section_auth")])
    lines.append(pt(lang, "item_auth_ssh"))
    lines.append(pt(lang, "item_auth_gpg"))
    lines.append(pt(lang, "item_auth_cloud"))
    lines.append(pt(lang, "item_auth_git"))

    counts = {
        "copy": len(by_category.get("user_custom", [])),
        "app": len(by_category.get("app_data", [])),
        "skip": len(by_category.get("cache_or_temp", [])),
        "review": len(by_category.get("uncertain", [])),
    }
    lines.extend(
        [
            "",
            pt(lang, "summary"),
            pt(lang, "summary_counts", **counts),
        ]
    )

    plan_json = {
        "generated_from": {
            "collector": str(collector.get("generated_at", "")),
            "analysis_mode": analysis.get("mode"),
        },
        "lang": lang,
        "counts": counts,
        "interactive_decision_count": len(
            [e for e in interactive_entries if e.get("decision") in ("migrate", "reinstall", "skip", "later")]
        ),
        "sections": {
            "copy": by_category.get("user_custom", []),
            "app_data": by_category.get("app_data", []),
            "skip": by_category.get("cache_or_temp", []),
            "review": by_category.get("uncertain", []),
        },
    }
    return lines, plan_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase C — migration plan generator")
    parser.add_argument(
        "--collector-json",
        type=Path,
        default=INVENTORY_DIR / "collector-output.json",
    )
    parser.add_argument(
        "--analysis-json",
        type=Path,
        default=INVENTORY_DIR / "analysis-report.json",
    )
    parser.add_argument(
        "--inventory-dir",
        type=Path,
        default=None,
        help="Directory with Phase A markdown/Brewfile (default: parent of collector JSON)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=INVENTORY_DIR / "migration-plan.md",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=INVENTORY_DIR / "migration-plan.json",
    )
    args = parser.parse_args()

    if not args.analysis_json.exists():
        print(pt("en", "input_analysis_missing", path=args.analysis_json), file=sys.stderr)
        sys.exit(1)
    if not args.collector_json.exists():
        print(pt("en", "input_collector_missing", path=args.collector_json), file=sys.stderr)
        sys.exit(1)

    inventory_dir = args.inventory_dir or args.collector_json.parent

    analysis = load_json(args.analysis_json)
    collector = load_json(args.collector_json)
    interactive = load_interactive_decisions(inventory_dir)
    manifest = load_restore_manifest(inventory_dir)

    md_paths = report_paths(args.output)
    json_paths = report_paths(args.output_json)

    for lang in ("en", "hu"):
        other_name = md_paths["hu"].name if lang == "en" else md_paths["en"].name
        lines, plan_json = build_plan(
            analysis, collector, inventory_dir, lang, other_name, interactive, manifest
        )
        md_paths[lang].write_text("\n".join(lines) + "\n", encoding="utf-8")
        json_paths[lang].write_text(
            json.dumps(plan_json, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(pt("en", "done", path=md_paths["en"]))
    print(pt("en", "done", path=md_paths["hu"]))


if __name__ == "__main__":
    main()
