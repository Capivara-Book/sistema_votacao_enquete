"""ApiTask: resultado, tratamento de erros e execução fora da thread principal."""
import threading

from PySide6.QtCore import QThreadPool

from client.api_client import ApiError
from client.tasks import ApiTask


def make_task(fn):
    return ApiTask(fn, on_done=lambda result: None, on_error=lambda message: None)


def test_success_stores_result_and_emits_the_task(qtbot):
    task = make_task(lambda: {"ok": True})
    with qtbot.waitSignal(task.signals.finished, timeout=1000) as blocker:
        task.run()
    assert blocker.args == [task]
    assert task.result == {"ok": True}
    assert task.error is None


def test_api_error_is_stored_as_message(qtbot):
    def fail():
        raise ApiError("Enquete encerrada", 409)

    task = make_task(fail)
    with qtbot.waitSignal(task.signals.finished, timeout=1000):
        task.run()
    assert task.error == "Enquete encerrada"
    assert task.result is None


def test_unexpected_exception_is_contained(qtbot):
    def boom():
        raise RuntimeError("boom")

    task = make_task(boom)
    with qtbot.waitSignal(task.signals.finished, timeout=1000):
        task.run()
    assert task.error == "Erro inesperado: boom"


def test_task_runs_outside_the_main_thread(qtbot):
    seen = {}

    def fn():
        seen["thread"] = threading.get_ident()
        return 1

    task = make_task(fn)
    pool = QThreadPool()
    with qtbot.waitSignal(task.signals.finished, timeout=5000):
        pool.start(task)
    pool.waitForDone(2000)

    assert seen["thread"] != threading.get_ident()
    assert task.result == 1


def test_auto_delete_is_disabled():
    assert make_task(lambda: None).autoDelete() is False
