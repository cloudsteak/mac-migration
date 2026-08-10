"""English console + bilingual report message catalog for analyzer."""

from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "adc_missing": (
            "ERROR: Application Default Credentials (ADC) not available.\n"
            "Or use --fallback for rule-based analysis without Agent Platform."
        ),
        "project_required": "ERROR: GCP project ID required (--project).",
        "input_missing": "ERROR: input file not found: {path}\nRun collector phase first.",
        "folders_loaded": "Loaded {count} folders.",
        "folders_filtered": "{count} folders remain after {min_mb} MB size filter.",
        "llm_batch": "LLM call {current}/{total} ({batch_size} folders)...",
        "retry_rate_limit": "Rate limited, retry {attempt}/{max_attempts} in {delay}s...",
        "retry_parse": "Invalid JSON from model, retry {attempt}/{max_attempts}...",
        "fallback_mode": "Running rule-based analysis (no Agent Platform).",
        "done_md": "Done: {path}",
        "done_json": "Done: {path}",
        "report_lang_link_en": "> **Language:** English | [Magyar]({other})",
        "report_lang_link_hu": "> **Nyelv:** [English]({other}) | Magyar",
        "report_title": "# Migration — folder categorization (LLM-based)",
        "report_intro": "Review each row — these are suggestions, not automatic decisions.",
        "report_table_header": "| Category | Path | Size | Confidence | Reason |",
        "report_table_sep": "|---|---|---|---|---|",
        "parse_error_reason": "LLM response parse error — manual review required.",
        "category_app_data": "app_data",
        "category_user_custom": "user_custom",
        "category_cache_or_temp": "cache_or_temp",
        "category_uncertain": "uncertain",
        "gcp_check_deps": "==> Checking Python dependencies...",
        "gcp_check_deps_ok": "==> Python dependencies OK.",
        "gcp_deps_missing": "ERROR: google-auth not installed. Run: pip install -r analyzer/requirements.txt",
        "gcp_check_project_ok": "==> GCP project: {project}",
        "gcp_check_adc": "==> Checking Application Default Credentials (ADC)...",
        "gcp_check_adc_ok": "==> Application Default Credentials OK.",
        "gcp_adc_missing": (
            "ERROR: Application Default Credentials (ADC) not configured.\n"
            "One-time setup (outside this tool): run\n"
            "  gcloud auth application-default login\n"
            "No API keys or JSON key files are supported."
        ),
        "gcp_adc_json_forbidden": (
            "ERROR: GOOGLE_APPLICATION_CREDENTIALS / JSON key files are not allowed.\n"
            "Use Application Default Credentials only:\n"
            "  gcloud auth application-default login"
        ),
        "gcp_adc_invalid": "ERROR: ADC invalid or expired: {error}",
        "gcp_enable_api": "==> Enabling {api} for project {project}...",
        "gcp_api_already_enabled": "==> API already enabled: {api}",
        "gcp_api_enabled": "==> API enabled: {api}",
        "gcp_enabling_service_usage": "==> Enabling serviceusage.googleapis.com (required to enable other APIs)...",
        "gcp_enable_failed": "ERROR: failed to enable API (HTTP {code}): {detail}",
    },
    "hu": {
        "adc_missing": (
            "HIBA: Application Default Credentials (ADC) nem elérhető.\n"
            "Vagy használd a --fallback kapcsolót Agent Platform nélkül."
        ),
        "project_required": "HIBA: GCP project ID kötelező (--project).",
        "input_missing": "HIBA: nem található a bemeneti fájl: {path}\nFuttasd előbb a collector fázist.",
        "folders_loaded": "==> {count} mappa betöltve.",
        "folders_filtered": "==> {count} mappa marad a {min_mb} MB méretszűrés után.",
        "llm_batch": "==> LLM hívás {current}/{total} ({batch_size} mappa)...",
        "retry_rate_limit": "Rate limit — újrapróbálkozás {attempt}/{max_attempts}, {delay}s múlva...",
        "retry_parse": "Érvénytelen JSON a modelltől — újrapróbálkozás {attempt}/{max_attempts}...",
        "fallback_mode": "==> Szabály alapú elemzés (Agent Platform nélkül).",
        "done_md": "==> Kész: {path}",
        "done_json": "==> JSON kimenet: {path}",
        "report_lang_link_en": "> **Language:** English | [Magyar]({other})",
        "report_lang_link_hu": "> **Nyelv:** [English]({other}) | Magyar",
        "report_title": "# Migráció — mappa kategorizálási javaslat (LLM-alapú)",
        "report_intro": "Minden sort te hagysz jóvá — ez javaslat, nem automatikus döntés.",
        "report_table_header": "| Kategória | Útvonal | Méret | Bizalom | Indoklás |",
        "report_table_sep": "|---|---|---|---|---|",
        "parse_error_reason": "LLM válasz parse hiba — kézi review szükséges.",
        "category_app_data": "app_data",
        "category_user_custom": "user_custom",
        "category_cache_or_temp": "cache_or_temp",
        "category_uncertain": "uncertain",
        "gcp_check_deps": "==> Python függőségek ellenőrzése...",
        "gcp_check_deps_ok": "==> Python függőségek rendben.",
        "gcp_deps_missing": "HIBA: google-auth nincs telepítve. Futtasd: pip install -r analyzer/requirements.txt",
        "gcp_check_project_ok": "==> GCP projekt: {project}",
        "gcp_check_adc": "==> Application Default Credentials (ADC) ellenőrzése...",
        "gcp_check_adc_ok": "==> Application Default Credentials rendben.",
        "gcp_adc_missing": (
            "HIBA: Application Default Credentials (ADC) nincs beállítva.\n"
            "Egyszeri beállítás (a toolon kívül):\n"
            "  gcloud auth application-default login\n"
            "API kulcs és JSON kulcsfájl használata nem engedélyezett."
        ),
        "gcp_adc_json_forbidden": (
            "HIBA: GOOGLE_APPLICATION_CREDENTIALS / JSON kulcsfájl nem engedélyezett.\n"
            "Csak Application Default Credentials:\n"
            "  gcloud auth application-default login"
        ),
        "gcp_adc_invalid": "HIBA: ADC érvénytelen vagy lejárt: {error}",
        "gcp_enable_api": "==> {api} engedélyezése a {project} projektben...",
        "gcp_api_already_enabled": "==> API már engedélyezve: {api}",
        "gcp_api_enabled": "==> API engedélyezve: {api}",
        "gcp_enabling_service_usage": "==> serviceusage.googleapis.com engedélyezése (más API-khoz szükséges)...",
        "gcp_enable_failed": "HIBA: API engedélyezés sikertelen (HTTP {code}): {detail}",
    },
}

PROMPT_BILINGUAL = """We are planning a macOS machine migration. The folder list below is JSON
with profiled directories (path, size, file count, dominant extensions, last modified).

For each folder, decide its category and justify in BOTH English and Hungarian (max 1 sentence each):

- app_data: factory/generated data tied to an installed app (usually restored on reinstall).
- user_custom: unique user-created content (samples, exports, projects) that MUST be copied.
- cache_or_temp: clear cache/temp/log data, safe to skip.
- uncertain: cannot decide confidently — manual review needed.

Reply with ONLY a JSON array, one object per input folder:
[{{"path": "...", "category": "...", "confidence": 0.0-1.0, "reason_en": "...", "reason_hu": "..."}}]

Folders:
{folders_json}"""


def get_prompt(_lang: str) -> str:
    return PROMPT_BILINGUAL

def get_messages(lang: str) -> dict[str, str]:
    return MESSAGES.get(lang, MESSAGES["en"])


def t(lang: str, key: str, **kwargs: str | int) -> str:
    msg = get_messages(lang)[key]
    return msg.format(**kwargs) if kwargs else msg
