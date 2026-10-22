"""Acesso HTTP aos endpoints do servidor. Não depende de Qt.

Todo erro (conexão, timeout ou resposta 4xx/5xx) vira ApiError com uma
mensagem pronta para exibir ao usuário (CA22).
"""
from __future__ import annotations

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:5050"
DEFAULT_TIMEOUT = 5  # segundos


class ApiError(Exception):
    """status é None quando o servidor não pôde ser alcançado."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status


class ApiClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        # Sem sessão injetada, cada chamada usa requests.request (nova conexão),
        # o que é seguro para chamadas vindas de várias threads do Qt.
        self._http = session if session is not None else requests
        self._timeout = timeout

    # ---- núcleo ----
    def _request(self, method: str, path: str, json: dict | None = None):
        url = f"{self.base_url}{path}"
        try:
            response = self._http.request(method, url, json=json, timeout=self._timeout)
        except requests.RequestException:
            raise ApiError(
                f"Não foi possível conectar ao servidor em {self.base_url}. "
                "Verifique se ele está em execução."
            ) from None

        try:
            body = response.json()
        except ValueError:
            raise ApiError("Resposta inválida do servidor", response.status_code) from None

        if response.status_code >= 400:
            message = body.get("error") if isinstance(body, dict) else None
            raise ApiError(message or f"Erro {response.status_code}", response.status_code)
        return body

    # ---- endpoints ----
    def list_polls(self) -> list[dict]:
        return self._request("GET", "/polls")

    def create_poll(self, title: str, options: list[str], poll_type: str) -> dict:
        return self._request(
            "POST", "/polls", {"title": title, "options": options, "type": poll_type}
        )

    def get_poll(self, poll_id: int) -> dict:
        return self._request("GET", f"/polls/{poll_id}")

    def vote(self, poll_id: int, user: str, options: list[str]) -> dict:
        return self._request(
            "POST", f"/polls/{poll_id}/votes", {"user": user, "options": options}
        )

    def results(self, poll_id: int) -> dict:
        return self._request("GET", f"/polls/{poll_id}/results")

    def close_poll(self, poll_id: int) -> dict:
        return self._request("POST", f"/polls/{poll_id}/close")

    def audit(self, poll_id: int) -> list[dict]:
        return self._request("GET", f"/polls/{poll_id}/audit")
