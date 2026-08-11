"""GCP prerequisite checks and API enablement — ADC only, no gcloud CLI subprocess."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from credentials import CredentialsError, get_access_token, load_credentials
from i18n import t

VERTEX_AI_API = "aiplatform.googleapis.com"
SERVICE_USAGE_API = "serviceusage.googleapis.com"


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _request_json(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_auth_headers(token), method=method)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def check_prerequisites(project: str) -> None:
    print(t("en", "gcp_check_deps"))
    try:
        import google.auth  # noqa: F401
    except ImportError:
        print(t("en", "gcp_deps_missing"), file=sys.stderr)
        sys.exit(1)
    print(t("en", "gcp_check_deps_ok"))

    if not project.strip():
        print(t("en", "project_required"), file=sys.stderr)
        sys.exit(1)
    print(t("en", "gcp_check_project_ok", project=project))

    print(t("en", "gcp_check_adc"))
    try:
        load_credentials()
    except CredentialsError as exc:
        if str(exc) == "GOOGLE_APPLICATION_CREDENTIALS":
            print(t("en", "gcp_adc_json_forbidden"), file=sys.stderr)
        else:
            print(t("en", "gcp_adc_missing"), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(t("en", "gcp_adc_invalid", error=exc), file=sys.stderr)
        sys.exit(1)
    print(t("en", "gcp_check_adc_ok"))


def _service_state(project: str, service: str, token: str) -> str | None:
    url = (
        f"https://serviceusage.googleapis.com/v1/projects/{project}"
        f"/services/{service}"
    )
    try:
        payload = _request_json("GET", url, token)
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):
            return None
        raise
    return payload.get("state")


def _enable_service(project: str, service: str, token: str) -> None:
    url = (
        f"https://serviceusage.googleapis.com/v1/projects/{project}"
        f"/services/{service}:enable"
    )
    try:
        _request_json("POST", url, token, body={})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 409 or "already enabled" in body.lower():
            return
        raise


def ensure_api_enabled(project: str) -> None:
    token = get_access_token()

    print(t("en", "gcp_enable_api", project=project, api=VERTEX_AI_API))
    state = _service_state(project, VERTEX_AI_API, token)
    if state == "ENABLED":
        print(t("en", "gcp_api_already_enabled", api=VERTEX_AI_API))
        return

    try:
        _enable_service(project, VERTEX_AI_API, token)
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            try:
                usage_state = _service_state(project, SERVICE_USAGE_API, token)
                if usage_state != "ENABLED":
                    print(t("en", "gcp_enabling_service_usage"))
                    _enable_service(project, SERVICE_USAGE_API, token)
                    token = get_access_token()
                    _enable_service(project, VERTEX_AI_API, token)
                else:
                    raise
            except urllib.error.HTTPError:
                print(t("en", "gcp_enable_failed", code=exc.code, detail=exc.reason), file=sys.stderr)
                sys.exit(1)
        else:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            print(t("en", "gcp_enable_failed", code=exc.code, detail=detail), file=sys.stderr)
            sys.exit(1)

    print(t("en", "gcp_api_enabled", api=VERTEX_AI_API))


def ensure_gcp_ready(project: str) -> None:
    """Prerequisite checks + enable Vertex AI API (ADC only, non-interactive)."""
    check_prerequisites(project)
    ensure_api_enabled(project)
