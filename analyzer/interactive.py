"""Interactive migration review — AI deep-dive per app/component with user decisions."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from discovery import (
    consolidate_for_interactive,
    discover_components,
    discovery_summary,
    group_components,
)
from i18n import t
from llm_client import generate_content_with_retries

INVENTORY_DIR = Path.home() / "migration-inventory"
DECISIONS_FILE = INVENTORY_DIR / "interactive-decisions.json"

INTERACTIVE_PROMPT = """You are a macOS migration expert. The user wants EVERY local path and component on this Mac understood before migrating to a new machine.

Analyze this component in depth using the profiler metadata and paths provided. Reply with ONLY valid JSON:

{{
  "what_it_is_en": "1-2 sentences",
  "what_it_is_hu": "1-2 sentences in Hungarian",
  "purpose_en": "what the user typically uses this for on macOS",
  "purpose_hu": "Hungarian",
  "settings_and_config_en": ["settings, plists, env vars, config file paths — no secret values"],
  "settings_and_config_hu": ["Hungarian"],
  "local_files_en": ["every related local path worth considering for migration"],
  "local_files_hu": ["Hungarian"],
  "migration_guidance_en": "concrete steps: copy vs reinstall vs skip; mention size if large",
  "migration_guidance_hu": "Hungarian",
  "default_recommendation": "migrate|reinstall|skip|review",
  "confidence": 0.0
}}

Component JSON:
{component_json}
"""

FALLBACK_ANALYSIS = {
    "what_it_is_en": "Local macOS component (rule-based fallback — no Agent Platform).",
    "what_it_is_hu": "Helyi macOS komponens (szabály alapú fallback).",
    "purpose_en": "Review manually.",
    "purpose_hu": "Kézi ellenőrzés szükséges.",
    "settings_and_config_en": [],
    "settings_and_config_hu": [],
    "local_files_en": [],
    "local_files_hu": [],
    "migration_guidance_en": "Decide based on whether you still use this on the new Mac.",
    "migration_guidance_hu": "Dönts aszerint, hogy az új Mac-en is használni fogod-e.",
    "default_recommendation": "review",
    "confidence": 0.3,
}

DECISION_TO_CATEGORY = {
    "migrate": "user_custom",
    "reinstall": "app_data",
    "skip": "cache_or_temp",
    "later": "uncertain",
}


def strip_json_fence(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def analyze_component_llm(
    component: dict,
    project: str,
    location: str,
    model: str,
) -> dict:
    prompt = INTERACTIVE_PROMPT.format(
        component_json=json.dumps(component, ensure_ascii=False, indent=2)
    )
    raw = generate_content_with_retries(prompt, project, location, model)
    parsed = json.loads(strip_json_fence(raw))
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Expected JSON object", raw, 0)
    return parsed


def load_decisions(path: Path) -> dict:
    if not path.exists():
        return {"decisions": {}, "meta": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_decisions(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def print_header(title: str, index: int, total: int) -> None:
    bar = "=" * 72
    print(f"\n{bar}\n[{index}/{total}] {title}\n{bar}")


def print_analysis(analysis: dict, *, show_hu: bool = True) -> None:
    print(f"\nWhat it is:\n  {analysis.get('what_it_is_en', '')}")
    print(f"\nPurpose:\n  {analysis.get('purpose_en', '')}")

    settings = analysis.get("settings_and_config_en") or []
    if settings:
        print("\nSettings / config:")
        for line in settings:
            print(f"  - {line}")

    local_files = analysis.get("local_files_en") or []
    if local_files:
        print("\nRelated local paths:")
        for line in local_files[:12]:
            print(f"  - {line}")
        if len(local_files) > 12:
            print(f"  ... and {len(local_files) - 12} more")

    print(f"\nMigration guidance:\n  {analysis.get('migration_guidance_en', '')}")
    rec = analysis.get("default_recommendation", "review")
    conf = analysis.get("confidence", "?")
    print(f"\nAI recommendation: {rec} (confidence: {conf})")

    if show_hu:
        print(f"\n--- HU ---")
        print(f"  {analysis.get('what_it_is_hu', '')}")
        print(f"  {analysis.get('migration_guidance_hu', '')}")


def print_component_summary(component: dict) -> None:
    print(f"Type: {component.get('type')}  |  Source: {component.get('source')}")
    if component.get("sensitive"):
        print("WARNING: Sensitive component — credentials/keys; migrate only if you understand the risk.")
    profile = component.get("profile") or {}
    if profile:
        print(
            f"  Profile: {profile.get('size_human', '?')} | "
            f"files(shallow): {profile.get('file_count_shallow', '?')} | "
            f"modified: {profile.get('last_modified', '?')} | "
            f"ext: {profile.get('dominant_extensions', '')}"
        )
    for path in component.get("paths") or []:
        print(f"  Path: {path}")
    related = component.get("related_paths") or []
    if related:
        print(f"  Related paths on disk: {len(related)} ({component.get('total_size_human', '?')} total)")
        for path in related[:8]:
            print(f"    - {path}")
        if len(related) > 8:
            print(f"    ... and {len(related) - 8} more")


def prompt_decision(default: str = "review") -> str:
    print(
        "\nDecision:"
        "\n  [m] migrate — copy data/config to the new Mac"
        "\n  [r] reinstall — install fresh, skip bulk local data"
        "\n  [s] skip — leave behind"
        "\n  [l] later — decide later"
        "\n  [a] ask AI again (refresh analysis)"
        "\n  [B] bulk skip — mark rest of this section as skip"
        "\n  [q] quit and save progress"
    )
    mapping = {
        "m": "migrate",
        "migrate": "migrate",
        "y": "migrate",
        "yes": "migrate",
        "r": "reinstall",
        "reinstall": "reinstall",
        "s": "skip",
        "skip": "skip",
        "n": "skip",
        "no": "skip",
        "l": "later",
        "later": "later",
        "a": "ask",
        "ask": "ask",
        "b": "bulk_skip",
        "bulk_skip": "bulk_skip",
        "q": "quit",
        "quit": "quit",
    }
    default_key = {"migrate": "m", "reinstall": "r", "skip": "s", "review": "l"}.get(
        default, "l"
    )
    while True:
        raw = input(f"Choice [{default_key}]: ").strip().lower()
        if not raw:
            return mapping.get(default_key, "later")
        if raw in mapping:
            return mapping[raw]
        print("Invalid choice. Use m / r / s / l / a / B / q.")


def decision_to_folder_results(decisions_data: dict) -> list[dict]:
    results: list[dict] = []
    for _comp_id, entry in decisions_data.get("decisions", {}).items():
        decision = entry.get("decision")
        if not decision or decision == "quit":
            continue
        category = DECISION_TO_CATEGORY.get(decision, "uncertain")
        analysis = entry.get("analysis") or {}
        note_en = analysis.get("migration_guidance_en") or entry.get("note_en") or decision
        note_hu = analysis.get("migration_guidance_hu") or entry.get("note_hu") or decision
        for folder in entry.get("related_folders") or []:
            results.append(
                {
                    **folder,
                    "category": category,
                    "confidence": analysis.get("confidence", 0.8 if decision != "later" else 0.5),
                    "reason_en": f"[{decision}] {note_en}",
                    "reason_hu": f"[{decision}] {note_hu}",
                    "interactive_decision": decision,
                    "component_id": entry.get("component_id"),
                    "component_name": entry.get("component_name"),
                }
            )
        if not entry.get("related_folders"):
            for path in entry.get("paths") or []:
                results.append(
                    {
                        "path": path,
                        "size_human": entry.get("total_size_human", "?"),
                        "category": category,
                        "confidence": analysis.get("confidence", 0.5),
                        "reason_en": f"[{decision}] {note_en}",
                        "reason_hu": f"[{decision}] {note_hu}",
                        "interactive_decision": decision,
                        "component_id": entry.get("component_id"),
                        "component_name": entry.get("component_name"),
                    }
                )
    return results


def run_interactive_session(
    *,
    inventory_dir: Path,
    decisions_path: Path,
    project: str,
    location: str,
    model: str,
    fallback: bool = False,
    skip_gcp_setup: bool = False,
    resume: bool = True,
    min_size_mb: int = 100,
) -> dict:
    from gcp_setup import ensure_gcp_ready

    inventory_dir = Path(inventory_dir)
    if not fallback:
        if not project:
            print(t("en", "project_required"), file=sys.stderr)
            sys.exit(1)
        if not skip_gcp_setup:
            ensure_gcp_ready(project)

    all_components = discover_components(inventory_dir)
    if not all_components:
        print("ERROR: No components discovered. Run collector phase first.", file=sys.stderr)
        sys.exit(1)

    min_size_bytes = min_size_mb * 1024 * 1024
    components = consolidate_for_interactive(all_components, min_size_bytes=min_size_bytes)
    if not components:
        print("ERROR: No reviewable components after filtering.", file=sys.stderr)
        sys.exit(1)

    full_summary = discovery_summary(all_components)
    review_summary = discovery_summary(components)
    store = load_decisions(decisions_path) if resume else {"decisions": {}, "meta": {}}
    store.setdefault("decisions", {})
    store["meta"] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "interactive",
        "model": model if not fallback else None,
        "project": project if not fallback else None,
        "min_size_mb": min_size_mb,
        "discovery_full": full_summary,
        "discovery_review": review_summary,
    }

    flat: list[tuple[str, dict]] = []
    for group_title, items in group_components(components):
        for comp in items:
            flat.append((group_title, comp))

    total = len(flat)
    print("Interactive migration review")
    print(
        f"  Review queue: {total} items "
        f"(from {full_summary['total_components']} discovered; "
        f"profiled folders ≥ {min_size_mb} MB or sensitive)"
    )
    print(
        f"  Focus: main apps, Homebrew casks/key formulae, key VS Code/Cursor extensions"
    )
    print(f"  Combined size (may overlap): {review_summary['total_size_human']}")
    print("Decisions saved after each item. [B] bulk-skips the rest of the current section.")
    print("Press Ctrl+C anytime to keep progress.\n")

    idx = 0
    skip_sections: set[str] = set()
    try:
        for group_title, component in flat:
            if group_title in skip_sections:
                continue

            idx += 1
            comp_id = component["id"]
            existing = store["decisions"].get(comp_id)
            if existing and existing.get("decision") in ("migrate", "reinstall", "skip", "later"):
                print(f"[{idx}/{total}] SKIP (already decided: {existing['decision']}): {component['name']}")
                continue

            print_header(f"{group_title}: {component['name']}", idx, total)
            print_component_summary(component)

            analysis = None
            if fallback:
                analysis = dict(FALLBACK_ANALYSIS)
            else:
                print("\nAnalyzing with Agent Platform...")
                try:
                    analysis = analyze_component_llm(component, project, location, model)
                except Exception as exc:
                    print(f"WARNING: AI analysis failed: {exc}", file=sys.stderr)
                    analysis = dict(FALLBACK_ANALYSIS)

            while True:
                print_analysis(analysis)
                default = analysis.get("default_recommendation", "review")
                if default not in DECISION_TO_CATEGORY and default != "review":
                    default = "later"
                if default == "review":
                    default = "later"

                choice = prompt_decision(default=default)
                if choice == "ask":
                    if fallback:
                        print("Fallback mode — cannot refresh AI analysis.")
                        continue
                    print("\nRefreshing AI analysis...")
                    try:
                        analysis = analyze_component_llm(component, project, location, model)
                    except Exception as exc:
                        print(f"WARNING: {exc}", file=sys.stderr)
                    continue
                if choice == "bulk_skip":
                    skip_sections.add(group_title)
                    store["decisions"][comp_id] = {
                        "component_id": comp_id,
                        "component_name": component.get("name"),
                        "type": component.get("type"),
                        "source": component.get("source"),
                        "decision": "skip",
                        "analysis": analysis,
                        "paths": component.get("paths"),
                        "related_paths": component.get("related_paths"),
                        "related_folders": component.get("related_folders"),
                        "total_size_human": component.get("total_size_human"),
                        "profile": component.get("profile"),
                        "decided_at": datetime.now(timezone.utc).isoformat(),
                        "bulk_section": group_title,
                    }
                    save_decisions(decisions_path, store)
                    print(f"Bulk skip enabled for section: {group_title}")
                    break

                if choice == "quit":
                    save_decisions(decisions_path, store)
                    print(f"\nSaved progress: {decisions_path}")
                    return store

                store["decisions"][comp_id] = {
                    "component_id": comp_id,
                    "component_name": component.get("name"),
                    "type": component.get("type"),
                    "source": component.get("source"),
                    "decision": choice,
                    "analysis": analysis,
                    "paths": component.get("paths"),
                    "related_paths": component.get("related_paths"),
                    "related_folders": component.get("related_folders"),
                    "total_size_human": component.get("total_size_human"),
                    "profile": component.get("profile"),
                    "decided_at": datetime.now(timezone.utc).isoformat(),
                }
                save_decisions(decisions_path, store)
                print(f"Saved: {choice} -> {comp_id}")
                break

    except KeyboardInterrupt:
        save_decisions(decisions_path, store)
        print(f"\n\nInterrupted — progress saved: {decisions_path}")
        return store

    save_decisions(decisions_path, store)
    print(f"\nInteractive review complete. Decisions: {decisions_path}")
    return store
