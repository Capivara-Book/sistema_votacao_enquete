"""Ponto de entrada do servidor: python -m server.run"""
from server.app import create_app

HOST = "127.0.0.1"
PORT = 5050


def main() -> None:
    create_app().run(host=HOST, port=PORT)


if __name__ == "__main__":
    main()
