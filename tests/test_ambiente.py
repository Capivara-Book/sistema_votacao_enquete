"""Sanidade do ambiente de teste: isolamento, usuários, espiões e servidor em thread."""
import pytest

from client.api_client import ApiClient, ApiError


# ---------------------------------------------------------------- isolamento por teste
def test_each_test_starts_with_ids_from_1_a(new_poll, repository):
    assert repository.list() == []
    assert new_poll()["id"] == 1


def test_each_test_starts_with_ids_from_1_b(new_poll, repository):
    # Se o estado vazasse do teste anterior, o id seria 2.
    assert repository.list() == []
    assert new_poll()["id"] == 1


def test_client_and_service_start_empty(client, service):
    assert client.get("/polls").get_json() == []
    assert service.list_polls() == []


# ---------------------------------------------------------------- usuários
def test_users_are_distinct_valid_names(users):
    assert len({users.ana, users.bia, users.caio}) == 3
    assert all(1 <= len(user) <= 30 for user in users)


# ---------------------------------------------------------------- espiões
def test_poll_vote_spy_records_calls_that_reach_the_real_poll(service, poll_vote_calls, users):
    poll = service.create_poll("Café?", ["Sim", "Não"], "single")
    service.vote(poll.id, users.ana, ["Sim"])
    assert poll_vote_calls == [(poll.id, users.ana, ("Sim",))]


def test_observer_spy_records_notifications(service, spy_observer, users):
    poll = service.create_poll("Café?", ["Sim", "Não"], "single")
    poll.attach(spy_observer)
    service.vote(poll.id, users.ana, ["Sim"])
    assert spy_observer.calls == [(poll.id, users.ana, ("Sim",))]


# ---------------------------------------------------------------- servidor em thread e rede
def test_live_server_is_reachable(api):
    assert api.list_polls() == []


def test_closed_server_url_refuses_connection(closed_server_url):
    with pytest.raises(ApiError) as caught:
        ApiClient(closed_server_url, timeout=2).list_polls()
    assert caught.value.status is None


# ---------------------------------------------------------------- Qt offscreen
def test_window_opener_opens_empty_window(window_opener):
    window = window_opener()
    assert window.poll_list.count() == 0
    assert not window.is_busy()
