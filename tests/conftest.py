"""Fixtures compartilhadas.

- Qt em modo offscreen: os testes de cliente rodam sem janela e sem display.
- live_server: o servidor Flask real em uma thread, em porta livre, para os
  testes de ApiClient e das telas. Nenhum servidor externo é necessário (CA24).
- Cada teste recebe um repositório novo (função), então não há estado compartilhado.
"""
import os
import socket
import threading
from collections import namedtuple

# Precisa vir antes de qualquer import do PySide6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from werkzeug.serving import make_server

from client.api_client import ApiClient
from server.app import create_app
from server.models import Poll
from server.observers import VoteObserver
from server.repository import PollRepository
from server.service import PollService


class LiveServer:
    def __init__(self, app):
        self._server = make_server("127.0.0.1", 0, app, threaded=True)  # porta 0 = livre
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.05},  # desligamento rápido (padrão: 0,5 s)
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


# ---------------------------------------------------------------- servidor e dados
@pytest.fixture
def repository() -> PollRepository:
    """Repositório em memória vazio, novo a cada teste (substitui banco de dados)."""
    return PollRepository()


@pytest.fixture
def service(repository) -> PollService:
    """Serviço isolado, para testes sem HTTP."""
    return PollService(repository)


@pytest.fixture
def app(repository):
    app = create_app(repository)
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    """Cliente de teste do Flask (sem rede)."""
    return app.test_client()


@pytest.fixture
def live_server(app):
    server = LiveServer(app)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def api(live_server) -> ApiClient:
    """ApiClient apontando para o servidor real em thread."""
    return ApiClient(live_server.url)


# ---------------------------------------------------------------- usuários
Users = namedtuple("Users", "ana bia caio")


@pytest.fixture
def users() -> Users:
    """Três eleitores distintos. O sistema não tem papéis: o usuário é só um nome (RN01)."""
    return Users("Ana", "Bia", "Caio")


# ---------------------------------------------------------------- enquetes prontas via HTTP
@pytest.fixture
def new_poll(client):
    """Cria enquete pela API (test client) e devolve o JSON. Padrão: 'Café?' de escolha única."""

    def _create(title="Café?", options=("Sim", "Não"), poll_type="single") -> dict:
        response = client.post(
            "/polls", json={"title": title, "options": list(options), "type": poll_type}
        )
        assert response.status_code == 201, response.get_json()
        return response.get_json()

    return _create


# ---------------------------------------------------------------- espiões dos padrões
class SpyObserver(VoteObserver):
    """Observer de teste: guarda cada notificação recebida."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def update(self, poll, vote) -> None:
        self.calls.append((poll.id, vote.user, vote.options))


@pytest.fixture
def spy_observer() -> SpyObserver:
    return SpyObserver()


@pytest.fixture
def poll_vote_calls(monkeypatch) -> list:
    """Registra toda chamada a Poll.vote() (o objeto real atrás do Proxy).

    Lista vazia = o Proxy bloqueou sem tocar no Poll real.
    """
    calls: list[tuple] = []
    original = Poll.vote

    def recording(self, user, options):
        calls.append((self.id, user, tuple(options)))
        return original(self, user, options)

    monkeypatch.setattr(Poll, "vote", recording)
    return calls


# ---------------------------------------------------------------- rede e Qt
@pytest.fixture
def closed_server_url() -> str:
    """URL local em que ninguém escuta (conexão recusada), para testar falha de rede."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


@pytest.fixture
def wait_until_idle(qtbot):
    """Espera a janela terminar todas as chamadas à API (sem sleep)."""

    def _wait(window) -> None:
        qtbot.waitUntil(lambda: not window.is_busy(), timeout=5000)

    return _wait


@pytest.fixture
def window_opener(qtbot, api, wait_until_idle):
    """Abre a MainWindow (servidor real em thread por padrão) já com a lista carregada."""
    from client.views.main_window import MainWindow  # import tardio: só testes de tela precisam de Qt

    def _open(api_client=None):
        window = MainWindow(api_client or api)
        qtbot.addWidget(window)
        wait_until_idle(window)
        return window

    return _open
