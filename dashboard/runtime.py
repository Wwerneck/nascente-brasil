"""Runtime configuration for the Streamlit dashboard."""

from __future__ import annotations

from collections.abc import Mapping
import os
from urllib.parse import urlsplit, urlunsplit


LOCAL_ENVIRONMENTS = {"local", "development", "dev", "test"}
LOCAL_API_URL = "http://127.0.0.1:8000"


class DashboardConfigurationError(RuntimeError):
    """Raised when the public API endpoint is missing or unsafe."""


def normalize_api_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DashboardConfigurationError("NASCENTE_API_URL must be a valid HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise DashboardConfigurationError("NASCENTE_API_URL contains unsupported components.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def get_api_url(
    environ: Mapping[str, str] | None = None,
    secrets: Mapping[str, object] | None = None,
) -> str:
    values = os.environ if environ is None else environ
    configured = values.get("NASCENTE_API_URL")
    if not configured and secrets:
        secret_value = secrets.get("NASCENTE_API_URL")
        configured = str(secret_value) if secret_value else None
    if configured:
        return normalize_api_url(configured)

    environment = values.get("NASCENTE_ENV", "").strip().lower()
    if environment in LOCAL_ENVIRONMENTS:
        return LOCAL_API_URL

    raise DashboardConfigurationError(
        "NASCENTE_API_URL is required outside an explicit local environment."
    )
