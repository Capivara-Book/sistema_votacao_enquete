"""Camada de aplicação: une Factory Method, Proxy e Observer.

- Factory Method: get_creator(tipo) escolhe a fábrica; a fábrica cria a enquete.
- Observer: ResultsCounter e AuditLog são anexados a toda enquete criada.
- Proxy: todo voto passa por VotingProxy; Poll.vote() nunca é chamado aqui.
"""
from __future__ import annotations

from server.factory import get_creator
from server.models import Poll, Vote
from server.observers import AuditLog, ResultsCounter
from server.proxy import VotingProxy
from server.repository import PollRepository


class PollService:
    def __init__(
        self,
        repository: PollRepository,
        results_counter: ResultsCounter | None = None,
        audit_log: AuditLog | None = None,
    ) -> None:
        self._repository = repository
        self._results = results_counter or ResultsCounter()
        self._audit = audit_log or AuditLog()

    def create_poll(self, title: object, options: object, poll_type: object) -> Poll:
        creator = get_creator(poll_type)                       # Factory Method
        poll = creator.create(self._repository.next_id(), title, options)
        poll.attach(self._results)                             # Observer
        poll.attach(self._audit)
        self._repository.add(poll)
        return poll

    def list_polls(self) -> list[Poll]:
        return self._repository.list()

    def get_poll(self, poll_id: int) -> Poll:
        return self._repository.get(poll_id)

    def vote(self, poll_id: int, user: object, options: object) -> Vote:
        poll = self._repository.get(poll_id)
        return VotingProxy(poll).vote(user, options)           # Proxy

    def results(self, poll_id: int) -> dict:
        return self._results.results(self._repository.get(poll_id))

    def close_poll(self, poll_id: int) -> Poll:
        poll = self._repository.get(poll_id)
        poll.close()
        return poll

    def audit(self, poll_id: int) -> list[dict]:
        self._repository.get(poll_id)  # garante 404 se a enquete não existir
        return self._audit.entries(poll_id)
