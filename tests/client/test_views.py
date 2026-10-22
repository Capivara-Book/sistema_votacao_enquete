"""Telas Qt (pytest-qt, offscreen). A janela principal é testada contra o servidor real em thread."""
import socket

import pytest
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QProgressBar,
    QRadioButton,
    QWidget,
)

from client.api_client import ApiClient
from client.views.create_poll_dialog import CreatePollDialog
from client.views.main_window import MainWindow
from client.views.results_widget import ResultsWidget
from client.views.vote_panel import VotePanel


# ------------------------------------------------------------------ helpers
def closed_port_url() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


def wait_idle(qtbot, window):
    qtbot.waitUntil(lambda: not window.is_busy(), timeout=5000)


def open_window(qtbot, api):
    window = MainWindow(api)
    qtbot.addWidget(window)
    wait_idle(qtbot, window)
    return window


def select(qtbot, window, row):
    window.poll_list.setCurrentRow(row)
    wait_idle(qtbot, window)


def option_buttons(panel):
    """{texto original da opção: botão}. Ignora o botão de votar."""
    return {
        b.property("option"): b
        for b in panel.findChildren(QAbstractButton)
        if b.property("option") is not None
    }


def submit_vote(qtbot, window, user, *options):
    panel = window.vote_panel
    panel.user_edit.setText(user)
    buttons = option_buttons(panel)
    for option in options:
        buttons[option].click()
    panel.submit_button.click()
    wait_idle(qtbot, window)


def answer_question(monkeypatch, answer):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: answer))


def stub_dialog(monkeypatch, values, accepted=True):
    result = QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected
    monkeypatch.setattr(CreatePollDialog, "exec", lambda self: result)
    monkeypatch.setattr(CreatePollDialog, "values", lambda self: values)


def poll_dict(poll_type="single", status="open", options=("Sim", "Não")):
    return {"id": 1, "title": "T", "type": poll_type, "status": status, "options": list(options)}


# ================================================================== MainWindow
def test_starts_empty_without_polls(qtbot, api):
    window = open_window(qtbot, api)
    assert window.poll_list.count() == 0
    assert window.title_label.text() == "Selecione uma enquete"
    assert window.vote_panel.isHidden()
    assert not window.close_button.isEnabled()
    assert window.error_label.isHidden()
    assert window.new_button.isEnabled()


def test_lists_existing_polls(qtbot, api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    api.create_poll("Sabores?", ["Uva", "Pera"], "multiple")
    window = open_window(qtbot, api)

    assert window.poll_list.count() == 2
    first, second = window.poll_list.item(0).text(), window.poll_list.item(1).text()
    assert "Café?" in first and "escolha única" in first and "aberta" in first
    assert "Sabores?" in second and "múltipla escolha" in second


def test_selecting_poll_shows_details_and_zero_results(qtbot, api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    window = open_window(qtbot, api)
    select(qtbot, window, 0)

    assert window.title_label.text() == "Café?"
    assert "escolha única" in window.info_label.text()
    assert "aberta" in window.info_label.text()
    assert not window.vote_panel.isHidden()
    assert window.close_button.isEnabled()
    assert window.results_widget.rows == [("Sim", 0), ("Não", 0)]
    assert window.results_widget.total_label.text() == "Total de votos: 0"


def test_panel_uses_radio_for_single_and_checkboxes_for_multiple(qtbot, api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    api.create_poll("Sabores?", ["Uva", "Maçã", "Pera"], "multiple")
    window = open_window(qtbot, api)

    select(qtbot, window, 0)
    assert len(window.vote_panel.findChildren(QRadioButton)) == 2
    assert window.vote_panel.findChildren(QCheckBox) == []

    select(qtbot, window, 1)
    assert len(window.vote_panel.findChildren(QCheckBox)) == 3
    assert window.vote_panel.findChildren(QRadioButton) == []


# ------------------------------------------------------------------ votar pela interface (CA21)
def test_vote_through_ui_updates_results(qtbot, api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    window = open_window(qtbot, api)
    select(qtbot, window, 0)

    submit_vote(qtbot, window, "Ana", "Sim")

    assert window.results_widget.rows == [("Sim", 1), ("Não", 0)]
    assert window.results_widget.total_label.text() == "Total de votos: 1"
    assert window.statusBar().currentMessage() == "Voto registrado"
    assert window.vote_panel.user_edit.text() == ""
    assert window.vote_panel.selected_options() == []
    assert window.error_label.isHidden()
    assert api.results(1)["results"] == {"Sim": 1, "Não": 0}
    assert [e["user"] for e in api.audit(1)] == ["Ana"]


def test_multiple_vote_through_ui(qtbot, api):
    api.create_poll("Sabores?", ["Uva", "Maçã", "Pera"], "multiple")
    window = open_window(qtbot, api)
    select(qtbot, window, 0)

    submit_vote(qtbot, window, "Ana", "Uva", "Pera")

    assert window.results_widget.rows == [("Uva", 1), ("Maçã", 0), ("Pera", 1)]
    assert window.results_widget.total_label.text() == "Total de votos: 1"


def test_vote_with_empty_user_shows_server_error(qtbot, api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    window = open_window(qtbot, api)
    select(qtbot, window, 0)

    submit_vote(qtbot, window, "", "Sim")

    assert not window.error_label.isHidden()
    assert window.error_label.text() == "Usuário é obrigatório"
    assert api.results(1)["total_votes"] == 0


def test_vote_without_selection_shows_choice_error(qtbot, api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    window = open_window(qtbot, api)
    select(qtbot, window, 0)

    submit_vote(qtbot, window, "Ana")  # nenhuma opção marcada

    assert not window.error_label.isHidden()
    assert "exatamente uma opção" in window.error_label.text()
    assert api.results(1)["total_votes"] == 0


def test_duplicate_vote_shows_conflict_and_keeps_results(qtbot, api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    api.vote(1, "Ana", ["Sim"])
    window = open_window(qtbot, api)
    select(qtbot, window, 0)

    submit_vote(qtbot, window, "Ana", "Não")

    assert "já votou" in window.error_label.text()
    assert window.results_widget.rows == [("Sim", 1), ("Não", 0)]


def test_error_banner_clears_on_next_action(qtbot, api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    window = open_window(qtbot, api)
    select(qtbot, window, 0)
    submit_vote(qtbot, window, "", "Sim")
    assert not window.error_label.isHidden()

    window.refresh_button.click()
    assert window.error_label.isHidden()  # some assim que a nova ação começa
    wait_idle(qtbot, window)
    assert window.error_label.isHidden()


def test_option_with_ampersand_is_displayed_and_sent_unchanged(qtbot, api):
    api.create_poll("Estilo?", ["Rock & Roll", "Pop"], "single")
    window = open_window(qtbot, api)
    select(qtbot, window, 0)

    buttons = option_buttons(window.vote_panel)
    assert buttons["Rock & Roll"].text() == "Rock && Roll"  # "&" escapado para não virar atalho

    submit_vote(qtbot, window, "Ana", "Rock & Roll")

    assert window.results_widget.rows == [("Rock & Roll", 1), ("Pop", 0)]
    assert api.audit(1)[0]["options"] == ["Rock & Roll"]


# ------------------------------------------------------------------ enquete encerrada (CA14)
def test_closed_poll_disables_voting_but_shows_results(qtbot, api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    api.vote(1, "Ana", ["Sim"])
    api.close_poll(1)
    window = open_window(qtbot, api)
    select(qtbot, window, 0)

    panel = window.vote_panel
    assert panel.hint_label.text() == "Enquete encerrada: votação indisponível"
    assert not panel.submit_button.isEnabled()
    assert not panel.user_edit.isEnabled()
    assert all(not b.isEnabled() for b in option_buttons(panel).values())
    assert not window.close_button.isEnabled()
    assert window.results_widget.rows == [("Sim", 1), ("Não", 0)]
    assert window.results_widget.total_label.text() == "Total de votos: 1  (enquete encerrada)"


def test_close_poll_through_ui_after_confirmation(qtbot, api, monkeypatch):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    window = open_window(qtbot, api)
    select(qtbot, window, 0)
    answer_question(monkeypatch, QMessageBox.StandardButton.Yes)

    window.close_button.click()
    wait_idle(qtbot, window)

    assert api.get_poll(1)["status"] == "closed"
    assert "encerrada" in window.poll_list.item(0).text()
    assert not window.vote_panel.submit_button.isEnabled()
    assert not window.close_button.isEnabled()
    assert window.statusBar().currentMessage() == "Enquete encerrada"


def test_close_poll_declined_changes_nothing(qtbot, api, monkeypatch):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    window = open_window(qtbot, api)
    select(qtbot, window, 0)
    answer_question(monkeypatch, QMessageBox.StandardButton.No)

    window.close_button.click()

    assert not window.is_busy()
    assert api.get_poll(1)["status"] == "open"
    assert window.close_button.isEnabled()


# ------------------------------------------------------------------ criar enquete (CA20)
def test_create_poll_through_dialog_selects_it(qtbot, api, monkeypatch):
    window = open_window(qtbot, api)
    stub_dialog(
        monkeypatch,
        {"title": "Pizza?", "options": ["Calabresa", "Queijo", "Atum"], "type": "multiple"},
    )

    window.new_button.click()
    wait_idle(qtbot, window)

    assert [p["title"] for p in api.list_polls()] == ["Pizza?"]
    assert window.poll_list.count() == 1
    assert window.poll_list.currentRow() == 0
    assert window.title_label.text() == "Pizza?"
    assert len(window.vote_panel.findChildren(QCheckBox)) == 3
    assert window.statusBar().currentMessage() == "Enquete criada"


def test_cancelled_dialog_creates_nothing(qtbot, api, monkeypatch):
    window = open_window(qtbot, api)
    stub_dialog(monkeypatch, {"title": "X", "options": ["A", "B"], "type": "single"}, accepted=False)

    window.new_button.click()

    assert not window.is_busy()
    assert api.list_polls() == []


def test_invalid_poll_from_dialog_shows_server_error(qtbot, api, monkeypatch):
    window = open_window(qtbot, api)
    stub_dialog(monkeypatch, {"title": "", "options": ["A", "B"], "type": "single"})

    window.new_button.click()
    wait_idle(qtbot, window)

    assert window.error_label.text() == "Título é obrigatório"
    assert api.list_polls() == []


# ------------------------------------------------------------------ atualizar e seleção
def test_refresh_button_loads_polls_created_elsewhere(qtbot, api):
    window = open_window(qtbot, api)
    assert window.poll_list.count() == 0

    api.create_poll("Café?", ["Sim", "Não"], "single")
    window.refresh_button.click()
    wait_idle(qtbot, window)

    assert window.poll_list.count() == 1


def test_selection_is_preserved_on_refresh(qtbot, api):
    api.create_poll("Primeira", ["A", "B"], "single")
    api.create_poll("Segunda", ["A", "B"], "single")
    window = open_window(qtbot, api)
    select(qtbot, window, 1)

    api.create_poll("Terceira", ["A", "B"], "single")
    window.refresh_button.click()
    wait_idle(qtbot, window)

    assert window.poll_list.count() == 3
    assert window.poll_list.currentRow() == 1
    assert window.title_label.text() == "Segunda"


def test_stale_results_for_another_poll_are_ignored(qtbot, api):
    api.create_poll("Café?", ["Sim", "Não"], "single")
    window = open_window(qtbot, api)
    select(qtbot, window, 0)

    window._on_results_loaded(
        {"poll_id": 999, "status": "open", "total_votes": 5, "results": {"X": 5}}
    )

    assert window.results_widget.rows == [("Sim", 0), ("Não", 0)]


# ------------------------------------------------------------------ servidor fora do ar (CA22)
def test_server_down_shows_friendly_message_without_crashing(qtbot, monkeypatch):
    window = open_window(qtbot, ApiClient(closed_port_url(), timeout=2))

    assert not window.error_label.isHidden()
    assert "Não foi possível conectar" in window.error_label.text()
    assert window.poll_list.count() == 0
    assert window.title_label.text() == "Selecione uma enquete"

    stub_dialog(monkeypatch, {"title": "T", "options": ["A", "B"], "type": "single"})
    window.new_button.click()
    wait_idle(qtbot, window)
    assert "Não foi possível conectar" in window.error_label.text()
    assert window.isEnabled()


# ================================================================== VotePanel
@pytest.fixture
def panel(qtbot):
    parent = QWidget()  # com pai, set_poll() não abre uma janela solta
    qtbot.addWidget(parent)
    yield VotePanel(parent)  # yield mantém o pai vivo durante o teste (senão o Qt apaga o painel)


def test_panel_is_hidden_without_poll(panel):
    panel.set_poll(None)
    assert panel.isHidden()


def test_panel_reappears_when_a_poll_is_set(panel):
    panel.set_poll(None)
    panel.set_poll(poll_dict())
    assert not panel.isHidden()


def test_single_poll_shows_radio_buttons_and_hint(panel):
    panel.set_poll(poll_dict("single"))
    assert len(panel.findChildren(QRadioButton)) == 2
    assert panel.findChildren(QCheckBox) == []
    assert panel.hint_label.text() == "Escolha uma opção"


def test_single_choice_is_exclusive(panel):
    panel.set_poll(poll_dict("single"))
    buttons = option_buttons(panel)
    buttons["Sim"].click()
    buttons["Não"].click()
    assert panel.selected_options() == ["Não"]


def test_multiple_poll_allows_several_options(panel):
    panel.set_poll(poll_dict("multiple", options=("Uva", "Maçã", "Pera")))
    assert len(panel.findChildren(QCheckBox)) == 3
    assert panel.hint_label.text() == "Escolha uma ou mais opções"
    buttons = option_buttons(panel)
    buttons["Uva"].click()
    buttons["Pera"].click()
    assert sorted(panel.selected_options()) == ["Pera", "Uva"]


def test_closed_poll_disables_every_control(panel):
    panel.set_poll(poll_dict(status="closed"))
    assert panel.hint_label.text() == "Enquete encerrada: votação indisponível"
    assert not panel.submit_button.isEnabled()
    assert not panel.user_edit.isEnabled()
    assert all(not b.isEnabled() for b in option_buttons(panel).values())


def test_reopening_controls_for_an_open_poll(panel):
    panel.set_poll(poll_dict(status="closed"))
    panel.set_poll(poll_dict(status="open"))
    assert panel.submit_button.isEnabled()
    assert panel.user_edit.isEnabled()
    assert all(b.isEnabled() for b in option_buttons(panel).values())


def test_set_poll_replaces_previous_options(panel):
    panel.set_poll(poll_dict("multiple", options=("Uva", "Maçã", "Pera")))
    panel.set_poll(poll_dict("single", options=("Sim", "Não")))
    assert panel.findChildren(QCheckBox) == []
    assert set(option_buttons(panel)) == {"Sim", "Não"}


def test_submit_emits_trimmed_user_and_selection(qtbot, panel):
    panel.set_poll(poll_dict("single"))
    panel.user_edit.setText("  Ana ")
    option_buttons(panel)["Sim"].click()
    with qtbot.waitSignal(panel.submitted, timeout=1000) as blocker:
        panel.submit_button.click()
    assert blocker.args == ["Ana", ["Sim"]]


def test_submit_without_selection_emits_empty_list(qtbot, panel):
    panel.set_poll(poll_dict("single"))
    panel.user_edit.setText("Ana")
    with qtbot.waitSignal(panel.submitted, timeout=1000) as blocker:
        panel.submit_button.click()
    assert blocker.args == ["Ana", []]


def test_reset_clears_user_and_selection_for_checkboxes(panel):
    panel.set_poll(poll_dict("multiple", options=("Uva", "Maçã")))
    panel.user_edit.setText("Ana")
    for button in option_buttons(panel).values():
        button.click()
    panel.reset()
    assert panel.user_edit.text() == ""
    assert panel.selected_options() == []


def test_reset_clears_radio_buttons_and_keeps_them_exclusive(panel):
    panel.set_poll(poll_dict("single"))
    buttons = option_buttons(panel)
    buttons["Sim"].click()
    panel.reset()
    assert panel.selected_options() == []

    buttons["Sim"].click()
    buttons["Não"].click()
    assert panel.selected_options() == ["Não"]  # exclusividade restaurada


def test_user_field_is_limited_to_30_characters(panel):
    assert panel.user_edit.maxLength() == 30


# ================================================================== CreatePollDialog
def test_dialog_values_are_cleaned(qtbot):
    dialog = CreatePollDialog()
    qtbot.addWidget(dialog)
    dialog.title_edit.setText("  Café?  ")
    dialog.options_edit.setPlainText("Sim\n\n  Não  \n   \n")
    dialog.type_combo.setCurrentIndex(1)
    assert dialog.values() == {"title": "Café?", "options": ["Sim", "Não"], "type": "multiple"}


def test_dialog_defaults_to_single_choice(qtbot):
    dialog = CreatePollDialog()
    qtbot.addWidget(dialog)
    assert dialog.values() == {"title": "", "options": [], "type": "single"}


def test_dialog_ok_accepts_and_cancel_rejects(qtbot):
    dialog = CreatePollDialog()
    qtbot.addWidget(dialog)
    box = dialog.findChild(QDialogButtonBox)

    with qtbot.waitSignal(dialog.accepted, timeout=1000):
        box.button(QDialogButtonBox.StandardButton.Ok).click()
    with qtbot.waitSignal(dialog.rejected, timeout=1000):
        box.button(QDialogButtonBox.StandardButton.Cancel).click()


# ================================================================== ResultsWidget
@pytest.fixture
def results(qtbot):
    widget = ResultsWidget()
    qtbot.addWidget(widget)
    return widget


def sample_results(status="open"):
    return {
        "poll_id": 1,
        "status": status,
        "total_votes": 3,
        "results": {"Sim": 2, "Não": 1},
    }


def test_results_show_one_bar_per_option(results):
    results.show_results(sample_results())
    bars = results.findChildren(QProgressBar)
    assert results.rows == [("Sim", 2), ("Não", 1)]
    assert [b.value() for b in bars] == [2, 1]
    assert all(b.maximum() == 3 for b in bars)
    assert results.total_label.text() == "Total de votos: 3"


def test_results_without_votes_use_a_valid_bar_range(results):
    results.show_results(
        {"poll_id": 1, "status": "open", "total_votes": 0, "results": {"Sim": 0, "Não": 0}}
    )
    bars = results.findChildren(QProgressBar)
    assert [b.value() for b in bars] == [0, 0]
    assert all(b.maximum() == 1 for b in bars)


def test_closed_poll_is_flagged_in_total(results):
    results.show_results(sample_results("closed"))
    assert results.total_label.text() == "Total de votos: 3  (enquete encerrada)"


def test_showing_results_again_replaces_previous_rows(results):
    results.show_results(sample_results())
    results.show_results(
        {"poll_id": 2, "status": "open", "total_votes": 1, "results": {"Uva": 1, "Pera": 0, "Kiwi": 0}}
    )
    assert len(results.findChildren(QProgressBar)) == 3
    assert [option for option, _ in results.rows] == ["Uva", "Pera", "Kiwi"]


def test_clear_removes_rows_and_total(results):
    results.show_results(sample_results())
    results.clear()
    assert results.rows == []
    assert results.findChildren(QProgressBar) == []
    assert results.total_label.text() == ""
