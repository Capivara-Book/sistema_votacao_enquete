"""Ponto de entrada do cliente: python -m client.main

URL do servidor configurável pela variável ENQUETES_API_URL
(padrão: http://127.0.0.1:5050).
"""
import os
import sys

from PySide6.QtWidgets import QApplication

from client.api_client import DEFAULT_BASE_URL, ApiClient
from client.views.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    api = ApiClient(os.environ.get("ENQUETES_API_URL", DEFAULT_BASE_URL))
    window = MainWindow(api)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
