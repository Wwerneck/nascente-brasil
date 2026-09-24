from __future__ import annotations

import pytest

from dashboard.api_client import ApiClientError, request_json
from dashboard.runtime import (
    DashboardConfigurationError,
    LOCAL_API_URL,
    get_api_url,
    normalize_api_url,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requested_url: str | None = None

    def get(self, url: str, **_kwargs) -> FakeResponse:
        self.requested_url = url
        return self.response


def test_api_url_prefers_environment_and_normalizes_trailing_slash() -> None:
    url = get_api_url(
        {"NASCENTE_API_URL": "https://api.example.com/", "NASCENTE_ENV": "production"},
        {"NASCENTE_API_URL": "https://secret.example.com"},
    )
    assert url == "https://api.example.com"


def test_api_url_supports_streamlit_secrets() -> None:
    assert get_api_url({}, {"NASCENTE_API_URL": "https://api.example.com/base/"}) == (
        "https://api.example.com/base"
    )


def test_api_url_uses_localhost_only_in_explicit_local_mode() -> None:
    assert get_api_url({"NASCENTE_ENV": "local"}) == LOCAL_API_URL
    with pytest.raises(DashboardConfigurationError):
        get_api_url({"NASCENTE_ENV": "production"})
    with pytest.raises(DashboardConfigurationError):
        get_api_url({})


def test_api_url_rejects_credentials_without_exposing_them() -> None:
    with pytest.raises(DashboardConfigurationError) as captured:
        normalize_api_url("https://user:super-secret@example.com")
    assert "super-secret" not in str(captured.value)


def test_api_client_reports_503_without_exposing_response_content() -> None:
    response = FakeResponse(
        503,
        {"status": "unavailable", "database": "unavailable"},
        text="postgresql://user:super-secret@database.example.com/db",
    )
    session = FakeSession(response)
    with pytest.raises(ApiClientError) as captured:
        request_json("https://api.example.com", "/ready", session=session)

    error = captured.value
    assert error.status_code == 503
    assert error.endpoint == "/ready"
    assert "banco analítico" in error.detail
    assert "super-secret" not in str(error)
    assert session.requested_url == "https://api.example.com/ready"
