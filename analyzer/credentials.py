"""Application Default Credentials (ADC) only — no API keys, no JSON key files."""

from __future__ import annotations

import os
import sys

CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
SCOPES = [CLOUD_PLATFORM_SCOPE]


class CredentialsError(Exception):
    pass


def _reject_disallowed_credential_sources() -> None:
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip():
        raise CredentialsError("GOOGLE_APPLICATION_CREDENTIALS")


def load_credentials():
    """Load ADC via google.auth.default() — user OAuth / metadata only."""
    _reject_disallowed_credential_sources()

    import google.auth
    import google.auth.transport.requests

    credentials, _ = google.auth.default(scopes=SCOPES)
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials


def get_access_token() -> str:
    try:
        credentials = load_credentials()
    except CredentialsError:
        raise
    except Exception as exc:
        raise CredentialsError(str(exc)) from exc
    return credentials.token or ""
