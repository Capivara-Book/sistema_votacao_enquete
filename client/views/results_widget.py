"""Resultados: uma barra de progresso por opção e o total de votos."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class ResultsWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows: list[tuple[str, int]] = []  # (opção, contagem), útil nos testes
        self._row_widgets: list[QWidget] = []

        self.total_label = QLabel()
        self._rows_layout = QVBoxLayout()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.total_label)
        layout.addLayout(self._rows_layout)
        layout.addStretch(1)

    def clear(self) -> None:
        for widget in self._row_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self._row_widgets.clear()
        self.rows.clear()
        self.total_label.setText("")

    def show_results(self, results: dict) -> None:
        self.clear()
        total = results["total_votes"]
        suffix = "  (enquete encerrada)" if results["status"] == "closed" else ""
        self.total_label.setText(f"Total de votos: {total}{suffix}")

        for option, count in results["results"].items():
            label = QLabel(option)
            label.setMinimumWidth(120)
            bar = QProgressBar()
            bar.setRange(0, max(total, 1))
            bar.setValue(count)
            bar.setFormat("%v")

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(label)
            row_layout.addWidget(bar, 1)

            self._rows_layout.addWidget(row)
            self._row_widgets.append(row)
            self.rows.append((option, count))
