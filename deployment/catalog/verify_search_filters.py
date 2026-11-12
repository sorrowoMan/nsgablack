#!/usr/bin/env python3
"""Exercise restored filters and category navigation against the live reader."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from unittest.mock import patch

from runtime import configure_reader


def verify():
    assert configure_reader(os.environ) == "only"
    from nsgablack.catalog import dashboard
    from nsgablack.catalog.curation_provider import DeepSeekGenerator
    from nsgablack.catalog.facade import catalog_summary, list_entries
    from nsgablack.units import UnitBinding
    from streamlit.testing.v1 import AppTest

    def forbidden(*args, **kwargs):
        raise AssertionError("Search verification attempted inference or Unit construction")

    def healthy(app):
        assert not app.exception, "Dashboard failed during filter navigation"

    def widget(elements, label):
        return next(item for item in elements if item.label == label)

    def tags(app, kind="adapter"):
        return app.session_state.filtered_state.get(f"catalog_ui::facet::framework::{kind}::tags", ())

    def app_for(profile, **query):
        app = AppTest.from_file(dashboard.__file__, default_timeout=90)
        app.query_params.update({"profile": profile, "kind": "adapter", **query})
        app.run()
        healthy(app)
        return app

    profiles, runs = {}, []
    with patch.object(DeepSeekGenerator, "generate", forbidden), patch.object(UnitBinding, "build", forbidden):
        for profile in ("default", "framework-core"):
            summary = catalog_summary(profile=profile, source_mode="only")
            counts = {}
            for kind, count in summary["by_kind"].items():
                actual = list_entries(profile=profile, kind=kind, limit=None, source_mode="only")
                assert len(actual) == count, "A category does not match the published database count"
                counts[kind] = count
            profiles[profile] = {"total": summary["total"], "by_kind": counts}

            app = app_for(profile, query="ns", f_tags="core")
            assert list(tags(app)) == ["core"]
            facet = next(item for item in app.multiselect if item.key.endswith("::adapter::tags"))
            facet.set_value([]).run()
            healthy(app)
            assert not tags(app) and "f_tags" not in app.query_params
            app.run()
            healthy(app)
            assert not tags(app)
            runs.append({"profile": profile, "scenario": "remove_restored_filter"})

            app = app_for(profile, query="ns", f_tags="core")
            widget(app.button, "清空字段筛选").click().run()
            healthy(app)
            assert not tags(app) and "f_tags" not in app.query_params
            assert app.session_state["catalog_ui_query"] == "ns"
            runs.append({"profile": profile, "scenario": "clear_restored_filters"})

            app = app_for(profile, query="ns", f_tags="core")
            widget(app.radio, "分类").set_value("all").run()
            healthy(app)
            assert not tags(app, "all") and "f_tags" not in app.query_params
            assert app.session_state["catalog_ui_query"] == ""
            assert "query" not in app.query_params
            runs.append({"profile": profile, "scenario": "category_filter_isolation"})

            app = app_for(profile, query="bias.tabu", f_tags="core")
            assert not any("其他分类里有结果" in item.value for item in app.info)
            widget(app.button, "清空字段筛选").click().run()
            healthy(app)
            assert any("其他分类里有结果" in item.value for item in app.info)
            next(item for item in app.button if item.key == "catalog_ui::switch_kind::framework::adapter::bias").click().run()
            healthy(app)
            assert app.session_state["catalog_ui_kind"] == "bias"
            assert "bias.tabu" in app.session_state["catalog_ui_result_keys"]
            widget(app.button, "重置搜索").click().run()
            healthy(app)
            assert app.session_state["catalog_ui_query"] == ""
            assert app.session_state["catalog_ui_field"] == "all"
            assert "query" not in app.query_params and not any(str(k).startswith("f_") for k in app.query_params)
            assert app.session_state["catalog_ui_result_keys"]
            runs.append({"profile": profile, "scenario": "honest_suggestions_switch_and_reset"})
    return {"ok": True, "backend": "mysql", "profiles": profiles, "scenarios": runs,
            "web_model_calls": 0, "unit_builds": 0}


def main():
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = verify()
        code = 0
    except Exception as exc:
        result, code = {"ok": False, "error_type": type(exc).__name__}, 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
