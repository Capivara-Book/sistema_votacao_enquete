"""Janela principal: lista de enquetes à esquerda, detalhe à direita."""
from __future__ import annotations

from functools import partial
from typing import Any, Callable

from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from client.api_client import ApiClient
from client.tasks import ApiTask
from client.views.create_poll_dialog import CreatePollDialog
from client.views.results_widget import ResultsWidget
from client.views.vote_panel import VotePanel

TYPE_LABELS = {"single": "escolha única", "multiple": "múltipla escolha"}
STATUS_LABELS = {"open": "aberta", "closed": "encerrada"}


class MainWindow(QMainWindow):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self.api = api
        self._pool = QThreadPool(self)
        self._tasks: set[ApiTask] = set()
        self._polls: list[dict] = []
        self._current: dict | None = None

        self.setWindowTitle("Sistema de Votação")
        self.resize(900, 560)
        self._build_ui()
        self._clear_detail()
        self.refresh_polls()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # coluna esquerda
        self.poll_list = QListWidget()
        self.refresh_button = QPushButton("Atualizar")
        self.new_button = QPushButton("Nova enquete")
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Enquetes"))
        left_layout.addWidget(self.poll_list)
        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.new_button)
        left_layout.addLayout(buttons)

        # coluna direita
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.title_label.setWordWrap(True)
        self.info_label = QLabel()
        self.vote_panel = VotePanel()
        self.results_widget = ResultsWidget()
        self.close_button = QPushButton("Encerrar enquete")
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.title_label)
        right_layout.addWidget(self.info_label)
        right_layout.addWidget(self.vote_panel)
        right_layout.addWidget(self.results_widget, 1)
        right_layout.addWidget(self.close_button)

        # banner de erro (não modal: não trava a interface nem os testes)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(
            "color: #b00020; background: #fdecea; padding: 6px; border-radius: 4px;"
        )
        self.error_label.hide()

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.error_label)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self.poll_list.currentRowChanged.connect(self.on_poll_selected)
        self.refresh_button.clicked.connect(self.refresh_polls)
        self.new_button.clicked.connect(self.on_new_poll)
        self.close_button.clicked.connect(self.on_close_poll)
        self.vote_panel.submitted.connect(self.on_vote)

    # ------------------------------------------------------- execução async
    def run_async(self, fn: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
        self.error_label.hide()
        task = ApiTask(fn, on_done, self._show_error)
        task.signals.finished.connect(self._on_task_finished)
        self._tasks.add(task)
        self._pool.start(task)

    @Slot(object)
    def _on_task_finished(self, task: ApiTask) -> None:
        self._tasks.discard(task)
        if task.error is not None:
            task.on_error(task.error)
        else:
            task.on_done(task.result)

    def is_busy(self) -> bool:
        return bool(self._tasks)

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    # --------------------------------------------------------------- listas
    def refresh_polls(self, *_: object) -> None:
        self.run_async(self.api.list_polls, self._on_polls_loaded)

    def _on_polls_loaded(self, polls: list[dict]) -> None:
        self._polls = polls
        current_id = self._current["id"] if self._current else None
        self.poll_list.blockSignals(True)
        self.poll_list.clear()
        for poll in polls:
            self.poll_list.addItem(self._item_text(poll))
        row = next((i for i, p in enumerate(polls) if p["id"] == current_id), -1)
        self.poll_list.setCurrentRow(row)
        self.poll_list.blockSignals(False)
        if row >= 0:
            self._show_poll(polls[row])
        else:
            self._clear_detail()

    @staticmethod
    def _item_text(poll: dict) -> str:
        return f"{poll['title']}  ·  {TYPE_LABELS[poll['type']]}  ·  {STATUS_LABELS[poll['status']]}"

    def on_poll_selected(self, row: int) -> None:
        if 0 <= row < len(self._polls):
            self._show_poll(self._polls[row])
        else:
            self._clear_detail()

    # -------------------------------------------------------------- detalhe
    def _show_poll(self, poll: dict) -> None:
        self._current = poll
        self.title_label.setText(poll["title"])
        self.info_label.setText(
            f"{TYPE_LABELS[poll['type']]}  ·  {STATUS_LABELS[poll['status']]}"
        )
        self.vote_panel.set_poll(poll)
        self.close_button.setEnabled(poll["status"] == "open")
        self.results_widget.clear()
        self._load_results(poll["id"])

    def _clear_detail(self) -> None:
        self._current = None
        self.title_label.setText("Selecione uma enquete")
        self.info_label.setText("")
        self.vote_panel.set_poll(None)
        self.results_widget.clear()
        self.close_button.setEnabled(False)

    def _load_results(self, poll_id: int) -> None:
        self.run_async(partial(self.api.results, poll_id), self._on_results_loaded)

    def _on_results_loaded(self, results: dict) -> None:
        # ignora resposta atrasada de uma enquete que não está mais selecionada
        if self._current and results["poll_id"] == self._current["id"]:
            self.results_widget.show_results(results)

    # ----------------------------------------------------------------- ações
    def on_new_poll(self, *_: object) -> None:
        dialog = CreatePollDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.values()
        self.run_async(
            partial(self.api.create_poll, data["title"], data["options"], data["type"]),
            self._on_created,
        )

    def _on_created(self, poll: dict) -> None:
        self.statusBar().showMessage("Enquete criada", 4000)
        self._current = poll  # será selecionada ao recarregar a lista
        self.refresh_polls()

    def on_vote(self, user: str, options: list) -> None:
        if not self._current:
            return
        poll_id = self._current["id"]
        self.run_async(
            partial(self.api.vote, poll_id, user, options),
            partial(self._on_voted, poll_id),
        )

    def _on_voted(self, poll_id: int, _result: dict) -> None:
        self.statusBar().showMessage("Voto registrado", 4000)
        if self._current and self._current["id"] == poll_id:
            self.vote_panel.reset()
            self._load_results(poll_id)

    def on_close_poll(self, *_: object) -> None:
        if not self._current:
            return
        answer = QMessageBox.question(
            self,
            "Encerrar enquete",
            f"Encerrar «{self._current['title']}»? Esta ação não pode ser desfeita.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.run_async(partial(self.api.close_poll, self._current["id"]), self._on_closed)

    def _on_closed(self, _poll: dict) -> None:
        self.statusBar().showMessage("Enquete encerrada", 4000)
        self.refresh_polls()

    def closeEvent(self, event) -> None:
        self._pool.waitForDone(2000)
        super().closeEvent(event)
