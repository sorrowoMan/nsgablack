#!/usr/bin/env python3
"""Read-only acceptance of the deployed dashboard against its real MySQL source."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from runtime import configure_reader


class VerificationError(RuntimeError):
    pass


def require(condition: object, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def query_value(app, key: str) -> str:
    value = app.query_params.get(key, "")
    return str(value[-1] if isinstance(value, list) else value)


def result_keys(app) -> set[str]:
    keys = tuple(app.session_state["catalog_ui_result_keys"])
    require(len(keys) == len(set(keys)), "Dashboard list duplicated component identities")
    if keys:
        lists = [item for item in app.radio if str(item.key).startswith("catalog_ui::component_list::")]
        require(len(lists) == 1 and len(lists[0].options) == len(keys),
                "Dashboard did not render its selectable component list")
    return set(keys)


def run_app(AppTest, dashboard_path: Path, *, profile: str, kind: str, query: str, selected: str = ""):
    # Execute the actual deployed entrypoint, including its normal CLI parsing.
    app = AppTest.from_file(str(dashboard_path), default_timeout=90)
    app.query_params.update({"profile": profile, "scope": "framework", "kind": kind,
                             "query": query, "selected": selected})
    app.run()
    require(not app.exception, "Dashboard raised an exception")
    for key, expected in (("profile", profile), ("kind", kind), ("query", query)):
        require(app.session_state[f"catalog_ui_{key}"] == expected,
                f"Dashboard did not apply requested {key}")
        require(query_value(app, key) == expected, f"Dashboard URL lost requested {key}")
    require(app.session_state["catalog_ui_source_mode"] == "only",
            "Dashboard did not retain its deployment-owned database source")
    return app


def verify_cross_kind(AppTest, dashboard_path: Path, profile: str) -> dict[str, object]:
    app = run_app(AppTest, dashboard_path, profile=profile, kind="adapter", query="bias.tabu")
    require(any("当前分类没有命中，但其他分类里有结果" in item.value for item in app.info),
            "Empty-category search did not offer results from another category")
    require(not result_keys(app), "The expected empty adapter search unexpectedly returned rows")
    buttons = [button for button in app.button
               if button.key == "catalog_ui::switch_kind::framework::adapter::bias"]
    require(len(buttons) == 1, "Dashboard did not offer the bias category switch")
    buttons[0].click().run()
    require(not app.exception, "Dashboard raised after switching category")
    require(app.session_state["catalog_ui_kind"] == "bias" and query_value(app, "kind") == "bias",
            "Category switch did not update both session and URL")
    require(app.session_state["catalog_ui_query"] == "bias.tabu" and query_value(app, "query") == "bias.tabu",
            "Category switch lost the search query")
    keys = result_keys(app)
    require(any(key.startswith("bias.tabu") for key in keys),
            "Switched category did not show the requested bias")
    return {"query": "bias.tabu", "switch": "adapter->bias", "results": len(keys), "app_runs": 2}


def verify_ml_entry(AppTest, dashboard_path: Path, facade, *, profile: str, original_key: str) -> dict[str, object]:
    key = "mlblack." + original_key
    hits = facade.search_entries(original_key, profile=profile, scope="framework", source_mode="only", limit=100)
    require(any(entry.key == key for entry in hits), "ML search did not find its database identity")
    entry = facade.show_entry(key, profile=profile, scope="framework", source_mode="only")
    require(entry is not None and entry.key == key, "ML database detail is missing")
    require(entry.metadata.get("catalog_framework") == "mlblack"
            and entry.metadata.get("catalog_original_key") == original_key,
            "ML database detail lost its owning framework or original key")
    app = run_app(AppTest, dashboard_path, profile=profile, kind="all", query=original_key, selected=key)
    require(key in result_keys(app), "Dashboard ML search did not display its database identity")
    require(app.session_state["catalog_ui_selected"] == key and query_value(app, "selected") == key,
            "Dashboard did not retain the requested ML selection")
    require(any("catalog-entry-key" in item.value and key in item.value for item in app.markdown),
            "Dashboard did not render the selected ML detail")
    next(item for item in app.radio if item.label == "详情 Tab").set_value("interface").run()
    require(not app.exception and query_value(app, "detail_tab") == "interface",
            "Dashboard did not open its restorable interface section")
    require(any(item.label == "原始组件声明" for item in app.expander),
            "Dashboard did not expose the owning framework declarations")
    require(any("catalog_original_key" in str(item.value) and original_key in str(item.value) for item in app.json),
            "Dashboard did not render the original ML contract and metadata")
    next(item for item in app.radio if item.label == "详情 Tab").set_value("overview").run()
    require(not app.exception and query_value(app, "detail_tab") == "overview",
            "Dashboard could not return from interface to usage")
    require(app.session_state["catalog_ui_selected"] == key,
            "Returning to usage lost the selected ML component")
    return {"key": key, "kind": entry.kind, "app_runs": 3}


def verify_related_usage(AppTest, dashboard_path: Path, facade, profile: str) -> dict[str, object]:
    source_key, target_key = "adapter.vns", "repr.context_gaussian"
    neighbors = facade.catalog_neighbors(source_key, profile=profile, scope="framework", source_mode="only")
    require(neighbors is not None and any(row["key"] == target_key for row in neighbors.get("companions", ())),
            "MySQL VNS declaration lost its ContextGaussian companion")
    app = run_app(AppTest, dashboard_path, profile=profile, kind="adapter", query=source_key, selected=source_key)
    next(item for item in app.radio if item.label == "详情 Tab").set_value("relations").run()
    require(not app.exception and query_value(app, "detail_tab") == "relations", "VNS relation page did not open")
    require(any(item.label.startswith("目录声明的配套组件") and item.proto.expanded for item in app.expander),
            "Companion relations are not expanded by default")
    if neighbors.get("relation_groups", {}).get("assembly_uses"):
        require(any(item.label.startswith("用法片段使用了") and item.proto.expanded for item in app.expander),
                "Usage assembly relations are not expanded by default")
        proofs = [item for item in app.expander if item.label == "查看这条关系的依据"]
        require(proofs and all(not item.proto.expanded for item in proofs),
                "Assembly evidence must remain available in collapsed details")
    overview = [item for item in app.expander if item.label == "查看上下文、Artifact 与阶段契约概览"]
    require(overview and all(not item.proto.expanded for item in overview), "Contract overview is not collapsed")
    relation_group = "assembly_uses" if neighbors.get("relation_groups", {}).get("assembly_uses") else "companions"
    buttons = [item for item in app.button if str(item.key).startswith(f"catalog_ui::jump::{source_key}::{relation_group}::")
               and str(item.key).endswith("::" + target_key)]
    require(len(buttons) == 1 and buttons[0].label == "查看用法", "VNS companion has no direct usage navigation")
    buttons[0].click().run()
    require(not app.exception and app.session_state["catalog_ui_selected"] == target_key
            and query_value(app, "selected") == target_key and query_value(app, "detail_tab") == "overview",
            "Companion jump did not select ContextGaussian usage in session and URL")
    require(any("ContextGaussianMutation" in item.value for item in app.code),
            "ContextGaussian usage omitted its actual component call")
    back = [item for item in app.button if item.label == "返回上一个"]
    require(len(back) == 1, "Related usage has no return navigation")
    back[0].click().run()
    require(not app.exception and app.session_state["catalog_ui_selected"] == source_key
            and query_value(app, "selected") == source_key and app.session_state["catalog_ui_kind"] == "adapter",
            "Return navigation did not restore the original VNS identity and category")
    require(app.session_state["catalog_ui_source_mode"] == "only", "Relation navigation lost the MySQL reader")
    return {"source": source_key, "target": target_key, "returned": source_key, "app_runs": 4}


def verify_ml_contract(AppTest, dashboard_path: Path, facade, profile: str) -> dict[str, object]:
    source_key, target_key = "mlblack.core.learning", "mlblack.bias.objective_policy"
    entry = facade.show_entry(source_key, profile=profile, scope="framework", source_mode="only")
    require(entry is not None and "feedback.objectives" in entry.context_provides
            and "candidate.model" in entry.context_requires,
            "MySQL ML contract was not published in the shared Catalog fields")
    neighbors = facade.catalog_neighbors(source_key, profile=profile, scope="framework", source_mode="only")
    relation = "context_provides::feedback.objectives"
    require(neighbors is not None and any(row["key"] == target_key
                                         for row in neighbors.get("relation_groups", {}).get(relation, ())),
            "MySQL ML objective contract has no actual objective-policy consumer")
    app = run_app(AppTest, dashboard_path, profile=profile, kind="all", query=source_key, selected=source_key)
    next(item for item in app.radio if item.label == "详情 Tab").set_value("relations").run()
    require(not app.exception and any("feedback.objectives" in item.label for item in app.expander),
            "ML objective contract consumer was not displayed in the relation page")
    buttons = [item for item in app.button
               if str(item.key).startswith(f"catalog_ui::jump::{source_key}::{relation}::")
               and str(item.key).endswith("::" + target_key)]
    require(len(buttons) == 1 and buttons[0].label == "查看用法", "ML contract consumer has no usage navigation")
    buttons[0].click().run()
    require(not app.exception and app.session_state["catalog_ui_selected"] == target_key
            and query_value(app, "selected") == target_key and query_value(app, "detail_tab") == "overview",
            "ML objective consumer navigation did not open its usage page")
    require(app.session_state["catalog_ui_source_mode"] == "only", "ML contract navigation lost the MySQL reader")
    return {"source": source_key, "consumer": target_key, "contract": "feedback.objectives", "app_runs": 3}


def verify_risk_usage(AppTest, dashboard_path: Path, profile: str) -> dict[str, object]:
    app = run_app(AppTest, dashboard_path, profile=profile, kind="bias", query="bias.risk", selected="bias.risk")
    text = "\n".join(item.value for item in app.markdown)
    code = "\n".join(item.value for item in app.code)
    require(all(value in text for value in ("mc_mean", "mc_std", "mc_min", "mc_max", "safe_zero")),
            "RiskBias usage omitted its actual candidate-local statistics or missing-data behavior")
    require(all(value in code for value in ("MonteCarloEvaluationConfig", "mc_samples=8", 'reduce="mean"',
                                           "cvar_alpha=0.25", "random_seed=7")),
            "RiskBias usage omitted the current Monte Carlo configuration interface")
    require("**放在哪**" in text and "**输入与准备**" in text and "**接下来怎么接**" in text,
            "RiskBias usage is missing its concrete preparation and assembly steps")
    return {"key": "bias.risk", "metrics": ["mc_mean", "mc_std", "mc_min", "mc_max"], "app_runs": 1}


def verify_ui() -> dict[str, object]:
    # Configure the same reader grant as the service before importing any Catalog code.
    mode = configure_reader(os.environ)
    require(mode == "only" and os.environ.get("NSGABLACK_CATALOG_HOSTED_SOURCE") == "database",
            "UI acceptance requires the deployment-owned MySQL reader configuration")
    require(os.environ.get("NSGABLACK_CATALOG_DB_READONLY") == "1", "Database reader is not read-only")

    from streamlit.testing.v1 import AppTest
    from nsgablack.catalog import dashboard, facade
    from nsgablack.catalog.curation_provider import DeepSeekGenerator
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.units.contracts import UnitBinding

    dashboard_path = Path(dashboard.__file__).resolve()
    calls = {"model": 0, "unit": 0, "solver": 0}

    def forbidden(kind):
        def reject(*args, **kwargs):
            calls[kind] += 1
            raise VerificationError("Catalog acceptance crossed a model or algorithm execution boundary")
        return reject

    profiles = {}
    with ExitStack() as stack:
        stack.enter_context(patch.object(UnitBinding, "build", forbidden("unit")))
        stack.enter_context(patch.object(DeepSeekGenerator, "generate", forbidden("model")))
        stack.enter_context(patch.object(SolverBase, "run", forbidden("solver")))
        for profile in ("default", "framework-core"):
            source = facade.catalog_source_info(profile=profile, scope="framework", source_mode="only")
            require(source.get("effective_source") == source.get("route_db_backend") == "mysql"
                    and source.get("source_mode") == "only" and not source.get("db_error"),
                    "Catalog acceptance did not read the deployed MySQL source")
            profiles[profile] = {
                "cross_kind": verify_cross_kind(AppTest, dashboard_path, profile),
                "ml_entries": [verify_ml_entry(AppTest, dashboard_path, facade, profile=profile, original_key=key)
                               for key in ("codec.linear_point", "codec.neural_graph", "integration.learning_solver")],
                "related_usage": verify_related_usage(AppTest, dashboard_path, facade, profile),
                "ml_contract": verify_ml_contract(AppTest, dashboard_path, facade, profile),
                "risk_usage": verify_risk_usage(AppTest, dashboard_path, profile),
            }
    require(not any(calls.values()), "Catalog acceptance invoked model inference or algorithm execution")
    app_runs = sum(report["cross_kind"]["app_runs"] + report["related_usage"]["app_runs"]
                   + report["ml_contract"]["app_runs"] + report["risk_usage"]["app_runs"]
                   + sum(item["app_runs"] for item in report["ml_entries"]) for report in profiles.values())
    return {"ok": True, "backend": "mysql", "read_only": True, "app_runs": app_runs,
            "unit_builds": calls["unit"], "execution_calls": calls, "profiles": profiles}


def main() -> int:
    try:
        # Streamlit/driver diagnostics may contain private source configuration.
        # Only the controlled result below is allowed onto the deployment log.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = verify_ui()
        code = 0
    except VerificationError as exc:
        result, code = {"ok": False, "error": str(exc)}, 1
    except Exception as exc:
        result, code = {"ok": False, "error": "Catalog UI acceptance failed",
                        "error_type": type(exc).__name__}, 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
