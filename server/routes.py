"""Endpoints REST. Esta camada só traduz HTTP; as regras ficam no serviço."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from server.errors import ValidationError
from server.service import PollService

bp = Blueprint("polls", __name__)


def _service() -> PollService:
    return current_app.extensions["poll_service"]


def _json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Corpo da requisição deve ser um objeto JSON")
    return data


@bp.post("/polls")
def create_poll():
    data = _json_body()
    poll = _service().create_poll(data.get("title"), data.get("options"), data.get("type"))
    return jsonify(poll.to_dict()), 201


@bp.get("/polls")
def list_polls():
    return jsonify([p.to_dict() for p in _service().list_polls()])


@bp.get("/polls/<int:poll_id>")
def get_poll(poll_id: int):
    return jsonify(_service().get_poll(poll_id).to_dict())


@bp.post("/polls/<int:poll_id>/votes")
def vote(poll_id: int):
    data = _json_body()
    cast = _service().vote(poll_id, data.get("user"), data.get("options"))
    return jsonify(
        {"poll_id": cast.poll_id, "user": cast.user, "options": list(cast.options)}
    ), 201


@bp.get("/polls/<int:poll_id>/results")
def results(poll_id: int):
    return jsonify(_service().results(poll_id))


@bp.post("/polls/<int:poll_id>/close")
def close_poll(poll_id: int):
    return jsonify(_service().close_poll(poll_id).to_dict())


@bp.get("/polls/<int:poll_id>/audit")
def audit(poll_id: int):
    return jsonify(_service().audit(poll_id))
