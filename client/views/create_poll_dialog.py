"""Diálogo de criação de enquete. A validação de verdade fica no servidor."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class CreatePollDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nova enquete")
        self.setMinimumWidth(380)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Pergunta da enquete")
        self.options_edit = QPlainTextEdit()
        self.options_edit.setPlaceholderText("Uma opção por linha (de 2 a 10)")
        self.type_combo = QComboBox()
        self.type_combo.addItem("Escolha única", "single")
        self.type_combo.addItem("Múltipla escolha", "multiple")

        form = QFormLayout()
        form.addRow("Título", self.title_edit)
        form.addRow("Opções", self.options_edit)
        form.addRow("Tipo", self.type_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict:
        lines = self.options_edit.toPlainText().splitlines()
        return {
            "title": self.title_edit.text().strip(),
            "options": [line.strip() for line in lines if line.strip()],
            "type": self.type_combo.currentData(),
        }
