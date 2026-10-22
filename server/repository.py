"""Repositório de enquetes em memória (RNF03).

Não há estado global: cada create_app() recebe a sua instância.
"""
from __future__ import annotations

import threading

from server.errors import PollNotFound
from server.models import Poll


class PollRepository:
    def __init__(self) -> None:
        self._polls: dict[int, Poll] = {}
        self._last_id = 0
        self._lock = threading.Lock()

    def next_id(self) -> int:
        """Reserva e devolve o próximo id (seguro entre threads)."""
        with self._lock:
            self._last_id += 1
            return self._last_id

    def add(self, poll: Poll) -> None:
        with self._lock:
            self._polls[poll.id] = poll

    def get(self, poll_id: int) -> Poll:
        with self._lock:
            poll = self._polls.get(poll_id)
        if poll is None:
            raise PollNotFound(poll_id)
        return poll

    def list(self) -> list[Poll]:
        with self._lock:
            return sorted(self._polls.values(), key=lambda p: p.id)
