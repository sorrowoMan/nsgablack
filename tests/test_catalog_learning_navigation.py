"""Real browse interactions for usage prerequisites and evidence-backed links."""
import pytest

from nsgablack.catalog import dashboard, registry

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


@pytest.fixture
def page(monkeypatch):
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    monkeypatch.setenv("NSGABLACK_CATALOG_PROVIDERS", "mlblack=mlblack.catalog.registry:get_catalog")
    monkeypatch.setenv("NSGABLACK_CATALOG_KNOWLEDGE_ENABLED", "0")
    monkeypatch.delenv("NSGABLACK_CATALOG_EXAMPLES_INDEX", raising=False)
    for name in ("_cached_summary", "_cached_schema", "_cached_source_info", "_cached_items", "_cached_facets",
                 "_cached_selected", "_cached_neighbors", "_cached_other_kind_hits"):
        getattr(dashboard, name).cache_clear()
    registry.get_source_catalog(profile="framework-core", refresh=True)
    return AppTest.from_string("from nsgablack.catalog.dashboard import run_dashboard\n"
                              "run_dashboard(['--profile','framework-core','--source-mode','off'])",
                              default_timeout=90)


def test_actual_wiring_relation_opens_target_usage_and_preserves_back_navigation(page):
    page.query_params.update({"kind": "adapter", "selected": "adapter.vns", "detail_tab": "relations"})
    page.run()
    assert not page.exception
    group = next(item for item in page.expander if item.label.startswith("用法片段使用了"))
    assert group.proto.expanded
    assert any(item.label == "查看这条关系的依据" for item in page.expander)
    button = next(item for item in page.button if "::assembly_uses::" in str(item.key)
                  and str(item.key).endswith("::repr.context_gaussian"))
    assert button.label == "查看用法"
    button.click().run()
    assert not page.exception
    assert page.session_state["catalog_ui_selected"] == "repr.context_gaussian"
    assert page.query_params["detail_tab"] in ("overview", ["overview"])
    assert any("放在哪" in item.value for item in page.markdown)
    next(item for item in page.button if item.label == "返回上一个").click().run()
    assert not page.exception
    assert page.session_state["catalog_ui_selected"] == "adapter.vns"


def test_ml_declared_feedback_consumers_are_reachable_in_relations(page):
    page.query_params.update({"kind": "all", "selected": "mlblack.core.learning", "detail_tab": "relations"})
    page.run()
    assert not page.exception
    assert any("feedback.objectives" in item.label for item in page.expander)
    assert any(str(item.key).endswith("::mlblack.bias.objective_weight") for item in page.button)


def test_plain_fragment_explains_solver_before_mounting_code(page):
    page.query_params.update({"kind": "adapter", "selected": "adapter.fixed_candidate", "detail_tab": "overview"})
    page.run()
    assert not page.exception
    prose = "\n".join(item.value for item in page.markdown)
    assert "build_solver()" in prose
    assert "return solver" in prose
    assert any(item.label.startswith("第一次装配") for item in page.expander)
