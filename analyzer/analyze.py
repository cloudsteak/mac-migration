#!/usr/bin/env python3
"""
analyze.py — Phase B: LLM-based folder categorization

Input: ~/migration-inventory/collector-output.json (from collector/02-folder-profiler.sh)
Output: analysis-report.md + analysis-report_HU.md (+ JSON variants)

Auth: Application Default Credentials only (no API keys).
Uses Google Enterprise Agent Platform (Gemini 3.5 Flash Lite) @ global location.

API equivalent (non-streaming; curl example uses :streamGenerateContent):
  MODEL_ID="gemini-3.5-flash-lite"
  PROJECT_ID="your-gcp-project"
  POST https://aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/global/
       publishers/google/models/{MODEL_ID}:generateContent
  Auth: Application Default Credentials (ADC) only — no API keys, no JSON key files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from credentials import CredentialsError, get_access_token
from gcp_setup import ensure_gcp_ready
from i18n import get_prompt, t
from paths import hu_path, report_paths
from rule_based import analyze_folders as rule_based_analyze
from rule_based import reason_for_lang

try:
    from interactive import decision_to_folder_results, run_interactive_session
    from interactive_report import write_interactive_reports
except ImportError:
    run_interactive_session = None  # type: ignore[misc, assignment]
    decision_to_folder_results = None  # type: ignore[misc, assignment]
    write_interactive_reports = None  # type: ignore[misc, assignment]

# Agent Platform — global Gemini 3.5 Flash Lite (override with --model / --location / --project)
MODEL_ID = "gemini-3.5-flash-lite"
AGENT_PLATFORM_LOCATION = "global"
DEFAULT_MODEL = MODEL_ID
DEFAULT_LOCATION = AGENT_PLATFORM_LOCATION
DEFAULT_BATCH_SIZE = 30
MIN_SIZE_BYTES_DEFAULT = 100 * 1024 * 1024
CATEGORIES = {"app_data", "user_custom", "cache_or_temp", "uncertain"}
REPORT_ORDER = {"user_custom": 0, "uncertain": 1, "app_data": 2, "cache_or_temp": 3}

MAX_RETRIES = 5
INITIAL_BACKOFF_SEC = 2.0


def load_collector_output(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("folders", [])


def filter_folders(folders: list[dict], min_size_bytes: int) -> list[dict]:
    return [f for f in folders if f.get("size_bytes", 0) >= min_size_bytes]


def chunk(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def strip_json_fence(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_model_response(raw_text: str, batch: list[dict]) -> list[dict]:
    cleaned = strip_json_fence(raw_text)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, list):
        raise json.JSONDecodeError("Expected JSON array", cleaned, 0)

    by_path = {item.get("path"): item for item in parsed if isinstance(item, dict)}
    err_en = t("en", "parse_error_reason")
    err_hu = t("hu", "parse_error_reason")
    results = []
    for folder in batch:
        path = folder.get("path")
        item = by_path.get(path)
        if not item:
            results.append(
                {
                    "path": path,
                    "category": "uncertain",
                    "confidence": 0.0,
                    "reason_en": err_en,
                    "reason_hu": err_hu,
                }
            )
            continue
        category = item.get("category", "uncertain")
        if category not in CATEGORIES:
            category = "uncertain"
        legacy = str(item.get("reason", ""))
        results.append(
            {
                "path": path,
                "category": category,
                "confidence": float(item.get("confidence", 0.5)),
                "reason_en": str(item.get("reason_en") or legacy or err_en),
                "reason_hu": str(item.get("reason_hu") or legacy or err_hu),
            }
        )
    return results


def uncertain_fallback(batch: list[dict]) -> list[dict]:
    err_en = t("en", "parse_error_reason")
    err_hu = t("hu", "parse_error_reason")
    return [
        {
            "path": f.get("path"),
            "category": "uncertain",
            "confidence": 0.0,
            "reason_en": err_en,
            "reason_hu": err_hu,
        }
        for f in batch
    ]


def get_adc_token() -> str:
    try:
        return get_access_token()
    except CredentialsError:
        return ""
    except Exception:
        return ""


def call_agent_platform_rest(
    folders_batch: list[dict],
    project: str,
    location: str,
    model_name: str,
) -> str:
    import urllib.request

    token = get_adc_token()
    if not token:
        raise RuntimeError("ADC_NOT_CONFIGURED")

    prompt = get_prompt("en").format(
        folders_json=json.dumps(folders_batch, ensure_ascii=False, indent=2)
    )

    url = (
        f"https://aiplatform.googleapis.com/v1/projects/{project}"
        f"/locations/{location}/publishers/google/models/{model_name}:generateContent"
    )

    body = json.dumps(
        {
            "contents": {
                "role": "user",
                "parts": [{"text": prompt}],
            },
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Empty response from Agent Platform")

    parts = candidates[0].get("content", {}).get("parts") or []
    texts = [p.get("text", "") for p in parts if p.get("text")]
    if not texts:
        raise RuntimeError("No text in Agent Platform response")
    return "\n".join(texts)


def is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in ("429", "rate", "quota", "resource exhausted", "too many requests")
    )


def call_agent_platform_with_retries(
    folders_batch: list[dict],
    project: str,
    location: str,
    model_name: str,
) -> list[dict]:
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw_text = call_agent_platform_rest(
                folders_batch, project, location, model_name
            )
            return parse_model_response(raw_text, folders_batch)
        except json.JSONDecodeError:
            print(
                t("en", "retry_parse", attempt=attempt, max_attempts=MAX_RETRIES),
                file=sys.stderr,
            )
            last_error = None
        except RuntimeError as exc:
            if str(exc) == "ADC_NOT_CONFIGURED":
                raise
            last_error = exc
            if is_rate_limit_error(exc) and attempt < MAX_RETRIES:
                delay = INITIAL_BACKOFF_SEC * (2 ** (attempt - 1))
                print(
                    t(
                        "en",
                        "retry_rate_limit",
                        attempt=attempt,
                        max_attempts=MAX_RETRIES,
                        delay=int(delay),
                    ),
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            break
        except Exception as exc:
            last_error = exc
            if is_rate_limit_error(exc) and attempt < MAX_RETRIES:
                delay = INITIAL_BACKOFF_SEC * (2 ** (attempt - 1))
                print(
                    t(
                        "en",
                        "retry_rate_limit",
                        attempt=attempt,
                        max_attempts=MAX_RETRIES,
                        delay=int(delay),
                    ),
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            break

    if last_error:
        print(f"WARNING: {last_error}", file=sys.stderr)
    return uncertain_fallback(folders_batch)


def write_markdown_report(
    results: list[dict],
    folders_by_path: dict[str, dict],
    out_path: Path,
    lang: str,
    other_path: Path,
) -> None:
    results_sorted = sorted(
        results, key=lambda r: REPORT_ORDER.get(r.get("category", "uncertain"), 1)
    )

    link_key = "report_lang_link_en" if lang == "en" else "report_lang_link_hu"
    lines = [
        t(lang, link_key, other=other_path.name),
        "",
        t(lang, "report_title"),
        "",
        t(lang, "report_intro"),
        "",
        t(lang, "report_table_header"),
        t(lang, "report_table_sep"),
    ]
    for r in results_sorted:
        path = r.get("path", "")
        meta = folders_by_path.get(path, {})
        size = meta.get("size_human", "?")
        reason = reason_for_lang(r, lang)
        lines.append(
            f"| {r.get('category', 'uncertain')} | `{path}` | {size} | "
            f"{r.get('confidence', '?')} | {reason} |"
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_bilingual_reports(
    results: list[dict],
    folders_by_path: dict[str, dict],
    md_base: Path,
    json_base: Path,
    meta_base: dict,
) -> None:
    md_paths = report_paths(md_base)
    json_paths = report_paths(json_base)

    for lang in ("en", "hu"):
        other_md = md_paths["hu"] if lang == "en" else md_paths["en"]
        write_markdown_report(results, folders_by_path, md_paths[lang], lang, other_md)
        write_json_report(
            results,
            folders_by_path,
            json_paths[lang],
            {**meta_base, "lang": lang},
        )


def write_json_report(
    results: list[dict],
    folders_by_path: dict[str, dict],
    out_path: Path,
    meta: dict,
) -> None:
    enriched = []
    for r in results:
        path = r.get("path", "")
        folder_meta = folders_by_path.get(path, {})
        enriched.append({**folder_meta, **r})

    payload = {
        **meta,
        "result_count": len(enriched),
        "results": enriched,
    }
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase B — LLM-based folder categorization"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path.home() / "migration-inventory" / "collector-output.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / "migration-inventory" / "analysis-report.md",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path.home() / "migration-inventory" / "analysis-report.json",
    )
    parser.add_argument("--project", required=False, help="GCP project ID (required unless --fallback)")
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="Agent Platform location")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Agent Platform model ID")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--min-size-mb",
        type=int,
        default=MIN_SIZE_BYTES_DEFAULT // (1024 * 1024),
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Interactive review: AI deep-dive per app/dotfolder with migrate/skip prompts",
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=Path.home() / "migration-inventory" / "interactive-decisions.json",
        help="Interactive decisions JSON (save/resume)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore previous interactive decisions and start fresh",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="Rule-based analysis without Agent Platform",
    )
    parser.add_argument(
        "--skip-gcp-setup",
        action="store_true",
        help="Skip prerequisite checks and API enable (ADC must already work)",
    )
    parser.add_argument(
        "--from-decisions",
        action="store_true",
        help="Regenerate analysis report from existing interactive-decisions.json (no LLM, no review)",
    )
    args = parser.parse_args()

    if args.from_decisions:
        if write_interactive_reports is None:
            print("ERROR: interactive report module unavailable.", file=sys.stderr)
            sys.exit(1)
        if not args.decisions.exists():
            print(f"ERROR: decisions file not found: {args.decisions}", file=sys.stderr)
            sys.exit(1)
        store = json.loads(args.decisions.read_text(encoding="utf-8"))
        inventory_dir = args.input.parent
        meta = {
            "generated_by": "analyzer/interactive_report.py",
            "mode": "interactive_report",
            "decisions_file": str(args.decisions),
        }
        write_interactive_reports(store, inventory_dir, args.output, args.output_json, meta)
        md_paths = report_paths(args.output)
        json_paths = report_paths(args.output_json)
        print(t("en", "done_md", path=md_paths["en"]))
        print(t("en", "done_md", path=md_paths["hu"]))
        print(t("en", "done_json", path=json_paths["en"]))
        print(t("en", "done_json", path=json_paths["hu"]))
        return

    if args.interactive:
        if run_interactive_session is None or write_interactive_reports is None:
            print("ERROR: interactive module unavailable.", file=sys.stderr)
            sys.exit(1)
        if args.fallback and not args.project:
            pass
        elif not args.fallback and not args.project:
            print(t("en", "project_required"), file=sys.stderr)
            sys.exit(1)

        inventory_dir = args.input.parent
        store = run_interactive_session(
            inventory_dir=inventory_dir,
            decisions_path=args.decisions,
            project=args.project or "",
            location=args.location,
            model=args.model,
            fallback=args.fallback,
            skip_gcp_setup=args.skip_gcp_setup,
            resume=not args.no_resume,
            min_size_mb=args.min_size_mb,
        )
        meta = {
            "generated_by": "analyzer/interactive_report.py",
            "mode": "interactive_fallback" if args.fallback else "interactive",
            "model": args.model if not args.fallback else None,
            "project": args.project if not args.fallback else None,
            "location": args.location if not args.fallback else None,
            "decisions_file": str(args.decisions),
        }
        write_interactive_reports(store, inventory_dir, args.output, args.output_json, meta)
        md_paths = report_paths(args.output)
        json_paths = report_paths(args.output_json)
        print(t("en", "done_md", path=md_paths["en"]))
        print(t("en", "done_md", path=md_paths["hu"]))
        print(t("en", "done_json", path=json_paths["en"]))
        print(t("en", "done_json", path=json_paths["hu"]))
        print(f"Decisions: {args.decisions}")
        return

    if not args.fallback and not args.project:
        print(t("en", "project_required"), file=sys.stderr)
        sys.exit(1)

    if not args.input.exists():
        print(t("en", "input_missing", path=args.input), file=sys.stderr)
        sys.exit(1)

    folders = load_collector_output(args.input)
    print(t("en", "folders_loaded", count=len(folders)))

    min_size_bytes = args.min_size_mb * 1024 * 1024
    filtered = filter_folders(folders, min_size_bytes)
    print(t("en", "folders_filtered", count=len(filtered), min_mb=args.min_size_mb))

    folders_by_path = {f["path"]: f for f in filtered}
    all_results: list[dict] = []

    if args.fallback:
        print(t("en", "fallback_mode"))
        all_results = rule_based_analyze(filtered)
    else:
        if not args.skip_gcp_setup:
            ensure_gcp_ready(args.project)
        elif not get_adc_token():
            print(t("en", "adc_missing"), file=sys.stderr)
            sys.exit(1)

        batches = list(chunk(filtered, args.batch_size))
        total = len(batches)
        for i, batch in enumerate(batches, start=1):
            print(
                t(
                    "en",
                    "llm_batch",
                    current=i,
                    total=total,
                    batch_size=len(batch),
                )
            )
            results = call_agent_platform_with_retries(
                batch,
                args.project,
                args.location,
                args.model,
            )
            all_results.extend(results)

    meta = {
        "generated_by": "analyzer/analyze.py",
        "mode": "fallback" if args.fallback else "agent_platform",
        "model": args.model if not args.fallback else None,
        "project": args.project if not args.fallback else None,
        "location": args.location if not args.fallback else None,
    }

    write_bilingual_reports(
        all_results, folders_by_path, args.output, args.output_json, meta
    )

    md_paths = report_paths(args.output)
    json_paths = report_paths(args.output_json)
    print(t("en", "done_md", path=md_paths["en"]))
    print(t("en", "done_md", path=md_paths["hu"]))
    print(t("en", "done_json", path=json_paths["en"]))
    print(t("en", "done_json", path=json_paths["hu"]))


if __name__ == "__main__":
    main()
