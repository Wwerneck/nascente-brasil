"""Small, testable HTTP client with safe deployment diagnostics."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import socket

import requests


class ApiClientError(RuntimeError):
    def __init__(
        self,
        kind: str,
        detail: str,
        base_url: str,
        endpoint: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.base_url = base_url
        self.endpoint = endpoint
        self.status_code = status_code
        self.attempted_at = datetime.now(timezone.utc)


def _exception_tree(error: BaseException) -> Iterable[BaseException]:
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        for nested in (current.__cause__, current.__context__, *current.args):
            if isinstance(nested, BaseException):
                pending.append(nested)


def request_json(
    base_url: str,
    endpoint: str,
    params: dict[str, str | int] | None = None,
    timeout: float = 20,
    session=requests,
) -> dict:
    url = f"{base_url}{endpoint}"
    try:
        response = session.get(url, params=params or {}, timeout=timeout)
    except requests.Timeout as exc:
        raise ApiClientError("timeout", "A API não respondeu dentro do tempo limite.", base_url, endpoint) from exc
    except requests.ConnectionError as exc:
        errors = tuple(_exception_tree(exc))
        if any(isinstance(item, socket.gaierror) for item in errors):
            detail = "Não foi possível resolver o endereço DNS da API."
            kind = "dns"
        elif any(isinstance(item, ConnectionRefusedError) for item in errors):
            detail = "A conexão com a API foi recusada."
            kind = "connection_refused"
        else:
            detail = "Não foi possível estabelecer conexão com a API."
            kind = "connection"
        raise ApiClientError(kind, detail, base_url, endpoint) from exc
    except requests.RequestException as exc:
        raise ApiClientError("request", "Falha ao consultar a API analítica.", base_url, endpoint) from exc

    if response.status_code >= 400:
        if response.status_code == 404:
            detail = "O endpoint solicitado não foi encontrado na API."
        elif response.status_code == 503:
            detail = "A API está disponível, mas o banco analítico ainda não está pronto."
        elif response.status_code >= 500:
            detail = "A API apresentou uma falha interna."
        else:
            detail = "A API recusou a solicitação."
        raise ApiClientError(
            "http", detail, base_url, endpoint, status_code=response.status_code
        )

    try:
        return response.json()
    except requests.JSONDecodeError as exc:
        raise ApiClientError(
            "invalid_response", "A API retornou uma resposta inválida.", base_url, endpoint
        ) from exc
