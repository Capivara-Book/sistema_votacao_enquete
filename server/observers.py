"""Observer (padrão comportamental).

O Poll (Subject) notifica cada VoteObserver anexado a cada voto aceito.
Poll só conhece a interface VoteObserver, nunca as classes concretas.

Os observers são compartilhados entre enquetes (um ResultsCounter e um
AuditLog por aplicação) e podem receber votos de enquetes diferentes ao
mesmo tempo, por isso cada um tem o seu próprio lock.
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.models import Poll, Vote


class VoteObserver(ABC):
    @abstractmethod
    def update(self, poll: Poll, vote: Vote) -> None:
        """Chamado pela enquete a cada voto aceito."""


class ResultsCounter(VoteObserver):
    """Mantém a contagem de votos por opção (RF11)."""

    def __init__(self) -> None:
        self._counts: dict[int, dict[str, int]] = {}
        self._ballots: dict[int, int] = {}
        self._lock = threading.Lock()

    def update(self, poll: Poll, vote: Vote) -> None:
        with self._lock:
            counts = self._counts.setdefault(poll.id, {})
            for option in vote.options:
                counts[option] = counts.get(option, 0) + 1
            self._ballots[poll.id] = self._ballots.get(poll.id, 0) + 1

    def results(self, poll: Poll) -> dict:
        with self._lock:
            counts = self._counts.get(poll.id, {})
            return {
                "poll_id": poll.id,
                "status": poll.status.value,
                "total_votes": self._ballots.get(poll.id, 0),
                "results": {option: counts.get(option, 0) for option in poll.options},
            }


class AuditLog(VoteObserver):
    """Registra cada voto aceito (RF12). Votos rejeitados nunca chegam aqui."""

    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._lock = threading.Lock()

    def update(self, poll: Poll, vote: Vote) -> None:
        entry = {
            "poll_id": poll.id,
            "user": vote.user,
            "options": list(vote.options),
            "timestamp": vote.timestamp.isoformat(),
        }
        with self._lock:
            self._entries.append(entry)

    def entries(self, poll_id: int) -> list[dict]:
        with self._lock:
            return [dict(e) for e in self._entries if e["poll_id"] == poll_id]
