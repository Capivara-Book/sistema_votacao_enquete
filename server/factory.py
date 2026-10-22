"""Factory Method (padrão criacional).

PollCreator.create() é o método-template: valida o que é comum a qualquer
enquete (RN02 e RN03) e delega ao método fábrica make_poll(), que cada
subclasse implementa devolvendo o tipo concreto de enquete.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from server.errors import ValidationError
from server.models import MultiplePoll, Poll, PollType, SinglePoll

TITLE_MAX = 120
OPTIONS_MIN = 2
OPTIONS_MAX = 10


class PollCreator(ABC):
    def create(self, poll_id: int, title: object, options: object) -> Poll:
        clean_title = self._validate_title(title)
        clean_options = self._validate_options(options)
        return self.make_poll(poll_id, clean_title, clean_options)

    @abstractmethod
    def make_poll(self, poll_id: int, title: str, options: list[str]) -> Poll:
        """Método fábrica: devolve a enquete concreta do tipo."""

    @staticmethod
    def _validate_title(title: object) -> str:
        if not isinstance(title, str) or not title.strip():
            raise ValidationError("Título é obrigatório")
        title = title.strip()
        if len(title) > TITLE_MAX:
            raise ValidationError(f"Título deve ter no máximo {TITLE_MAX} caracteres")
        return title

    @staticmethod
    def _validate_options(options: object) -> list[str]:
        if not isinstance(options, list) or not all(isinstance(o, str) for o in options):
            raise ValidationError("Opções devem ser uma lista de textos")
        clean = [o.strip() for o in options]
        if any(not o for o in clean):
            raise ValidationError("Opções não podem ser vazias")
        if not OPTIONS_MIN <= len(clean) <= OPTIONS_MAX:
            raise ValidationError(
                f"A enquete deve ter de {OPTIONS_MIN} a {OPTIONS_MAX} opções"
            )
        if len({o.casefold() for o in clean}) != len(clean):
            raise ValidationError("Opções duplicadas")
        return clean


class SinglePollCreator(PollCreator):
    def make_poll(self, poll_id: int, title: str, options: list[str]) -> Poll:
        return SinglePoll(poll_id, title, options)


class MultiplePollCreator(PollCreator):
    def make_poll(self, poll_id: int, title: str, options: list[str]) -> Poll:
        return MultiplePoll(poll_id, title, options)


_CREATORS: dict[PollType, PollCreator] = {
    PollType.SINGLE: SinglePollCreator(),
    PollType.MULTIPLE: MultiplePollCreator(),
}


def get_creator(poll_type: object) -> PollCreator:
    """Escolhe a fábrica pelo tipo informado (RN04)."""
    try:
        return _CREATORS[PollType(poll_type)]
    except ValueError:
        raise ValidationError("Tipo deve ser 'single' ou 'multiple'") from None
