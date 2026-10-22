"""Modelos de domínio: Poll (e subclasses), Vote e enums.

Poll é o *Subject* do Observer e o *Produto* do Factory Method.
Poll implementa Votable e é o alvo real do VotingProxy.
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from server.errors import Conflict, InvalidVote

if TYPE_CHECKING:  # evita import circular; só para tipagem
    from server.observers import VoteObserver


class PollType(str, Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"


class PollStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


def normalize_user(user: str) -> str:
    """Chave de identificação do usuário (RN05): sem espaços e sem diferenciar caixa."""
    return user.strip().casefold()


@dataclass(frozen=True)
class Vote:
    poll_id: int
    user: str
    options: tuple[str, ...]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Votable(ABC):
    """Interface comum ao Poll real e ao VotingProxy."""

    @abstractmethod
    def vote(self, user: str, options: list[str] | tuple[str, ...]) -> Vote:
        ...


class Poll(Votable, ABC):
    """Enquete. A regra de escolha fica em validate_choice (varia por tipo).

    Poll.vote() NÃO verifica usuário, status nem voto duplicado: essa
    responsabilidade é do VotingProxy, que é o único caminho de voto usado
    pelo PollService.
    """

    type: PollType  # definido pelas subclasses

    def __init__(self, poll_id: int, title: str, options: list[str]):
        self.id = poll_id
        self.title = title
        self.options = list(options)
        self.status = PollStatus.OPEN
        self.lock = threading.RLock()
        self.votes: list[Vote] = []
        self._voters: set[str] = set()
        self._observers: list[VoteObserver] = []

    # ---- Observer (Subject) ----
    def attach(self, observer: VoteObserver) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: VoteObserver) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, vote: Vote) -> None:
        for observer in list(self._observers):
            observer.update(self, vote)

    # ---- Estado ----
    def is_open(self) -> bool:
        return self.status is PollStatus.OPEN

    def has_voted(self, user: str) -> bool:
        return normalize_user(user) in self._voters

    def close(self) -> None:
        with self.lock:
            if not self.is_open():
                raise Conflict("Enquete já está encerrada")
            self.status = PollStatus.CLOSED

    # ---- Voto ----
    def vote(self, user: str, options: list[str] | tuple[str, ...]) -> Vote:
        choice = tuple(options)
        self.validate_choice(choice)
        vote = Vote(self.id, user.strip(), choice)
        self.votes.append(vote)
        self._voters.add(normalize_user(user))
        self.notify(vote)
        return vote

    @abstractmethod
    def validate_choice(self, options: tuple[str, ...]) -> None:
        """Lança InvalidVote se a escolha violar a regra do tipo."""

    def _check_known(self, options: tuple[str, ...]) -> None:
        for option in options:
            if option not in self.options:
                raise InvalidVote(f"Opção inexistente: {option}")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type.value,
            "status": self.status.value,
            "options": list(self.options),
        }


class SinglePoll(Poll):
    type = PollType.SINGLE

    def validate_choice(self, options: tuple[str, ...]) -> None:
        if len(options) != 1:
            raise InvalidVote("Enquete de escolha única exige exatamente uma opção")
        self._check_known(options)


class MultiplePoll(Poll):
    type = PollType.MULTIPLE

    def validate_choice(self, options: tuple[str, ...]) -> None:
        if not options:
            raise InvalidVote("Selecione ao menos uma opção")
        if len(set(options)) != len(options):
            raise InvalidVote("Opções repetidas no voto")
        self._check_known(options)
