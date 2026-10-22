"""Painel de voto: radio buttons (single) ou checkboxes (multiple)."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class VotePanel(QWidget):
    submitted = Signal(str, list)  # (usuário, opções escolhidas)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: list[QAbstractButton] = []
        self._group: QButtonGroup | None = None

        self.hint_label = QLabel()
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("Seu nome")
        self.user_edit.setMaxLength(30)
        self._options_box = QVBoxLayout()
        self.submit_button = QPushButton("Votar")
        self.submit_button.clicked.connect(self._on_submit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.user_edit)
        layout.addLayout(self._options_box)
        layout.addWidget(self.submit_button)

    # ---- API usada pela janela ----
    def set_poll(self, poll: dict | None) -> None:
        self._clear_options()
        if poll is None:
            self.setVisible(False)
            return
        self.setVisible(True)

        is_open = poll["status"] == "open"
        single = poll["type"] == "single"
        if not is_open:
            self.hint_label.setText("Enquete encerrada: votação indisponível")
        elif single:
            self.hint_label.setText("Escolha uma opção")
        else:
            self.hint_label.setText("Escolha uma ou mais opções")

        if single:
            self._group = QButtonGroup(self)  # exclusivo por padrão
        for option in poll["options"]:
            button: QAbstractButton = QRadioButton() if single else QCheckBox()
            # "&" em texto de botão vira atalho; escapa para exibir o texto original
            button.setText(option.replace("&", "&&"))
            button.setProperty("option", option)
            button.setEnabled(is_open)
            self._options_box.addWidget(button)
            self._buttons.append(button)
            if self._group is not None:
                self._group.addButton(button)

        self.user_edit.setEnabled(is_open)
        self.submit_button.setEnabled(is_open)

    def selected_options(self) -> list[str]:
        return [b.property("option") for b in self._buttons if b.isChecked()]

    def reset(self) -> None:
        """Limpa nome e seleção depois de um voto aceito."""
        self.user_edit.clear()
        if self._group is not None:
            self._group.setExclusive(False)  # permite desmarcar radio buttons
        for button in self._buttons:
            button.setChecked(False)
        if self._group is not None:
            self._group.setExclusive(True)

    # ---- internos ----
    def _on_submit(self) -> None:
        self.submitted.emit(self.user_edit.text().strip(), self.selected_options())

    def _clear_options(self) -> None:
        for button in self._buttons:
            button.setParent(None)
            button.deleteLater()
        self._buttons.clear()
        if self._group is not None:
            self._group.deleteLater()
            self._group = None
