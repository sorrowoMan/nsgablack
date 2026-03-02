from __future__ import annotations

from typing import Any, Dict, List

from nsgablack.utils.viz.ui.context_view import ContextView


class _DummyButton:
    def __init__(self) -> None:
        self.state = "disabled"

    def configure(self, **kwargs: Any) -> None:
        if "state" in kwargs:
            self.state = str(kwargs["state"])


class _DummyTree:
    def __init__(self) -> None:
        self._rows: List[tuple] = []
        self._sel: List[str] = []

    def get_children(self) -> List[str]:
        return [str(i) for i in range(len(self._rows))]

    def delete(self, item_id: str) -> None:
        idx = int(item_id)
        if 0 <= idx < len(self._rows):
            self._rows.pop(idx)

    def insert(self, _parent: str, _where: str, values: tuple) -> None:
        self._rows.append(tuple(values))

    def selection(self) -> List[str]:
        return list(self._sel)

    def selection_set(self, item_id: str) -> None:
        self._sel = [str(item_id)]

    def item(self, item_id: str) -> Dict[str, tuple]:
        return {"values": self._rows[int(item_id)]}


class _DummyWindow:
    def winfo_exists(self) -> bool:
        return True

    def deiconify(self) -> None:
        return None

    def lift(self) -> None:
        return None


class _DummyApp:
    def __init__(self) -> None:
        self.called: List[str] = []
        self.catalog = {}

    def show_component_detail(self, name: str) -> None:
        self.called.append(str(name))

    def _set_status(self, _msg: str) -> None:
        return None


def _make_view() -> ContextView:
    view = ContextView.__new__(ContextView)
    view.app = _DummyApp()
    view._declared_writers = {}
    view._declared_readers = {}
    view._runtime_writers = {}
    view._component_contracts = {}
    view._missing_requires_by_component = {}
    view._selected_key = ""
    view._field_selected_component = ""
    view._field_window = _DummyWindow()
    view._field_summary_var = None
    view._field_providers_tree = _DummyTree()
    view._field_consumers_tree = _DummyTree()
    view._field_component_text = None
    view._field_notes_text = None
    view._declared_cache_solver_ref = None
    view._declared_cache_data = ({}, {}, {})
    view._catalog_intro_cache = {}
    view._catalog_intro_cache_size = -1
    view._refresh_pending_id = None
    view._refresh_min_interval_sec = 0.0
    view._last_refresh_ts = 0.0
    view.provider_btn = _DummyButton()
    view.consumer_btn = _DummyButton()
    view.field_window_btn = _DummyButton()
    view.error_var = type("_Var", (), {"set": lambda self, _v: None})()
    view._detail_lines: List[str] = []
    view._detail = object()
    view._set_text = lambda _widget, text: view._detail_lines.append(str(text))  # type: ignore[assignment]
    view._refresh_field_window_calls = 0
    view._refresh_field_window = lambda: setattr(view, "_refresh_field_window_calls", view._refresh_field_window_calls + 1)  # type: ignore[assignment]
    return view


def test_context_select_triggers_field_refresh_and_enables_buttons() -> None:
    view = _make_view()
    view._declared_writers = {"generation": ["solver.core"]}
    view._declared_readers = {"generation": ["adapter.main"]}
    view._runtime_writers = {"generation": "solver.core (builtin)"}

    view._set_selected_key("generation")

    assert view.provider_btn.state == "normal"
    assert view.consumer_btn.state == "normal"
    assert view.field_window_btn.state == "normal"
    assert view._refresh_field_window_calls == 1
    assert any("key: generation" in line for line in view._detail_lines)


def test_field_window_refresh_populates_provider_consumer_rows() -> None:
    view = _make_view()
    view._selected_key = "generation"
    view._declared_writers = {"generation": ["solver.core"]}
    view._declared_readers = {"generation": ["adapter.*"]}
    view._runtime_writers = {"generation": "solver.core (builtin)"}
    view._component_contracts = {
        "adapter.unit.explorer#0:MOEADAdapter": {
            "requires": ["population_ref"],
            "provides": ["generation"],
            "mutates": [],
            "cache": [],
            "notes": [],
        },
        "plugin.console_progress:ConsoleProgressPlugin": {
            "requires": ["generation"],
            "provides": [],
            "mutates": [],
            "cache": [],
            "notes": [],
        },
    }

    # Restore real method for this test.
    view._refresh_field_window = ContextView._refresh_field_window.__get__(view, ContextView)  # type: ignore[assignment]
    view._refresh_field_window()

    providers = view._field_providers_tree._rows
    consumers = view._field_consumers_tree._rows
    assert ("adapter.unit.explorer#0:MOEADAdapter", "provides") in providers
    assert any(row[0] == "plugin.console_progress:ConsoleProgressPlugin" and row[1] == "requires" for row in consumers)


def test_double_click_component_opens_main_details() -> None:
    view = _make_view()
    view._field_selected_component = "adapter.unit.explorer#0:MOEADAdapter"

    ContextView._open_selected_component_detail(view)

    assert view.app.called == ["adapter.unit.explorer#0:MOEADAdapter"]


def test_context_select_open_window_and_jump_details_flow() -> None:
    view = _make_view()
    view._selected_key = "generation"
    view._declared_writers = {"generation": ["solver.core"]}
    view._declared_readers = {"generation": ["adapter.*"]}
    view._runtime_writers = {"generation": "solver.core (builtin)"}
    view._component_contracts = {
        "adapter.unit.explorer#0:MOEADAdapter": {
            "requires": ["population_ref"],
            "provides": ["generation"],
            "mutates": [],
            "cache": [],
            "notes": [],
        }
    }

    view._field_window = None

    def _fake_build_field_window() -> None:
        view._field_window = _DummyWindow()
        view._field_summary_var = type("_Var", (), {"set": lambda self, _v: None})()
        view._field_providers_tree = _DummyTree()
        view._field_consumers_tree = _DummyTree()
        view._field_component_text = object()
        view._field_notes_text = object()

    view._build_field_window = _fake_build_field_window  # type: ignore[assignment]
    view._refresh_field_window = ContextView._refresh_field_window.__get__(view, ContextView)  # type: ignore[assignment]

    ContextView._open_field_window(view, "providers")

    assert view._field_providers_tree is not None
    assert view._field_providers_tree.get_children()

    view._field_providers_tree.selection_set("0")
    ContextView._on_field_component_select(view, view._field_providers_tree)
    ContextView._open_selected_component_detail(view)

    assert view.app.called == ["adapter.unit.explorer#0:MOEADAdapter"]
