"""Factory Method: criação por tipo, validação comum e regra de voto de cada produto."""
import pytest

from server.errors import InvalidVote, ValidationError
from server.factory import (
    OPTIONS_MAX,
    TITLE_MAX,
    MultiplePollCreator,
    PollCreator,
    SinglePollCreator,
    get_creator,
)
from server.models import MultiplePoll, PollStatus, PollType, SinglePoll


# ---------------------------------------------------------------- escolha da fábrica
def test_get_creator_returns_creator_for_each_type():
    assert isinstance(get_creator("single"), SinglePollCreator)
    assert isinstance(get_creator("multiple"), MultiplePollCreator)


def test_get_creator_accepts_enum_member():
    assert isinstance(get_creator(PollType.MULTIPLE), MultiplePollCreator)


@pytest.mark.parametrize("invalid", ["", "unique", "SINGLE", None, 1, []])
def test_get_creator_rejects_unknown_type(invalid):
    with pytest.raises(ValidationError):
        get_creator(invalid)


# ---------------------------------------------------------------- produtos criados
def test_single_creator_builds_single_poll():
    poll = SinglePollCreator().create(1, "Café?", ["Sim", "Não"])
    assert isinstance(poll, SinglePoll)
    assert poll.type is PollType.SINGLE


def test_multiple_creator_builds_multiple_poll():
    poll = MultiplePollCreator().create(2, "Sabores?", ["Uva", "Maçã"])
    assert isinstance(poll, MultiplePoll)
    assert poll.type is PollType.MULTIPLE


def test_created_poll_starts_open_with_given_id():
    poll = SinglePollCreator().create(5, "Café?", ["Sim", "Não"])
    assert poll.id == 5
    assert poll.status is PollStatus.OPEN
    assert poll.is_open()


def test_create_trims_title_and_options():
    poll = SinglePollCreator().create(1, "  Café?  ", ["  Sim ", "Não  "])
    assert poll.title == "Café?"
    assert poll.options == ["Sim", "Não"]


# ---------------------------------------------------------------- regra de voto por tipo
def test_single_poll_rule_requires_exactly_one_option():
    poll = SinglePollCreator().create(1, "Café?", ["Sim", "Não"])
    poll.validate_choice(("Sim",))  # válido: não lança
    with pytest.raises(InvalidVote):
        poll.validate_choice(())
    with pytest.raises(InvalidVote):
        poll.validate_choice(("Sim", "Não"))


def test_multiple_poll_rule_accepts_several_distinct_options():
    poll = MultiplePollCreator().create(1, "Sabores?", ["Uva", "Maçã", "Pera"])
    poll.validate_choice(("Uva",))
    poll.validate_choice(("Uva", "Pera"))
    with pytest.raises(InvalidVote):
        poll.validate_choice(())
    with pytest.raises(InvalidVote):
        poll.validate_choice(("Uva", "Uva"))


@pytest.mark.parametrize("creator", [SinglePollCreator(), MultiplePollCreator()])
def test_both_types_reject_unknown_option(creator):
    poll = creator.create(1, "Café?", ["Sim", "Não"])
    with pytest.raises(InvalidVote):
        poll.validate_choice(("Talvez",))


# ---------------------------------------------------------------- validação de título (RN02)
@pytest.mark.parametrize("title", ["", "   ", None, 42, ["x"]])
def test_invalid_title_is_rejected(title):
    with pytest.raises(ValidationError):
        SinglePollCreator().create(1, title, ["A", "B"])


def test_title_length_limit():
    poll = SinglePollCreator().create(1, "x" * TITLE_MAX, ["A", "B"])
    assert len(poll.title) == TITLE_MAX
    with pytest.raises(ValidationError):
        SinglePollCreator().create(1, "x" * (TITLE_MAX + 1), ["A", "B"])


# ---------------------------------------------------------------- validação de opções (RN03)
@pytest.mark.parametrize(
    "options",
    [
        ["Só uma"],                         # menos de 2
        [],                                 # vazia
        [f"op{i}" for i in range(OPTIONS_MAX + 1)],  # mais de 10
        ["A", ""],                          # opção vazia
        ["A", "   "],                       # opção só com espaços
        ["Sim", "sim"],                     # duplicada sem diferenciar caixa
        ["Sim", " Sim "],                   # duplicada após strip
        ("A", "B"),                         # não é lista
        "A,B",                              # não é lista
        None,
        ["A", 2],                           # item que não é texto
    ],
)
def test_invalid_options_are_rejected(options):
    with pytest.raises(ValidationError):
        MultiplePollCreator().create(1, "Título", options)


def test_options_limits_are_inclusive():
    two = SinglePollCreator().create(1, "T", ["A", "B"])
    ten = SinglePollCreator().create(2, "T", [f"op{i}" for i in range(OPTIONS_MAX)])
    assert len(two.options) == 2
    assert len(ten.options) == OPTIONS_MAX


# ---------------------------------------------------------------- estrutura do padrão
class SpyCreator(PollCreator):
    def __init__(self):
        self.calls = []

    def make_poll(self, poll_id, title, options):
        self.calls.append((poll_id, title, options))
        return SinglePoll(poll_id, title, options)


def test_create_delegates_to_factory_method_with_clean_values():
    spy = SpyCreator()
    poll = spy.create(7, "  Título  ", [" A ", "B"])
    assert spy.calls == [(7, "Título", ["A", "B"])]
    assert poll.id == 7


def test_factory_method_is_not_called_when_validation_fails():
    spy = SpyCreator()
    with pytest.raises(ValidationError):
        spy.create(1, "", ["A", "B"])
    assert spy.calls == []


def test_poll_creator_is_abstract():
    with pytest.raises(TypeError):
        PollCreator()
