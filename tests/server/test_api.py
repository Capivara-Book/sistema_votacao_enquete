"""API HTTP: cobre CA01 a CA16 pelo cliente de teste do Flask (sem rede).

Cada teste recebe um app novo com repositório próprio (fixtures do conftest).
"""
from datetime import datetime

import pytest

from server.app import create_app
from server.repository import PollRepository


# ------------------------------------------------------------------ helpers
def make_poll(client, title="Café?", options=("Sim", "Não"), poll_type="single"):
    response = client.post(
        "/polls", json={"title": title, "options": list(options), "type": poll_type}
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def cast(client, poll_id, user, options):
    return client.post(f"/polls/{poll_id}/votes", json={"user": user, "options": options})


def assert_error(response, status):
    assert response.status_code == status
    assert response.is_json
    body = response.get_json()
    assert isinstance(body.get("error"), str) and body["error"]


# ------------------------------------------------------------------ criar enquete (CA01-CA03)
def test_create_single_poll_returns_201_with_open_status(client):
    response = client.post(
        "/polls", json={"title": "Café?", "options": ["Sim", "Não"], "type": "single"}
    )
    assert response.status_code == 201
    assert response.get_json() == {
        "id": 1,
        "title": "Café?",
        "type": "single",
        "status": "open",
        "options": ["Sim", "Não"],
    }


def test_create_multiple_poll_returns_201(client):
    body = make_poll(client, "Sabores?", ["Uva", "Maçã", "Pera"], "multiple")
    assert body["type"] == "multiple"
    assert body["status"] == "open"


def test_create_trims_title_and_options(client):
    body = make_poll(client, "  Café?  ", ["  Sim ", "Não  "])
    assert body["title"] == "Café?"
    assert body["options"] == ["Sim", "Não"]


def test_ids_are_sequential(client):
    assert make_poll(client)["id"] == 1
    assert make_poll(client)["id"] == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"options": ["A", "B"], "type": "single"},                            # sem título
        {"title": "", "options": ["A", "B"], "type": "single"},
        {"title": "   ", "options": ["A", "B"], "type": "single"},
        {"title": "x" * 121, "options": ["A", "B"], "type": "single"},
        {"title": "T", "type": "single"},                                     # sem opções
        {"title": "T", "options": ["A"], "type": "single"},                   # 1 opção
        {"title": "T", "options": [f"o{i}" for i in range(11)], "type": "single"},
        {"title": "T", "options": ["A", "a"], "type": "single"},              # duplicada
        {"title": "T", "options": ["A", ""], "type": "single"},               # vazia
        {"title": "T", "options": "A,B", "type": "single"},                   # não é lista
        {"title": "T", "options": ["A", "B"]},                                # sem tipo
        {"title": "T", "options": ["A", "B"], "type": "unique"},              # tipo inválido
        {"title": "T", "options": ["A", "B"], "type": "SINGLE"},
    ],
)
def test_invalid_poll_data_returns_400_and_creates_nothing(client, payload):
    assert_error(client.post("/polls", json=payload), 400)
    assert client.get("/polls").get_json() == []


@pytest.mark.parametrize("raw", ["not json", "", "[1, 2]", '"texto"'])
def test_non_object_body_returns_400(client, raw):
    response = client.post("/polls", data=raw, content_type="application/json")
    assert_error(response, 400)


def test_body_without_json_content_type_returns_400(client):
    response = client.post("/polls", data='{"title": "T", "options": ["A", "B"], "type": "single"}')
    assert_error(response, 400)


def test_invalid_type_does_not_consume_an_id(client):
    client.post("/polls", json={"title": "T", "options": ["A", "B"], "type": "x"})
    assert make_poll(client)["id"] == 1


# ------------------------------------------------------------------ listar e consultar (CA04, CA05)
def test_list_is_empty_at_start(client):
    response = client.get("/polls")
    assert response.status_code == 200
    assert response.get_json() == []


def test_list_returns_all_polls_in_creation_order(client):
    make_poll(client, "Primeira")
    make_poll(client, "Segunda", ["Uva", "Pera"], "multiple")
    polls = client.get("/polls").get_json()
    assert [(p["id"], p["title"], p["type"], p["status"]) for p in polls] == [
        (1, "Primeira", "single", "open"),
        (2, "Segunda", "multiple", "open"),
    ]


def test_get_poll_returns_the_same_data_as_creation(client):
    created = make_poll(client)
    response = client.get(f"/polls/{created['id']}")
    assert response.status_code == 200
    assert response.get_json() == created


def test_get_unknown_poll_returns_404(client):
    assert_error(client.get("/polls/999"), 404)


@pytest.mark.parametrize(
    "method, path, kwargs",
    [
        ("get", "/polls/999", {}),
        ("post", "/polls/999/votes", {"json": {"user": "Ana", "options": ["Sim"]}}),
        ("get", "/polls/999/results", {}),
        ("post", "/polls/999/close", {}),
        ("get", "/polls/999/audit", {}),
    ],
)
def test_every_poll_endpoint_returns_404_for_unknown_id(client, method, path, kwargs):
    assert_error(getattr(client, method)(path, **kwargs), 404)


def test_vote_on_unknown_poll_is_404_even_with_bad_payload(client):
    response = client.post("/polls/999/votes", json={"user": "", "options": "x"})
    assert_error(response, 404)


# ------------------------------------------------------------------ votar: sucesso (CA06, CA08)
def test_single_vote_returns_201_and_counts(client):
    poll = make_poll(client)
    response = cast(client, poll["id"], "Ana", ["Sim"])
    assert response.status_code == 201
    assert response.get_json() == {"poll_id": 1, "user": "Ana", "options": ["Sim"]}
    results = client.get("/polls/1/results").get_json()
    assert results["results"] == {"Sim": 1, "Não": 0}


def test_multiple_vote_counts_each_chosen_option(client):
    poll = make_poll(client, "Sabores?", ["Uva", "Maçã", "Pera"], "multiple")
    response = cast(client, poll["id"], "Ana", ["Uva", "Pera"])
    assert response.status_code == 201
    results = client.get("/polls/1/results").get_json()
    assert results["results"] == {"Uva": 1, "Maçã": 0, "Pera": 1}
    assert results["total_votes"] == 1  # uma cédula


def test_vote_user_is_trimmed_in_response(client):
    make_poll(client)
    assert cast(client, 1, "  Ana  ", ["Sim"]).get_json()["user"] == "Ana"


# ------------------------------------------------------------------ votar: erros (CA07, CA09-CA12)
@pytest.mark.parametrize("options", [[], ["Sim", "Não"], ["Talvez"]])
def test_single_poll_rejects_invalid_choice_with_422(client, options):
    make_poll(client)
    assert_error(cast(client, 1, "Ana", options), 422)
    assert client.get("/polls/1/results").get_json()["total_votes"] == 0


@pytest.mark.parametrize("options", [[], ["Uva", "Uva"], ["Uva", "Kiwi"]])
def test_multiple_poll_rejects_invalid_choice_with_422(client, options):
    make_poll(client, "Sabores?", ["Uva", "Maçã"], "multiple")
    assert_error(cast(client, 1, "Ana", options), 422)
    assert client.get("/polls/1/results").get_json()["total_votes"] == 0


def test_second_vote_from_same_user_returns_409(client):
    make_poll(client)
    assert cast(client, 1, "Ana", ["Sim"]).status_code == 201
    assert_error(cast(client, 1, "Ana", ["Não"]), 409)
    assert client.get("/polls/1/results").get_json()["results"] == {"Sim": 1, "Não": 0}


def test_duplicate_detection_ignores_case_and_spaces(client):
    make_poll(client)
    cast(client, 1, "Ana", ["Sim"])
    assert_error(cast(client, 1, "  ANA ", ["Não"]), 409)


def test_same_user_can_vote_in_different_polls(client):
    make_poll(client, "A?")
    make_poll(client, "B?")
    assert cast(client, 1, "Ana", ["Sim"]).status_code == 201
    assert cast(client, 2, "Ana", ["Sim"]).status_code == 201


@pytest.mark.parametrize("user", ["", "   ", None, 42, "x" * 31])
def test_invalid_user_returns_400(client, user):
    make_poll(client)
    assert_error(cast(client, 1, user, ["Sim"]), 400)


def test_user_with_30_chars_is_accepted(client):
    make_poll(client)
    assert cast(client, 1, "x" * 30, ["Sim"]).status_code == 201


def test_vote_without_user_or_options_returns_400(client):
    make_poll(client)
    assert_error(client.post("/polls/1/votes", json={"options": ["Sim"]}), 400)
    assert_error(client.post("/polls/1/votes", json={"user": "Ana"}), 400)
    assert_error(client.post("/polls/1/votes", json={"user": "Ana", "options": "Sim"}), 400)


def test_vote_without_json_body_returns_400(client):
    make_poll(client)
    assert_error(client.post("/polls/1/votes"), 400)


def test_vote_on_closed_poll_returns_409(client):
    make_poll(client)
    client.post("/polls/1/close")
    assert_error(cast(client, 1, "Ana", ["Sim"]), 409)
    assert client.get("/polls/1/results").get_json()["total_votes"] == 0


def test_error_precedence_user_closed_duplicate_choice(client):
    make_poll(client)
    cast(client, 1, "Ana", ["Sim"])
    # duplicado antes da regra do tipo: 409, não 422
    assert_error(cast(client, 1, "Ana", ["Talvez"]), 409)
    client.post("/polls/1/close")
    # usuário inválido antes de "encerrada": 400, não 409
    assert_error(cast(client, 1, "", ["Sim"]), 400)


# ------------------------------------------------------------------ resultados (CA13)
def test_results_of_poll_without_votes_list_zeros(client):
    make_poll(client)
    response = client.get("/polls/1/results")
    assert response.status_code == 200
    assert response.get_json() == {
        "poll_id": 1,
        "status": "open",
        "total_votes": 0,
        "results": {"Sim": 0, "Não": 0},
    }


def test_results_accumulate_across_users(client):
    make_poll(client)
    cast(client, 1, "Ana", ["Sim"])
    cast(client, 1, "Bia", ["Sim"])
    cast(client, 1, "Caio", ["Não"])
    body = client.get("/polls/1/results").get_json()
    assert body["results"] == {"Sim": 2, "Não": 1}
    assert body["total_votes"] == 3


def test_results_of_one_poll_do_not_leak_into_another(client):
    make_poll(client, "A?")
    make_poll(client, "B?")
    cast(client, 1, "Ana", ["Sim"])
    assert client.get("/polls/2/results").get_json()["total_votes"] == 0


# ------------------------------------------------------------------ encerrar (CA14, CA15)
def test_close_returns_closed_poll(client):
    make_poll(client)
    response = client.post("/polls/1/close")
    assert response.status_code == 200
    assert response.get_json()["status"] == "closed"


def test_close_is_reflected_in_get_and_list(client):
    make_poll(client)
    client.post("/polls/1/close")
    assert client.get("/polls/1").get_json()["status"] == "closed"
    assert client.get("/polls").get_json()[0]["status"] == "closed"


def test_results_remain_available_after_close(client):
    make_poll(client)
    cast(client, 1, "Ana", ["Sim"])
    client.post("/polls/1/close")
    body = client.get("/polls/1/results").get_json()
    assert body["status"] == "closed"
    assert body["results"]["Sim"] == 1 and body["total_votes"] == 1


def test_closing_twice_returns_409(client):
    make_poll(client)
    assert client.post("/polls/1/close").status_code == 200
    assert_error(client.post("/polls/1/close"), 409)


def test_closing_one_poll_does_not_close_others(client):
    make_poll(client, "A?")
    make_poll(client, "B?")
    client.post("/polls/1/close")
    assert client.get("/polls/2").get_json()["status"] == "open"
    assert cast(client, 2, "Ana", ["Sim"]).status_code == 201


# ------------------------------------------------------------------ auditoria (CA16)
def test_audit_is_empty_before_votes(client):
    make_poll(client)
    response = client.get("/polls/1/audit")
    assert response.status_code == 200
    assert response.get_json() == []


def test_audit_records_accepted_votes_in_order(client):
    make_poll(client, "Sabores?", ["Uva", "Maçã", "Pera"], "multiple")
    cast(client, 1, "Ana", ["Uva", "Pera"])
    cast(client, 1, "Bia", ["Maçã"])
    entries = client.get("/polls/1/audit").get_json()
    assert [(e["poll_id"], e["user"], e["options"]) for e in entries] == [
        (1, "Ana", ["Uva", "Pera"]),
        (1, "Bia", ["Maçã"]),
    ]
    assert datetime.fromisoformat(entries[0]["timestamp"]).tzinfo is not None


def test_audit_ignores_rejected_votes(client):
    make_poll(client)
    cast(client, 1, "Ana", ["Sim"])
    cast(client, 1, "Ana", ["Não"])          # 409 duplicado
    cast(client, 1, "Bia", ["Talvez"])       # 422 regra do tipo
    cast(client, 1, "", ["Sim"])             # 400 usuário
    client.post("/polls/1/close")
    cast(client, 1, "Caio", ["Sim"])         # 409 encerrada
    entries = client.get("/polls/1/audit").get_json()
    assert [e["user"] for e in entries] == ["Ana"]


def test_audit_is_separate_per_poll(client):
    make_poll(client, "A?")
    make_poll(client, "B?")
    cast(client, 1, "Ana", ["Sim"])
    cast(client, 2, "Bia", ["Não"])
    assert [e["user"] for e in client.get("/polls/1/audit").get_json()] == ["Ana"]
    assert [e["user"] for e in client.get("/polls/2/audit").get_json()] == ["Bia"]


# ------------------------------------------------------------------ formato e roteamento
def test_all_responses_are_json_with_readable_accents(client):
    response = client.post(
        "/polls", json={"title": "Você prefere?", "options": ["Não", "Sim"], "type": "single"}
    )
    assert response.is_json
    assert "Você prefere?".encode("utf-8") in response.data  # sem \u00ea
    assert "Não".encode("utf-8") in response.data


@pytest.mark.parametrize("path", ["/", "/nada", "/polls/abc", "/polls/1/inexistente"])
def test_unknown_routes_return_json_404(client, path):
    assert_error(client.get(path), 404)


@pytest.mark.parametrize(
    "method, path",
    [
        ("delete", "/polls"),
        ("put", "/polls/1"),
        ("get", "/polls/1/votes"),
        ("get", "/polls/1/close"),
        ("post", "/polls/1/results"),
    ],
)
def test_wrong_method_returns_json_405(client, repository, method, path):
    make_poll(client)
    assert_error(getattr(client, method)(path), 405)


# ------------------------------------------------------------------ injeção de repositório (RNF04)
def test_apps_do_not_share_state():
    first, second = create_app(PollRepository()), create_app(PollRepository())
    first_client, second_client = first.test_client(), second.test_client()
    make_poll(first_client)
    assert len(first_client.get("/polls").get_json()) == 1
    assert second_client.get("/polls").get_json() == []


def test_injected_repository_is_the_one_used(repository, client):
    make_poll(client)
    assert [poll.title for poll in repository.list()] == ["Café?"]


def test_create_app_without_arguments_works():
    app = create_app()
    assert app.test_client().get("/polls").get_json() == []


# ------------------------------------------------------------------ fluxo completo
def test_full_flow_create_vote_results_close_audit(client):
    make_poll(client, "Almoço?", ["Pizza", "Sushi", "Salada"], "multiple")
    assert cast(client, 1, "Ana", ["Pizza", "Sushi"]).status_code == 201
    assert cast(client, 1, "Bia", ["Sushi"]).status_code == 201
    assert_error(cast(client, 1, "Ana", ["Salada"]), 409)

    results = client.get("/polls/1/results").get_json()
    assert results["results"] == {"Pizza": 1, "Sushi": 2, "Salada": 0}
    assert results["total_votes"] == 2

    assert client.post("/polls/1/close").status_code == 200
    assert_error(cast(client, 1, "Caio", ["Pizza"]), 409)

    assert client.get("/polls/1/results").get_json()["total_votes"] == 2
    assert [e["user"] for e in client.get("/polls/1/audit").get_json()] == ["Ana", "Bia"]
