#!/usr/bin/env python3
"""Verify browse groups with the published reader, without inference or builds."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from unittest.mock import patch

from runtime import configure_reader


def verify():
    assert configure_reader(os.environ) == "only"
    from nsgablack.catalog import dashboard, navigation
    from nsgablack.catalog.curation_provider import DeepSeekGenerator
    from nsgablack.catalog.facade import catalog_summary, list_entries, search_entries
    from nsgablack.units import UnitBinding
    from streamlit.testing.v1 import AppTest

    def forbidden(*args, **kwargs):
        raise AssertionError("Navigation attempted inference or Unit construction")

    def healthy(app):
        assert not app.exception, "Dashboard failed during grouped navigation"

    def widget(elements, label):
        return next(item for item in elements if item.label == label)

    def app_for(profile, **query):
        app = AppTest.from_file(dashboard.__file__, default_timeout=90)
        app.query_params.update({"profile": profile, "page_size": "250", **query})
        app.run()
        healthy(app)
        assert len(widget(app.radio, "分类").options) <= 9
        return app

    profiles, scenarios = {}, []
    with patch.object(DeepSeekGenerator, "generate", forbidden), patch.object(DeepSeekGenerator, "_complete", forbidden), patch.object(UnitBinding, "build", forbidden):
        for profile in ("default", "framework-core"):
            summary = catalog_summary(profile=profile, source_mode="only")
            entries = list_entries(profile=profile, source_mode="only", limit=None)
            by_kind = summary["by_kind"]
            group_counts = navigation.group_counts(by_kind)
            seen = set()
            for group in navigation.PRIMARY_OPTIONS[1:]:
                expected = {entry.key for entry in entries if navigation.contains_kind(group, entry.kind)}
                actual = dashboard._load_items(profile, "framework", "", False, group, "", "all", (), "", "only")
                keys = {entry["key"] for entry in actual}
                assert keys == expected and not seen.intersection(keys), "Group partition changed component membership"
                seen.update(keys)
                facets = dashboard._load_facets(profile, "framework", "", False, group, "", "all", "", "only")
                assert len(keys) == group_counts[group] == facets["total"], "Group count differs across reads"
            assert seen == {entry.key for entry in entries}
            assert group_counts["all"] == len(entries) == summary["total"]
            assert sum(value for key, value in group_counts.items() if key != "all") == len(entries)
            if profile == "framework-core":
                assert group_counts["group:learning"] == 0
            profiles[profile] = {"total": summary["total"], "groups": group_counts}

            # Concrete-kind deep links remain valid and highlight their parent.
            app = app_for(profile, kind="codec", query="linear")
            assert app.session_state["catalog_ui_kind"] == "codec"
            assert app.session_state["catalog_ui::browse_kind"] == "group:model"
            assert app.session_state["catalog_ui::browse_subkind"] == "codec"
            actual_options = widget(app.selectbox, "组件类型").options
            expected_options = {f"本组全部 · {group_counts['group:model']}"} | {
                f"{dashboard._kind_label(kind)} · {by_kind[kind]}"
                for kind in navigation.member_kinds("group:model", tuple(by_kind))}
            assert set(actual_options) == expected_options, "Secondary types leaked other groups"

            widget(app.radio, "分类").set_value("group:runtime").run()
            healthy(app)
            assert app.session_state["catalog_ui_kind"] == "group:runtime"
            assert app.session_state["catalog_ui_query"] == "" and "query" not in app.query_params
            assert len(app.session_state["catalog_ui_result_keys"]) == group_counts["group:runtime"]
            widget(app.selectbox, "组件类型").set_value("plugin").run()
            healthy(app)
            assert app.session_state["catalog_ui_kind"] == "plugin"
            assert len(app.session_state["catalog_ui_result_keys"]) == by_kind["plugin"]
            widget(app.radio, "分类").set_value("all").run()
            healthy(app)
            assert app.session_state["catalog_ui_kind"] == "all"
            assert not any(item.label == "组件类型" for item in app.selectbox)
            scenarios.append({"profile": profile, "scenario": "old_links_primary_and_secondary"})

            app = app_for(profile, kind="group:model", query="linear")
            expected = search_entries("linear", profile=profile, source_mode="only", limit=1000,
                field_filters={"kind": navigation.member_kinds("group:model", tuple(by_kind))})
            assert set(app.session_state["catalog_ui_result_keys"]) == {entry.key for entry in expected}
            assert app.session_state["catalog_ui_kind"] == "group:model"
            assert "group:model" in str(app.query_params.get("kind", ""))
            scenarios.append({"profile": profile, "scenario": "group_search_restorable_url"})

            app = app_for(profile, kind="group:search", query="bias.tabu")
            assert any("其他分类里有结果" in item.value for item in app.info)
            next(item for item in app.button
                 if item.key == "catalog_ui::switch_kind::framework::group:search::group:problem").click().run()
            healthy(app)
            assert app.session_state["catalog_ui_kind"] == "group:problem"
            assert app.session_state["catalog_ui_query"] == "bias.tabu"
            assert "bias.tabu" in app.session_state["catalog_ui_result_keys"]
            widget(app.radio, "分类").set_value("group:pipeline").run()
            healthy(app)
            assert app.session_state["catalog_ui_query"] == ""
            assert len(app.session_state["catalog_ui_result_keys"]) == group_counts["group:pipeline"]
            scenarios.append({"profile": profile, "scenario": "honest_group_suggestion_and_full_browse"})

            # Authored migration links lead to the actual tutorial, including
            # sources without Python calls. Shared host continuations must not
            # mix the two destination books into one group.
            origin = "mlblack.nsgablack_symbolic.orthogonal_basis_outer"
            target = "mlblack.representation.symbolic_expression"
            app = app_for(profile, kind="all", selected=origin, detail_tab="overview")
            fixed = next(item for item in app.expander if item.label == "固定符号/基集合Case · 11 个组件")
            function_pool = next(item for item in app.expander if item.label == "函数池实际消费 · 9 个组件")
            def reference_keys(container):
                return {str(item.key).rsplit("::", 1)[-1] for item in container.button
                        if "::tutorial_reference::" in str(item.key)}
            assert len(reference_keys(fixed)) == 11 and len(reference_keys(function_pool)) == 9
            assert not reference_keys(fixed).intersection(reference_keys(function_pool))
            next(item for item in fixed.button if str(item.key).endswith("::" + target)).click().run()
            healthy(app)
            assert app.session_state["catalog_ui_selected"] == target
            assert app.query_params["detail_tab"] in ("overview", ["overview"])
            next(item for item in app.button if str(item.key).startswith("catalog_ui::stack::")
                 and str(item.key).endswith("::" + origin)).click().run()
            healthy(app)
            assert app.session_state["catalog_ui_selected"] == origin
            scenarios.append({"profile": profile, "scenario": "migration_tutorial_handoff_and_return",
                              "fixed_tutorial_components": 11, "function_pool_components": 9})

    return {"ok": True, "backend": "mysql", "primary_options": len(navigation.PRIMARY_OPTIONS),
            "profiles": profiles, "scenarios": scenarios, "web_model_calls": 0, "unit_builds": 0}


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
