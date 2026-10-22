"""ApiClient: contra o servidor real (thread) e contra sessões falsas para os cenários de falha."""
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest
import requests

from client.api_client import DEFAULT_BASE_URL, ApiClient, ApiError


# ------------------------------------------------------------------ helpers
def closed_port_url() -> str:
    """URL de uma porta local em que ninguém escuta (conexão recusada)."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, invalid_json=False):
        self.status_code = status_code
        self.payload = payload
        self.invalid_json = invalid_json

    def json(self):
        if self.invalid_json:
            raise ValueError("sem JSON")
        return self.payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def request(self, method, url, json=None, timeout=None):
        self.calls.append((method, url, json, timeout))
        if self.error is not None:
            raise self.error
        return self.response


# ------------------------------------------------------------------ montagem das requisições
def test_default_base_url():
    assert DEFAULT_BASE_URL == "http://127.0.0.1:5050"
    assert ApiClient().base_url == DEFAULT_BASE_URL


def test_trailing_slash_of_base_url_is_removed():
    session = FakeSession(FakeResponse(payload=[]))
    api = ApiClient("http://servidor:5050/", session=session)
    api.list_polls()
    assert api.base_url == "http://servidor:5050"
    assert session.calls[0][1] == "http://servidor:5050/polls"


def test_requests_use_expected_method_url_body_and_timeout():
    session = FakeSession(FakeResponse(payload={}))
    api = ApiClient("http://x", session=session, timeout=3)

    api.list_polls()
    api.create_poll("Café?", ["Sim", "Não"], "single")
    api.get_poll(7)
    api.vote(7, "Ana", ["Sim"])
    api.results(7)
    api.close_poll(7)
    api.audit(7)

    assert session.calls == [
        ("GET", "http://x/polls", None, 3),
        ("POST", "http://x/polls", {"title": "Café?", "options": ["Sim", "Não"], "type": "single"}, 3),
        ("GET", "http://x/polls/7", None, 3),
        ("POST", "http://x/polls/7/votes", {"user": "Ana", "options": ["Sim"]}, 3),
        ("GET", "http://x/polls/7/results", None, 3),
        ("POST", "http://x/polls/7/close", None, 3),
        ("GET", "http://x/polls/7/audit", None, 3),
    ]


def test_default_timeout_is_five_seconds():
    session = FakeSession(FakeResponse(payload=[]))
    ApiClient("http://x", session=session).list_polls()
    assert session.calls[0][3] == 5


def test_parsed_json_is_returned_as_is():
    payload = [{"id": 1}]
    api = ApiClient("http://x", session=FakeSession(FakeResponse(payload=payload)))
    assert api.list_polls() == payload


# ------------------------------------------------------------------ contra o servidor real
def test_list_is_empty_at_start(api):
    assert api.list_polls() == []


def test_create_and_get_poll(api):
    created = api.create_poll("Café?", ["Sim", "Não"], "single")
    assert created == {
        "id": 1,
        "title": "Café?",
        "type": "single",
        "status": "open",
        "options": ["Sim", "Não"],
    }
    assert api.get_poll(1) == created
    assert api.list_polls() == [created]


def test_vote_and_results(api):
    api.create_poll("Sabores?", ["Uva", "Maçã", "Pera"], "multiple")
    assert api.vote(1, "Ana", ["Uva", "Pera"]) == {
        "poll_id": 1,
        "user": "Ana",
        "options": ["Uva", "Pera"],
    }
    assert api.results(1) == {
        "poll_id": 1,
        "status": "open",
        "total_votes": 1,
        "results": {"Uva": 1, "Maçã": 0, "Pera": 1},
    }


def test_close_poll_and_audit(api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    api.vote(1, "Ana", ["Sim"])
    assert api.close_poll(1)["status"] == "closed"
    entries = api.audit(1)
    assert [(e["user"], e["options"]) for e in entries] == [("Ana", ["Sim"])]


def test_full_flow_through_the_client(api):
    api.create_poll("Almoço?", ["Pizza", "Sushi"], "single")
    api.vote(1, "Ana", ["Pizza"])
    api.vote(1, "Bia", ["Pizza"])
    api.vote(1, "Caio", ["Sushi"])
    api.close_poll(1)
    results = api.results(1)
    assert results["status"] == "closed"
    assert results["results"] == {"Pizza": 2, "Sushi": 1}
    assert results["total_votes"] == 3


# ------------------------------------------------------------------ erros da API viram ApiError
@pytest.mark.parametrize(
    "call, status, message",
    [
        (lambda api: api.get_poll(999), 404, "Enquete 999 não encontrada"),
        (lambda api: api.results(999), 404, "Enquete 999 não encontrada"),
        (lambda api: api.create_poll("", ["A", "B"], "single"), 400, "Título é obrigatório"),
        (lambda api: api.create_poll("T", ["A"], "single"), 400, "A enquete deve ter de 2 a 10 opções"),
        (lambda api: api.create_poll("T", ["A", "B"], "x"), 400, "Tipo deve ser 'single' ou 'multiple'"),
    ],
)
def test_api_errors_carry_status_and_server_message(api, call, status, message):
    with pytest.raises(ApiError) as caught:
        call(api)
    assert caught.value.status == status
    assert caught.value.message == message
    assert str(caught.value) == message


def test_vote_errors_map_to_400_409_and_422(api):
    api.create_poll("Café?", ["Sim", "Não"], "single")

    with pytest.raises(ApiError) as empty_user:
        api.vote(1, "", ["Sim"])
    assert (empty_user.value.status, empty_user.value.message) == (400, "Usuário é obrigatório")

    with pytest.raises(ApiError) as bad_choice:
        api.vote(1, "Ana", ["Sim", "Não"])
    assert bad_choice.value.status == 422
    assert "exatamente uma opção" in bad_choice.value.message

    api.vote(1, "Ana", ["Sim"])
    with pytest.raises(ApiError) as duplicate:
        api.vote(1, "Ana", ["Não"])
    assert (duplicate.value.status, duplicate.value.message) == (409, "Usuário já votou nesta enquete")


def test_vote_and_close_on_closed_poll_return_409(api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    api.close_poll(1)

    with pytest.raises(ApiError) as vote_error:
        api.vote(1, "Ana", ["Sim"])
    assert (vote_error.value.status, vote_error.value.message) == (409, "Enquete encerrada")

    with pytest.raises(ApiError) as close_error:
        api.close_poll(1)
    assert (close_error.value.status, close_error.value.message) == (409, "Enquete já está encerrada")


# ------------------------------------------------------------------ servidor inalcançável (CA22)
def test_connection_refused_becomes_friendly_error():
    url = closed_port_url()
    with pytest.raises(ApiError) as caught:
        ApiClient(url, timeout=2).list_polls()
    assert caught.value.status is None
    assert "conectar" in caught.value.message
    assert url in caught.value.message


@pytest.mark.parametrize("error", [requests.Timeout(), requests.ConnectionError(), requests.RequestException()])
def test_network_failures_become_api_error_without_status(error):
    api = ApiClient("http://x", session=FakeSession(error=error))
    with pytest.raises(ApiError) as caught:
        api.vote(1, "Ana", ["Sim"])
    assert caught.value.status is None
    assert "conectar" in caught.value.message


# ------------------------------------------------------------------ respostas inesperadas
def test_invalid_json_on_success_is_reported():
    api = ApiClient("http://x", session=FakeSession(FakeResponse(200, invalid_json=True)))
    with pytest.raises(ApiError) as caught:
        api.list_polls()
    assert (caught.value.status, caught.value.message) == (200, "Resposta inválida do servidor")


def test_html_error_page_is_reported_with_its_status():
    api = ApiClient("http://x", session=FakeSession(FakeResponse(502, invalid_json=True)))
    with pytest.raises(ApiError) as caught:
        api.list_polls()
    assert (caught.value.status, caught.value.message) == (502, "Resposta inválida do servidor")


@pytest.mark.parametrize("status, payload", [(500, {}), (404, ["lista"]), (400, {"error": ""})])
def test_error_without_message_falls_back_to_status(status, payload):
    api = ApiClient("http://x", session=FakeSession(FakeResponse(status, payload)))
    with pytest.raises(ApiError) as caught:
        api.get_poll(1)
    assert caught.value.status == status
    assert caught.value.message == f"Erro {status}"


# ------------------------------------------------------------------ concorrência e independência do Qt
def test_client_is_safe_to_use_from_several_threads(api):
    ids, errors = [], []

    def worker(index):
        try:
            ids.append(api.create_poll(f"Enquete {index}", ["A", "B"], "single")["id"])
        except Exception as err:  # noqa: BLE001
            errors.append(err)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert errors == []
    assert sorted(ids) == list(range(1, 9))


def test_api_client_module_does_not_import_qt():
    root = Path(__file__).resolve().parents[2]
    code = "import sys, client.api_client; sys.exit(1 if 'PySide6' in sys.modules else 0)"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=root, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
