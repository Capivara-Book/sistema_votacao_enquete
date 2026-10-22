"""Proxy (padrão estrutural).

VotingProxy implementa a mesma interface do Poll (Votable) e controla o
acesso ao voto: usuário válido, enquete aberta e voto único. Só depois
delega ao Poll real. O PollService nunca chama Poll.vote() diretamente.
"""
from __future__ import annotations

from server.errors import Conflict, ValidationError
from server.models import Poll, Vote, Votable

USER_MAX = 30


class VotingProxy(Votable):
    def __init__(self, poll: Poll):
        self._poll = poll

    def vote(self, user: str, options: list[str] | tuple[str, ...]) -> Vote:
        self._check_payload(user, options)
        # Mesmo lock de Poll.close(): verificar e votar é uma operação atômica (RNF07).
        with self._poll.lock:
            self._check_open()
            self._check_not_voted(user)
            return self._poll.vote(user, options)

    # ---- verificações de acesso ----
    @staticmethod
    def _check_payload(user: object, options: object) -> None:
        if not isinstance(user, str) or not user.strip():
            raise ValidationError("Usuário é obrigatório")
        if len(user.strip()) > USER_MAX:
            raise ValidationError(f"Usuário deve ter no máximo {USER_MAX} caracteres")
        if not isinstance(options, (list, tuple)) or not all(
            isinstance(o, str) for o in options
        ):
            raise ValidationError("Opções devem ser uma lista de textos")

    def _check_open(self) -> None:
        if not self._poll.is_open():
            raise Conflict("Enquete encerrada")

    def _check_not_voted(self, user: str) -> None:
        if self._poll.has_voted(user):
            raise Conflict("Usuário já votou nesta enquete")
