"""Application factory. O repositório é injetado: sem estado global (RNF04)."""
from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from server.errors import DomainError
from server.repository import PollRepository
from server.routes import bp
from server.service import PollService


def create_app(repository: PollRepository | None = None) -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False  # acentos legíveis no JSON
    app.json.sort_keys = False     # preserva a ordem das opções em "results"

    repo = repository if repository is not None else PollRepository()
    app.extensions["poll_service"] = PollService(repo)
    app.register_blueprint(bp)

    @app.errorhandler(DomainError)
    def handle_domain_error(err: DomainError):
        return jsonify({"error": err.message}), err.status

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        return jsonify({"error": err.description}), err.code

    return app
