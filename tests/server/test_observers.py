"""Observer: mecânica de anexar/notificar, ResultsCounter, AuditLog e integração."""
import threading
from datetime import datetime

import pytest

from server.errors import Conflict, InvalidVote
from server.factory import MultiplePollCreator, SinglePollCreator
from server.observers import AuditLog, ResultsCounter, VoteObserver
from server.proxy import VotingProxy


def single_poll(poll_id=1):
    return SinglePollCreator().create(poll_id, "Café?", ["Sim", "Não"])


def multiple_poll(poll_id=2):
    return MultiplePollCreator().create(poll_id, "Sabores?", ["Uva", "Maçã", "Pera"])


def cast(poll, user, options):
    return VotingProxy(poll).vote(user, options)


class SpyObserver(VoteObserver):
    def __init__(self, name="spy", journal=None):
        self.name = name
        self.journal = journal if journal is not None else []
        self.calls = []

    def update(self, poll, vote):
        self.calls.append((poll, vote))
        self.journal.append(self.name)


# ---------------------------------------------------------------- mecânica do padrão
def test_vote_observer_is_abstract():
    with pytest.raises(TypeError):
        VoteObserver()


def test_observer_receives_poll_and_vote():
    poll, spy = single_poll(), SpyObserver()
    poll.attach(spy)
    vote = cast(poll, "Ana", ["Sim"])
    assert spy.calls == [(poll, vote)]


def test_all_attached_observers_are_notified_in_attach_order():
    poll, journal = single_poll(), []
    poll.attach(SpyObserver("primeiro", journal))
    poll.attach(SpyObserver("segundo", journal))
    cast(poll, "Ana", ["Sim"])
    assert journal == ["primeiro", "segundo"]


def test_attach_is_idempotent():
    poll, spy = single_poll(), SpyObserver()
    poll.attach(spy)
    poll.attach(spy)
    cast(poll, "Ana", ["Sim"])
    assert len(spy.calls) == 1


def test_detached_observer_is_no_longer_notified():
    poll, spy = single_poll(), SpyObserver()
    poll.attach(spy)
    cast(poll, "Ana", ["Sim"])
    poll.detach(spy)
    cast(poll, "Bia", ["Não"])
    assert len(spy.calls) == 1


def test_detach_of_unknown_observer_is_harmless():
    single_poll().detach(SpyObserver())


def test_rejected_votes_do_not_notify():
    poll, spy = single_poll(), SpyObserver()
    poll.attach(spy)
    cast(poll, "Ana", ["Sim"])
    spy.calls.clear()

    with pytest.raises(Conflict):
        cast(poll, "Ana", ["Não"])         # duplicado
    with pytest.raises(InvalidVote):
        cast(poll, "Bia", ["Talvez"])      # regra do tipo
    poll.close()
    with pytest.raises(Conflict):
        cast(poll, "Caio", ["Sim"])        # encerrada

    assert spy.calls == []


# ---------------------------------------------------------------- ResultsCounter (RF11)
def test_results_of_poll_without_votes_list_every_option_with_zero():
    poll, counter = single_poll(), ResultsCounter()
    poll.attach(counter)
    assert counter.results(poll) == {
        "poll_id": 1,
        "status": "open",
        "total_votes": 0,
        "results": {"Sim": 0, "Não": 0},
    }


def test_counter_never_attached_still_reports_zeros():
    assert ResultsCounter().results(single_poll())["total_votes"] == 0


def test_results_keep_the_option_order_of_the_poll():
    poll, counter = multiple_poll(), ResultsCounter()
    poll.attach(counter)
    cast(poll, "Ana", ["Pera"])
    assert list(counter.results(poll)["results"]) == ["Uva", "Maçã", "Pera"]


def test_single_votes_accumulate_per_option():
    poll, counter = single_poll(), ResultsCounter()
    poll.attach(counter)
    cast(poll, "Ana", ["Sim"])
    cast(poll, "Bia", ["Sim"])
    cast(poll, "Caio", ["Não"])
    data = counter.results(poll)
    assert data["results"] == {"Sim": 2, "Não": 1}
    assert data["total_votes"] == 3


def test_multiple_vote_counts_each_option_but_one_ballot():
    poll, counter = multiple_poll(), ResultsCounter()
    poll.attach(counter)
    cast(poll, "Ana", ["Uva", "Pera"])
    cast(poll, "Bia", ["Uva"])
    data = counter.results(poll)
    assert data["results"] == {"Uva": 2, "Maçã": 0, "Pera": 1}
    assert data["total_votes"] == 2  # cédulas, não opções marcadas


def test_closing_changes_status_but_keeps_counts():
    poll, counter = single_poll(), ResultsCounter()
    poll.attach(counter)
    cast(poll, "Ana", ["Sim"])
    poll.close()
    data = counter.results(poll)
    assert data["status"] == "closed"
    assert data["results"]["Sim"] == 1 and data["total_votes"] == 1


def test_one_counter_keeps_polls_separate():
    first, second, counter = single_poll(1), multiple_poll(2), ResultsCounter()
    first.attach(counter)
    second.attach(counter)
    cast(first, "Ana", ["Sim"])
    cast(second, "Ana", ["Uva", "Maçã"])
    assert counter.results(first)["results"] == {"Sim": 1, "Não": 0}
    assert counter.results(second)["results"] == {"Uva": 1, "Maçã": 1, "Pera": 0}


# ---------------------------------------------------------------- AuditLog (RF12, CA16)
def test_audit_entry_has_poll_user_options_and_timestamp():
    poll, log = single_poll(), AuditLog()
    poll.attach(log)
    cast(poll, "  Ana ", ["Sim"])

    (entry,) = log.entries(1)
    assert entry["poll_id"] == 1
    assert entry["user"] == "Ana"
    assert entry["options"] == ["Sim"]
    assert datetime.fromisoformat(entry["timestamp"]).tzinfo is not None


def test_audit_keeps_acceptance_order_and_all_options_of_a_ballot():
    poll, log = multiple_poll(), AuditLog()
    poll.attach(log)
    cast(poll, "Ana", ["Uva", "Pera"])
    cast(poll, "Bia", ["Maçã"])
    assert [(e["user"], e["options"]) for e in log.entries(2)] == [
        ("Ana", ["Uva", "Pera"]),
        ("Bia", ["Maçã"]),
    ]


def test_audit_is_filtered_by_poll():
    first, second, log = single_poll(1), single_poll(2), AuditLog()
    first.attach(log)
    second.attach(log)
    cast(first, "Ana", ["Sim"])
    cast(second, "Bia", ["Não"])
    assert [e["user"] for e in log.entries(1)] == ["Ana"]
    assert [e["user"] for e in log.entries(2)] == ["Bia"]
    assert log.entries(99) == []


def test_audit_ignores_rejected_votes():
    poll, log = single_poll(), AuditLog()
    poll.attach(log)
    cast(poll, "Ana", ["Sim"])
    with pytest.raises(Conflict):
        cast(poll, "Ana", ["Não"])
    with pytest.raises(InvalidVote):
        cast(poll, "Bia", ["Talvez"])
    poll.close()
    with pytest.raises(Conflict):
        cast(poll, "Caio", ["Sim"])
    assert len(log.entries(1)) == 1


def test_audit_entries_are_copies():
    poll, log = single_poll(), AuditLog()
    poll.attach(log)
    cast(poll, "Ana", ["Sim"])
    log.entries(1)[0]["user"] = "Adulterado"
    assert log.entries(1)[0]["user"] == "Ana"


# ---------------------------------------------------------------- integração com o serviço
def test_service_attaches_both_observers_to_new_polls(service):
    poll = service.create_poll("Café?", ["Sim", "Não"], "single")
    service.vote(poll.id, "Ana", ["Sim"])

    assert service.results(poll.id)["results"] == {"Sim": 1, "Não": 0}
    assert [e["user"] for e in service.audit(poll.id)] == ["Ana"]


def test_service_rejected_vote_changes_neither_results_nor_audit(service):
    poll = service.create_poll("Café?", ["Sim", "Não"], "single")
    service.vote(poll.id, "Ana", ["Sim"])
    with pytest.raises(Conflict):
        service.vote(poll.id, "Ana", ["Não"])
    with pytest.raises(InvalidVote):
        service.vote(poll.id, "Bia", ["Sim", "Não"])

    assert service.results(poll.id)["total_votes"] == 1
    assert len(service.audit(poll.id)) == 1


# ---------------------------------------------------------------- concorrência
def test_observers_stay_consistent_under_concurrent_votes(service):
    first = service.create_poll("Primeira", ["Sim", "Não"], "single")
    second = service.create_poll("Segunda", ["Sim", "Não"], "single")
    barrier = threading.Barrier(40)

    def worker(index):
        barrier.wait()
        target = first if index % 2 == 0 else second
        service.vote(target.id, f"user{index}", ["Sim" if index % 4 < 2 else "Não"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    for poll in (first, second):
        data = service.results(poll.id)
        assert data["total_votes"] == 20
        assert sum(data["results"].values()) == 20
        assert len(service.audit(poll.id)) == 20
