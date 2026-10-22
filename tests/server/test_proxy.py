"""Proxy: usuário válido, enquete aberta, voto único, ordem das verificações e atomicidade."""
import threading
from unittest.mock import Mock

import pytest

from server.errors import Conflict, InvalidVote, ValidationError
from server.factory import MultiplePollCreator, SinglePollCreator
from server.models import Votable
from server.proxy import USER_MAX, VotingProxy


def single_poll():
    return SinglePollCreator().create(1, "Café?", ["Sim", "Não"])


def multiple_poll():
    return MultiplePollCreator().create(2, "Sabores?", ["Uva", "Maçã", "Pera"])


def run_concurrently(callables):
    """Executa todas ao mesmo tempo (Barrier) e devolve [("ok", valor) | ("err", exceção)]."""
    barrier = threading.Barrier(len(callables))
    outcomes = [None] * len(callables)

    def worker(index):
        barrier.wait()
        try:
            outcomes[index] = ("ok", callables[index]())
        except Exception as err:  # noqa: BLE001 - queremos capturar qualquer falha
            outcomes[index] = ("err", err)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(callables))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    return outcomes


# ---------------------------------------------------------------- voto aceito
def test_valid_vote_is_delegated_and_returned():
    poll = single_poll()
    vote = VotingProxy(poll).vote("Ana", ["Sim"])
    assert (vote.poll_id, vote.user, vote.options) == (1, "Ana", ("Sim",))
    assert poll.votes == [vote]


def test_user_is_trimmed_and_tracked_case_insensitively():
    poll = single_poll()
    vote = VotingProxy(poll).vote("  Ana  ", ["Sim"])
    assert vote.user == "Ana"
    assert poll.has_voted("ANA")


def test_proxy_implements_the_same_interface_as_poll():
    assert isinstance(VotingProxy(single_poll()), Votable)


def test_accepted_vote_reaches_the_real_poll_once():
    poll = single_poll()
    poll.vote = Mock(wraps=poll.vote)
    VotingProxy(poll).vote("Ana", ["Sim"])
    poll.vote.assert_called_once_with("Ana", ["Sim"])


def test_multiple_poll_accepts_several_options_through_proxy():
    poll = multiple_poll()
    vote = VotingProxy(poll).vote("Ana", ["Uva", "Pera"])
    assert vote.options == ("Uva", "Pera")


# ---------------------------------------------------------------- usuário válido (RF08, RN01)
@pytest.mark.parametrize("user", ["", "   ", None, 42, ["Ana"]])
def test_invalid_user_is_rejected(user):
    poll = single_poll()
    with pytest.raises(ValidationError):
        VotingProxy(poll).vote(user, ["Sim"])
    assert poll.votes == []


def test_user_length_limit_is_inclusive():
    poll = single_poll()
    VotingProxy(poll).vote("x" * USER_MAX, ["Sim"])
    with pytest.raises(ValidationError):
        VotingProxy(poll).vote("y" * (USER_MAX + 1), ["Sim"])
    assert len(poll.votes) == 1


@pytest.mark.parametrize("options", ["Sim", None, [1], [None], {"Sim"}, 7])
def test_malformed_options_payload_is_rejected(options):
    poll = single_poll()
    with pytest.raises(ValidationError):
        VotingProxy(poll).vote("Ana", options)
    assert poll.votes == []


# ---------------------------------------------------------------- enquete aberta (RF07)
def test_closed_poll_rejects_votes():
    poll = single_poll()
    poll.close()
    with pytest.raises(Conflict, match="encerrada"):
        VotingProxy(poll).vote("Ana", ["Sim"])
    assert poll.votes == []


# ---------------------------------------------------------------- voto único (RF09, RN05)
def test_second_vote_from_same_user_is_rejected():
    poll = single_poll()
    VotingProxy(poll).vote("Ana", ["Sim"])
    with pytest.raises(Conflict, match="já votou"):
        VotingProxy(poll).vote("Ana", ["Não"])
    assert len(poll.votes) == 1


def test_duplicate_check_ignores_case_and_spaces():
    poll = single_poll()
    VotingProxy(poll).vote("Ana", ["Sim"])
    with pytest.raises(Conflict):
        VotingProxy(poll).vote("  ANA ", ["Não"])


def test_different_users_can_vote_on_the_same_poll():
    poll = single_poll()
    VotingProxy(poll).vote("Ana", ["Sim"])
    VotingProxy(poll).vote("Bia", ["Não"])
    assert len(poll.votes) == 2


def test_same_user_can_vote_on_different_polls():
    first, second = single_poll(), multiple_poll()
    VotingProxy(first).vote("Ana", ["Sim"])
    VotingProxy(second).vote("Ana", ["Uva"])
    assert len(first.votes) == len(second.votes) == 1


# ---------------------------------------------------------------- regra do tipo (422)
def test_choice_rule_violation_returns_invalid_vote_and_changes_nothing():
    poll = single_poll()
    with pytest.raises(InvalidVote):
        VotingProxy(poll).vote("Ana", ["Sim", "Não"])
    assert poll.votes == []
    assert not poll.has_voted("Ana")


def test_rejected_choice_does_not_burn_the_users_vote():
    poll = single_poll()
    with pytest.raises(InvalidVote):
        VotingProxy(poll).vote("Ana", ["Talvez"])
    VotingProxy(poll).vote("Ana", ["Sim"])  # ainda pode votar
    assert len(poll.votes) == 1


@pytest.mark.parametrize("factory", [single_poll, multiple_poll])
def test_empty_option_list_is_a_choice_error_not_a_payload_error(factory):
    with pytest.raises(InvalidVote):
        VotingProxy(factory()).vote("Ana", [])


# ---------------------------------------------------------------- ordem das verificações
def test_order_user_check_comes_before_closed_check():
    poll = single_poll()
    poll.close()
    with pytest.raises(ValidationError):
        VotingProxy(poll).vote("", ["Sim"])


def test_order_closed_check_comes_before_duplicate_and_choice_rule():
    poll = single_poll()
    VotingProxy(poll).vote("Ana", ["Sim"])
    poll.close()
    with pytest.raises(Conflict, match="encerrada"):
        VotingProxy(poll).vote("Ana", ["Talvez"])


def test_order_duplicate_check_comes_before_choice_rule():
    poll = single_poll()
    VotingProxy(poll).vote("Ana", ["Sim"])
    with pytest.raises(Conflict, match="já votou"):
        VotingProxy(poll).vote("Ana", ["Talvez"])  # seria 422 se a regra viesse antes


def test_rejections_never_reach_the_real_poll():
    poll = single_poll()
    VotingProxy(poll).vote("Ana", ["Sim"])
    poll.close()
    poll.vote = Mock(wraps=poll.vote)
    for user, options in [("", ["Sim"]), ("Ana", ["Sim"]), ("Bia", ["Sim"])]:
        with pytest.raises((ValidationError, Conflict)):
            VotingProxy(poll).vote(user, options)
    poll.vote.assert_not_called()


# ---------------------------------------------------------------- atomicidade (RNF07)
def test_concurrent_votes_from_same_user_accept_exactly_one():
    poll = multiple_poll()
    outcomes = run_concurrently(
        [lambda: VotingProxy(poll).vote("Ana", ["Uva"]) for _ in range(20)]
    )
    accepted = [o for o in outcomes if o[0] == "ok"]
    rejected = [o[1] for o in outcomes if o[0] == "err"]
    assert len(accepted) == 1
    assert len(rejected) == 19 and all(isinstance(e, Conflict) for e in rejected)
    assert len(poll.votes) == 1


def test_concurrent_votes_from_different_users_are_all_accepted():
    poll = single_poll()
    outcomes = run_concurrently(
        [lambda user=f"user{i}": VotingProxy(poll).vote(user, ["Sim"]) for i in range(30)]
    )
    assert all(o[0] == "ok" for o in outcomes)
    assert len(poll.votes) == 30


# ---------------------------------------------------------------- integração com o serviço (CA18)
def test_service_routes_every_vote_through_the_proxy(service, monkeypatch):
    calls = []

    class RecordingProxy(VotingProxy):
        def vote(self, user, options):
            calls.append((user, tuple(options)))
            return super().vote(user, options)

    monkeypatch.setattr("server.service.VotingProxy", RecordingProxy)
    poll = service.create_poll("Café?", ["Sim", "Não"], "single")

    service.vote(poll.id, "Ana", ["Sim"])
    with pytest.raises(Conflict):
        service.vote(poll.id, "Ana", ["Não"])

    assert calls == [("Ana", ("Sim",)), ("Ana", ("Não",))]
