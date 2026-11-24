from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs

import pytest

from nsgablack.catalog import dashboard
from nsgablack.catalog.guidance import WIRING_STATUS_NOTE
from nsgablack.catalog.registry import CatalogEntry


class _TextView:
    def __init__(self):
        self.output = []

    def markdown(self, value, **kwargs):
        self.output.append(str(value))

    def caption(self, value):
        self.output.append(str(value))


@pytest.fixture
def declared_entry(monkeypatch):
    class Example:
        def __init__(self, *, scale=1.0):
            raise AssertionError("Catalog presentation must not construct the component")

    monkeypatch.setattr(CatalogEntry, "load", lambda self: Example)
    return CatalogEntry(
        key="tool.example_guidance",
        title="Example",
        kind="tool",
        import_path="example:Example",
        use_when=("需要替换变化算子时",),
        minimal_wiring=("operator = Example(scale=0.5)",),
        config_keys=("scale",),
        contract={"catalog": {
            "role": "variation",
            "concepts": ["变化", "解池"],
            "operations": ["propose"],
            "boundaries": ["只提出候选，不执行真实求值"],
        }},
    )


def test_detail_payload_preserves_guidance_and_separates_configuration(declared_entry):
    payload = dashboard._entry_detail_payload(declared_entry)
    assert payload["kind"] == "tool"
    assert payload["role"] == "variation"
    assert payload["concepts"] == ("变化", "解池")
    assert payload["config_keys"] == ("scale",)
    assert payload["operations"] == ("propose",)
    assert payload["boundaries"] == ("只提出候选，不执行真实求值",)
    assert payload["wiring_status"] == "signature-checked"

    view = _TextView()
    dashboard._render_usage_overview(view, payload)
    rendered = "\n".join(view.output)
    assert rendered.index("适用场景") < rendered.index("最小接线") < rendered.index("运行方法")
    assert rendered.index("支持边界") < rendered.index("职责") < rendered.index("相关概念")
    assert rendered.index("运行方法") < rendered.index(">propose<") < rendered.index("装配配置")
    assert rendered.index("装配配置") < rendered.index(">scale<") < rendered.index("配方结构状态")
    assert "仅签名检查" in rendered
    assert WIRING_STATUS_NOTE in rendered


@pytest.mark.parametrize(("status", "label"), [
    ("guidance", "使用说明"),
    ("template", "需填写依赖"),
    ("signature-checked", "仅签名检查"),
    ("unverified", "尚未验证"),
    ("invalid", "签名不匹配"),
    ("unexpected-status", "尚未验证（未知状态）"),
])
def test_overview_distinguishes_structural_status_from_execution(status, label):
    view = _TextView()
    dashboard._render_usage_overview(view, {"wiring_status": status, "wiring_notes": ("检查详情",)})
    assert label in view.output
    assert "检查详情" in view.output
    assert WIRING_STATUS_NOTE in view.output


@pytest.mark.parametrize("query", ["", "解池"])
def test_guidance_filters_roundtrip_and_reach_existing_query(monkeypatch, declared_entry, query):
    filters = {"concepts": ("解池",), "role": ("variation",)}
    link = dashboard._build_deep_link_query(
        profile="framework-core", scope="framework", kind="tool", query=query,
        field="usage", selected=declared_entry.key, project_path="", include_global=False,
        db_path="", source_mode="off", sort_by="default", sort_dir="asc",
        detail_tab="interface", open_relations="", column_mode="standard",
        page_size=50, results_collapse="expanded", field_filters=filters,
    )
    params, restored_filters = dashboard._read_query_params(
        SimpleNamespace(query_params={key: values[-1] for key, values in parse_qs(link[1:]).items()})
    )
    assert params["kind"] == "tool"
    assert params["detail_tab"] == "interface"
    assert restored_filters == filters
    assert set(filters).issubset(dashboard._PRIMARY_FILTER_FIELDS)
    assert dashboard._field_label("concepts") == "相关概念"
    assert dashboard._field_label("role") == "职责"
    calls = []

    def read_entries(*args, **kwargs):
        calls.append((args, kwargs))
        return [declared_entry]

    monkeypatch.setattr(dashboard, "list_entries", read_entries)
    monkeypatch.setattr(dashboard, "search_entries", read_entries)
    rows = dashboard._load_items(
        params["profile"], params["scope"], "", False, params["kind"], query,
        params["field"], tuple(restored_filters.items()), "", "off",
    )
    assert rows[0]["key"] == declared_entry.key
    assert calls[0][1]["field_filters"] == {"concepts": "解池", "role": "variation"}
    assert calls[0][1]["kind"] == "tool"


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_cli_show_displays_guidance_without_running_component(monkeypatch, capsys, declared_entry, profile):
    import nsgablack.catalog as catalog
    from nsgablack.__main__ import main

    reads = []

    def show_entry(key, **kwargs):
        reads.append((key, kwargs))
        return declared_entry

    monkeypatch.setattr(catalog, "show_entry", show_entry)
    assert main(["catalog", "show", declared_entry.key, "--profile", profile]) == 0
    output = capsys.readouterr().out
    assert "职责 (role): variation" in output
    assert "相关概念 (concepts):\n  - 变化\n  - 解池" in output
    assert "运行方法 (operations):\n  - propose" in output
    assert "装配配置 (config_keys):\n  - scale" in output
    assert "支持边界 (boundaries):\n  - 只提出候选，不执行真实求值" in output
    assert "配方结构状态 (wiring_status): 仅签名检查 [signature-checked]" in output
    assert WIRING_STATUS_NOTE in output
    assert reads == [(declared_entry.key, {"profile": profile, "scope": "framework"})]


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_local_catalog_guidance_is_accessible_by_existing_facets(profile):
    facets = dashboard._load_facets(profile, "framework", "", False, "tool", "", "all", "", "off")
    assert any(row["value"] == "model" for row in facets["facets"]["role"])
    assert any(row["value"] == "贝叶斯优化" for row in facets["facets"]["concepts"])
    rows = dashboard._load_items(
        profile, "framework", "", False, "tool", "", "all",
        (("concepts", ("贝叶斯优化",)), ("role", ("model",))), "", "off",
    )
    assert any(row["key"] == "tool.bo_model" for row in rows)
    selected = dashboard._load_selected_entry(profile, "framework", "", False, "tool.bo_model", "", "off")
    assert selected["role"] == "model"
    assert "fit" in selected["operations"]
    assert selected["boundaries"]
