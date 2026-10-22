"""Execução de chamadas à API fora da thread da interface (RNF08).

O ApiTask roda em uma thread do QThreadPool e, ao terminar, emite
`finished` com ele mesmo. A janela recebe o sinal na thread principal
(conexão enfileirada, pois o receptor é um QObject) e chama o callback certo.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal

from client.api_client import ApiError


class TaskSignals(QObject):
    finished = Signal(object)  # emite o próprio ApiTask


class ApiTask(QRunnable):
    def __init__(
        self,
        fn: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[str], None],
    ) -> None:
        super().__init__()
        # A janela mantém a referência até o fim; sem auto-delete, o objeto
        # Python não é destruído antes de o sinal ser entregue.
        self.setAutoDelete(False)
        self.fn = fn
        self.on_done = on_done
        self.on_error = on_error
        self.result: Any = None
        self.error: str | None = None
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            self.result = self.fn()
        except ApiError as err:
            self.error = err.message
        except Exception as err:  # nunca deixar a thread morrer em silêncio
            self.error = f"Erro inesperado: {err}"
        self.signals.finished.emit(self)
