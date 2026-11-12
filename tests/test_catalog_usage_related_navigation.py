"""Every usage companion remains reachable, with a visible route back."""
import pytest

from nsgablack.adapters.unit_backed import UnitBackedAdapter
from nsgablack.catalog import dashboard
from nsgablack.catalog.facade import _entry_payload, list_entries, show_entry

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _forbidden(*args, **kwargs):
    raise AssertionError("Browsing usage must not build an algorithm Unit")


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_usage_lists_all_related_components_and_returns_without_switching_tabs(monkeypatch, profile):
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    monkeypatch.setenv("NSGABLACK_CATALOG_KNOWLEDGE_ENABLED", "0")
    monkeypatch.delenv("NSGABLACK_CATALOG_EXAMPLES_INDEX", raising=False)
    monkeypatch.setattr(UnitBackedAdapter, "ensure_unit", _forbidden)
    monkeypatch.setattr(dashboard._examples, "render_examples", lambda st, entry, **kwargs: None)
    origin = _entry_payload(show_entry("adapter.vns", profile=profile, source_mode="off"))
    rows = [_entry_payload(item) for item in list_entries(profile=profile, kind="adapter", source_mode="off", limit=None)
            if item.key != origin["key"]][:7]
    assert len(rows) == 7
    entries = {item["key"]: item for item in [origin, *rows]}
    neighbors = {"relation_groups": {"assembly_uses": rows}, "companions": rows[:2]}
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from nsgablack.catalog.dashboard import _render_detail\n"
        f"entries = {entries!r}\n"
        f"origin = {origin!r}\n"
        f"neighbors = {neighbors!r}\n"
        f"st.session_state.setdefault('catalog_ui_profile', {profile!r})\n"
        "st.session_state.setdefault('catalog_ui_scope', 'framework')\n"
        "st.session_state.setdefault('catalog_ui_selected', origin['key'])\n"
        "entry = entries[st.session_state['catalog_ui_selected']]\n"
        "_render_detail(st, entry=entry, neighbors=neighbors if entry == origin else None,\n"
        "    source_info={}, deep_link_query='', scope='framework', kind=entry['kind'],\n"
        "    detail_tab='overview', expanded_relation_groups=())\n",
        default_timeout=40,
    ).run()
    assert not app.exception
    related = [item for item in app.button if "::usage_related::" in str(item.key)]
    assert len(related) == 7  # Duplicate companions do not consume visible slots.
    more = next(item for item in app.expander if item.label == "查看其余 2 个关联组件（共 7 个）")
    assert not more.proto.expanded
    assert [item.label for item in more.button] == [item["title"] for item in rows[5:]]
    assert any("不表示必须全部启用" in item.value for item in app.caption)
    target = rows[-1]
    next(item for item in more.button if str(item.key).endswith("::" + target["key"])).click().run()
    assert not app.exception
    assert app.session_state["catalog_ui_selected"] == target["key"]
    assert app.query_params["detail_tab"] in ("overview", ["overview"])
    back = next(item for item in app.button if str(item.key).startswith("catalog_ui::stack::"))
    assert origin["key"] in back.label
    back.click().run()
    assert not app.exception
    assert app.session_state["catalog_ui_selected"] == origin["key"]
    assert len([item for item in app.button if "::usage_related::" in str(item.key)]) == 7


@pytest.mark.parametrize("tab", ["overview", "interface", "relations", "source"])
def test_navigation_stack_is_rendered_once_in_each_detail_tab(monkeypatch, tab):
    """Use the real widget tree so duplicate Streamlit keys are a regression."""
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_KNOWLEDGE_ENABLED", "0")
    monkeypatch.setattr(dashboard._examples, "render_examples", lambda st, entry, **kwargs: None)
    monkeypatch.setattr(dashboard._curation, "render_note", lambda *args, **kwargs: None)
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from nsgablack.catalog.dashboard import _render_detail, _NAV_STACK_KEY\n"
        "st.session_state[_NAV_STACK_KEY] = [{'key': 'adapter.vns', 'title': 'VNS', 'kind': 'adapter'}]\n"
        "_render_detail(st, entry={'key': 'adapter.fixed_candidate', 'kind': 'adapter', 'import_path': ''},\n"
        "    neighbors={}, source_info={}, deep_link_query='', scope='framework', kind='adapter',\n"
        f"    detail_tab={tab!r}, expanded_relation_groups=())\n",
        default_timeout=40,
    ).run()
    assert not app.exception
    assert len([item for item in app.button if str(item.key).startswith("catalog_ui::stack::")]) == 1
