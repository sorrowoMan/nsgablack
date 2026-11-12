"""User interaction checks for editable assembly, trial isolation and AI drafts."""
from __future__ import annotations

from copy import deepcopy
import json
from urllib.parse import parse_qs

import pytest

from nsgablack.catalog import lab_client, lab_ui
from nsgablack.catalog.lab_assembly import assembly_catalog, assembly_from_recipe
from nsgablack.catalog.lab_design import notes_digest
from nsgablack.catalog.lab_jobs import spec_digest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _widget(elements, label):
    return next(item for item in elements if item.label == label)


def _assert_ok(app):
    assert not app.exception, [item.message for item in app.exception]


@pytest.fixture
def trial_client(monkeypatch):
    state = {"submitted": [], "polled": [], "status": "succeeded", "poll_error": None}

    def capabilities():
        return {"enabled": True, "mode": "remote", "reason": "", "recipes": ["ga", "vns", "moead", "ga_vns"], "assembly_catalog": assembly_catalog()}

    def submit(spec, *, request_id=None):
        state["submitted"].append(deepcopy(spec))
        return {"job_id": f"{len(state['submitted']):032x}", "status": "queued",
                "spec": dict(spec), "spec_digest": spec_digest(spec)}

    def poll(job_id):
        state["polled"].append(job_id)
        if state["poll_error"]:
            raise lab_client.LabClientError(state["poll_error"])
        spec = state["submitted"][-1]
        result = {"steps": 8, "evaluations": 42, "duration_seconds": 1.25,
                  "report": {"raw_objectives": [[0.2, 3.2]], "plan_completed": True},
                  "pool": {"records": 42, "subpools": 1},
                  "unit": {"population_size": 6}, "resource_binding": {"current": True},
                  "project_result": {"status": "succeeded"}, "exit_code": 0,
                  "logs": "Project L0 granted\nCase completed", "error": None}
        if state["status"] == "failed":
            result.update(error={"code": "trial_timeout", "message": "试跑超过时间限制。"},
                          logs="Project started\nworker timeout", exit_code=1)
        result.update(state.get("result_override", {}))
        return {"job_id": job_id, "status": state["status"], "spec": dict(spec),
                "spec_digest": spec_digest(spec), "result": result if state["status"] not in {"queued", "running"} else None}

    monkeypatch.setattr(lab_client, "assistant_capabilities", lambda: {"enabled": False, "reason": "AI 未启用"})
    monkeypatch.setattr(lab_client, "get_capabilities", capabilities)
    monkeypatch.setattr(lab_client, "submit", submit)
    monkeypatch.setattr(lab_client, "poll", poll)
    return state


@pytest.fixture
def app(trial_client):
    return AppTest.from_string(
        "import streamlit as st\n"
        "from nsgablack.catalog.lab_ui import render_workbench\n"
        "render_workbench(st, hosted=True)\n", default_timeout=30).run()


def test_render_and_export_preview_do_not_start_a_solver(app, trial_client):
    _assert_ok(app)
    assert [tab.label for tab in app.tabs if " · " in tab.label] == ["1 · 定义问题", "2 · 装配算法", "3 · 运行结果"]
    assert _widget(app.selectbox, "载入一个配方作为起点").value == "ga"
    assert len(app.get("download_button")) == 3
    selected = _widget(app.selectbox, "项目文件").value
    assert selected.endswith("/build_solver.py")
    assert any("def build_solver" in code.value for code in app.code)
    assert trial_client["submitted"] == trial_client["polled"] == []
    app.run()
    assert trial_client["submitted"] == []


@pytest.mark.parametrize("label", ["定义一个生产优化问题", "设计 GA → VNS 流程"])
def test_starting_prompt_only_fills_input_without_applying_or_submitting(app, trial_client, assistant_client, label):
    original = deepcopy(app.session_state[lab_ui._DRAFT_KEY])
    _widget(app.button, label).click().run()
    _assert_ok(app)
    assert _widget(app.text_area, "描述要解决的问题").value.strip()
    assert app.session_state[lab_ui._DRAFT_KEY] == original
    assert assistant_client["submitted"] == trial_client["submitted"] == []


@pytest.mark.parametrize("component", ["problem.two_centers", "problem.sphere"])
def test_demo_conversion_preserves_ordered_objectives_and_constraints(component):
    from nsgablack.catalog.lab_problem import evaluate_problem

    preset = {"component": component, "parameters": {}}
    expression = lab_ui._problem_as_expression(preset, 2)
    for candidate in ([0., 0.], [-1.5, .25], [1., -.75]):
        expected, expected_violation = evaluate_problem(preset, candidate)
        actual, actual_violation = evaluate_problem(expression, candidate)
        assert actual == pytest.approx(expected)
        assert actual_violation == pytest.approx(expected_violation)


def test_run_uses_current_parameters_once_and_rerender_does_not_resubmit(app, trial_client):
    seed = next(item for item in app.number_input if item.key.endswith("::seed"))
    seed.set_value(29).run()
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert len(trial_client["submitted"]) == 1
    assert trial_client["submitted"][0]["seed"] == 29
    assert [metric.value for metric in app.metric][:3] == ["8", "42", "1.25 s"]
    assert any("Case completed" in item.value for item in app.code)
    assert len(app.get("download_button")) == 4
    app.run()
    assert len(trial_client["submitted"]) == 1
    assert len(trial_client["polled"]) == 1


def test_changed_parameters_label_old_result_and_keep_submitted_spec(app, trial_client):
    _widget(app.button, "开始小预算试跑").click().run()
    old = deepcopy(app.session_state[lab_ui._JOB_KEY])
    seed = next(item for item in app.number_input if item.key.endswith("::seed"))
    seed.set_value(31).run()
    _assert_ok(app)
    assert any("上一次提交" in warning.value for warning in app.warning)
    assert app.session_state[lab_ui._JOB_KEY] == old
    assert len(trial_client["submitted"]) == 1
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert len(trial_client["submitted"]) == 2
    assert not any("上一次提交" in warning.value for warning in app.warning)


def test_pending_job_disables_double_submit_and_manual_refresh_delivers_result(app, trial_client):
    trial_client["status"] = "running"
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert _widget(app.button, "开始小预算试跑").disabled
    assert any("正在试跑" in info.value for info in app.info)
    trial_client["status"] = "succeeded"
    _widget(app.button, "刷新运行状态").click().run()
    _assert_ok(app)
    assert not _widget(app.button, "开始小预算试跑").disabled
    assert len(trial_client["submitted"]) == 1
    assert any("试跑完成" in success.value for success in app.success)


def test_failed_trial_shows_failure_log_without_claiming_success(app, trial_client):
    trial_client["status"] = "failed"
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert any("超过时间限制" in item.value for item in app.error)
    assert any("worker timeout" in item.value for item in app.code)
    assert not app.success
    log_expander = next(item for item in app.expander if item.label == "运行日志")
    assert log_expander.proto.expanded


def test_poll_failure_keeps_last_job_and_allows_retry(app, trial_client):
    trial_client["status"] = "running"
    trial_client["poll_error"] = "试跑服务暂不可用"
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert any("暂时无法读取" in item.value for item in app.warning)
    assert app.session_state[lab_ui._JOB_KEY]["status"] == "queued"
    trial_client["poll_error"] = None
    trial_client["status"] = "succeeded"
    _widget(app.button, "刷新运行状态").click().run()
    _assert_ok(app)
    assert any("试跑完成" in item.value for item in app.success)


def test_submit_failure_never_invents_a_job(app, trial_client, monkeypatch):
    def unavailable(spec, *, request_id=None):
        raise lab_client.LabClientError("试跑队列已满")

    monkeypatch.setattr(lab_client, "submit", unavailable)
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert any("试跑队列已满" in item.value for item in app.error)
    assert lab_ui._JOB_KEY not in app.session_state
    assert trial_client["polled"] == []


def test_expired_job_can_be_forgotten_without_implicitly_submitting_again(app, trial_client):
    trial_client["status"] = "running"
    trial_client["poll_error"] = "试跑记录已过期或服务已重启，请重新试跑。"
    _widget(app.button, "开始小预算试跑").click().run()
    _widget(app.button, "移除本页运行记录").click().run()
    _assert_ok(app)
    assert lab_ui._JOB_KEY not in app.session_state
    assert not _widget(app.button, "开始小预算试跑").disabled
    assert len(trial_client["submitted"]) == 1


def test_uncertain_submission_reuses_frozen_request_until_acknowledged(app, trial_client, monkeypatch):
    normal_submit = lab_client.submit
    requests = []

    def uncertain(spec, *, request_id=None):
        requests.append((request_id, deepcopy(spec)))
        if len(requests) == 1:
            raise lab_client.LabClientError("响应丢失，状态未确认")
        return normal_submit(spec, request_id=request_id)

    monkeypatch.setattr(lab_client, "submit", uncertain)
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    intent = deepcopy(app.session_state[lab_ui._INTENT_KEY])
    app.run()
    assert len(requests) == 1
    assert any("上次提交状态尚未确认" in warning.value for warning in app.warning)
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert requests[0] == requests[1]
    assert requests[0][0] == intent["request_id"]
    assert lab_ui._INTENT_KEY not in app.session_state
    assert any("试跑完成" in success.value for success in app.success)


def test_new_parameters_warn_about_unconfirmed_submission_before_new_intent(app, trial_client, monkeypatch):
    normal_submit = lab_client.submit
    requests = []

    def uncertain(spec, *, request_id=None):
        requests.append(request_id)
        if len(requests) == 1:
            raise lab_client.LabClientError("状态未确认")
        return normal_submit(spec, request_id=request_id)

    monkeypatch.setattr(lab_client, "submit", uncertain)
    _widget(app.button, "开始小预算试跑").click().run()
    next(item for item in app.number_input if item.key.endswith("::seed")).set_value(44).run()
    _assert_ok(app)
    assert any("修改参数不会取消" in warning.value for warning in app.warning)
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert requests[0] != requests[1]
    assert trial_client["submitted"][0]["seed"] == 44


def test_disabled_service_preserves_preview_and_export(app, monkeypatch):
    monkeypatch.setattr(lab_client, "get_capabilities", lambda: {
        "enabled": False, "mode": "unavailable", "reason": "运行服务未配置", "recipes": []})
    app.run()
    _assert_ok(app)
    assert _widget(app.button, "开始小预算试跑").disabled
    assert len(app.get("download_button")) == 3
    assert any("运行服务未配置" in item.value for item in app.info)


def test_hosted_ui_refuses_local_execution_even_when_capability_claims_enabled(app, monkeypatch):
    monkeypatch.setattr(lab_client, "get_capabilities", lambda: {
        "enabled": True, "mode": "local", "recipes": ["ga"]})
    app.run()
    _assert_ok(app)
    assert _widget(app.button, "开始小预算试跑").disabled
    assert any("需要配置隔离试跑服务" in item.value for item in app.info)


def test_invalid_initial_count_prevents_export_and_run(app, trial_client):
    count = next(item for item in app.number_input if item.key.endswith("::initial_count"))
    count.set_value(1).run()
    _assert_ok(app)
    assert any("调整装配参数" in item.value for item in app.error)
    assert _widget(app.button, "开始小预算试跑").disabled
    assert len(app.get("download_button")) == 0
    assert trial_client["submitted"] == []


def test_invalid_draft_keeps_running_job_visible_without_allowing_resubmit(app, trial_client):
    trial_client["status"] = "running"
    _widget(app.button, "开始小预算试跑").click().run()
    count = next(item for item in app.number_input if item.key.endswith("::initial_count"))
    count.set_value(1).run()
    _assert_ok(app)
    assert _widget(app.button, "开始小预算试跑").disabled
    assert any("上一次提交" in item.value for item in app.warning)
    assert any("正在试跑" in item.value for item in app.info)
    assert len(trial_client["submitted"]) == 1
    trial_client["status"] = "succeeded"
    _widget(app.button, "刷新运行状态").click().run()
    _assert_ok(app)
    assert any("试跑完成" in item.value for item in app.success)
    assert _widget(app.button, "开始小预算试跑").disabled


def test_result_tables_show_checked_raw_feedback_identity_units_and_budget_limit(app, trial_client):
    trial_client["result_override"] = {
        "pool": {"initial_count": 12, "accepted_count": 42, "records": 9,
                 "views": [{"descriptor": {"name": "moead/0", "revision": 3}, "members": 1,
                            "metadata": {"kind": "objective_projection", "created_by": ["router", "moead"],
                                         "projection": {"weights": [.8, .2]}}}]},
        "results": {"scope": "last_128_accepted", "candidates": [[0.0, 0.0]],
                    "raw_objectives": [[1.0, 1.0]], "raw_violations": [0.0],
                    "refs": [{"candidate_token": "proposal-17", "record_id": "version-4", "row": 3}]},
        "unit": {"instances": [{"path": "router/0:ga", "type": "NSGA2Adapter", "unit_exists": True,
                                 "current_exists": False, "population_members": 6, "published_views": ["population"]}]},
        "records": [{"steps": 1, "evaluations": 6, "best_raw_sum": 2.0,
                     "accepted_count": 6, "pool_records": 2, "phases": ["ga"]}],
        "plan_completed": False,
    }
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert any("计划尚未完成" in item.value for item in app.warning)
    tables = [frame.value for frame in app.dataframe]
    candidates = next(frame for frame in tables if "候选 token" in frame.columns)
    assert candidates.iloc[0]["候选 token"] == "proposal-17"
    assert candidates.iloc[0]["原始目标 1"] == 1.0
    assert candidates.iloc[0]["原始目标 2"] == 1.0
    assert candidates.iloc[0]["原记录行"] == 3
    units = next(frame for frame in tables if "实例路径" in frame.columns)
    assert units.iloc[0]["实例路径"] == "router/0:ga"
    assert units.iloc[0]["种群成员"] == 6
    views = next(frame for frame in tables if "子池 / 视图" in frame.columns)
    assert views.iloc[0]["创建者路径"] == "router/moead"
    assert views.iloc[0]["成员引用数"] == 1
    assert any("不代表最终种群" in item.value for item in app.caption)
    assert [metric.value for metric in app.metric][3:] == ["12", "42", "9"]


def test_capabilities_error_still_allows_static_project_export(app, monkeypatch):
    def unavailable():
        raise lab_client.LabClientError("无法连接运行服务")

    monkeypatch.setattr(lab_client, "get_capabilities", unavailable)
    app.run()
    _assert_ok(app)
    assert _widget(app.button, "开始小预算试跑").disabled
    assert len(app.get("download_button")) == 3
    assert any("试跑服务暂不可用" in item.value for item in app.info)


@pytest.mark.parametrize("recipe", ["vns", "moead", "ga_vns"])
def test_recipes_require_explicit_load_and_then_remain_freely_editable(app, trial_client, recipe):
    initial = deepcopy(app.session_state[lab_ui._DRAFT_KEY])
    _widget(app.selectbox, "载入一个配方作为起点").set_value(recipe).run()
    _assert_ok(app)
    assert app.session_state[lab_ui._DRAFT_KEY] == initial
    _widget(app.button, "载入配方").click().run()
    _assert_ok(app)
    assert [row["id"] for row in app.session_state[lab_ui._DRAFT_KEY]["nodes"]] == [row["id"] for row in assembly_from_recipe(recipe)["nodes"]]
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert trial_client["submitted"][0]["recipe"] == "assembly"
    assert trial_client["submitted"][0]["nodes"][0]["component"] == assembly_from_recipe(recipe)["nodes"][0]["component"]


def test_catalog_link_preserves_current_profile_search_and_multivalue_filters():
    values = {"view": "lab", "kind": "group:tools", "selected": "tool.old", "profile": "framework-core",
              "query": "Unit & Pool", "f_tags": ["numeric", "pool"]}
    url = lab_ui.catalog_component_url(values, "adapter.moead")
    parsed = parse_qs(url[1:])
    assert parsed == {"view": ["catalog"], "kind": ["all"], "selected": ["adapter.moead"],
                      "nav_action": ["locate_selected"],
                      "profile": ["framework-core"], "query": ["Unit & Pool"], "f_tags": ["numeric", "pool"]}
    assert values["view"] == "lab"


def test_representation_link_locates_real_component_in_full_dashboard_with_existing_filters(monkeypatch, trial_client):
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    app = AppTest.from_string(
        "from nsgablack.catalog.dashboard import run_dashboard\n"
        "run_dashboard(['--profile', 'default', '--source-mode', 'off'])\n", default_timeout=45)
    app.query_params.update({"view": "lab", "profile": "framework-core", "query": "不存在的过滤词", "f_tags": "no-such-tag"})
    app.run()
    _assert_ok(app)
    assert sum("class='workspace-brand'" in item.value for item in app.markdown) == 1
    url = lab_ui.catalog_component_url(app.query_params, "repr.continuous")
    app.query_params.clear()
    app.query_params.update(parse_qs(url[1:]))
    app.run()
    _assert_ok(app)
    assert _widget(app.radio, "工作区").value == "组件目录"
    assert app.session_state["catalog_ui_selected"] == "repr.continuous"
    assert app.session_state["catalog_ui_kind"] == "all"
    assert app.session_state["catalog_ui_query"] == ""
    assert "repr.continuous" in app.session_state["catalog_ui_result_keys"]
    assert any(str(item.key).startswith("catalog_ui::component_list::") for item in app.radio)
    assert sum("class='workspace-brand'" in item.value for item in app.markdown) == 1
    _widget(app.radio, "工作区").set_value("装配实验台").run()
    _assert_ok(app)
    assert sum("class='workspace-brand'" in item.value for item in app.markdown) == 1
    assert _widget(app.selectbox, "载入一个配方作为起点").value == "ga"


def test_add_same_algorithm_twice_assigns_distinct_instance_and_plan_identity(app, trial_client):
    _widget(app.button, "添加算法实例").click().run()
    _assert_ok(app)
    draft = app.session_state[lab_ui._DRAFT_KEY]
    assert len(draft["nodes"]) == 2
    assert draft["nodes"][0]["component"] == draft["nodes"][1]["component"] == "adapter.nsga2"
    assert draft["nodes"][0]["id"] != draft["nodes"][1]["id"]
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    spec = trial_client["submitted"][0]
    assert len({child["label"] for child in spec["plan"]["children"]}) == 2
    assert spec["plan"]["children"][1]["node"] == draft["nodes"][1]["id"]


def test_replacing_algorithm_shows_real_parameters_and_discards_previous_fields(app, trial_client):
    _widget(app.selectbox, "算法组件").set_value("adapter.sa").run()
    _assert_ok(app)
    assert not app.error
    names = {item.key.rsplit("::", 1)[-1] for item in app.number_input}
    assert "initial_temperature" in names
    assert "population_size" not in names
    _widget(app.button, "开始小预算试跑").click().run()
    node = trial_client["submitted"][0]["nodes"][0]
    assert node["component"] == "adapter.sa"
    assert "initial_temperature" in node["parameters"]
    assert "population_size" not in node["parameters"]


def test_replacing_vns_with_sa_preserves_refinement_wiring_and_return_competition(app, trial_client):
    from nsgablack.catalog.lab_assembly import normalize_assembly

    _widget(app.selectbox, "载入一个配方作为起点").set_value("ga_vns").run()
    _widget(app.button, "载入配方").click().run()
    _widget(app.selectbox, "选择这些来源的哪些视图").set_value("random").run()
    _widget(app.number_input, "随机选择的视图数").set_value(1).run()
    _widget(app.number_input, "每个起点的精修步数（含起点评估）").set_value(3).run()
    shuffle_key = next(item.key for item in app.checkbox if "node::vns::shuffle" in item.key)
    app.checkbox(key=shuffle_key).check().run()
    before = deepcopy(app.session_state[lab_ui._DRAFT_KEY])
    vns_component_key = next(item.key for item in app.selectbox if "node::vns::component" in item.key)
    app.selectbox(key=vns_component_key).set_value("adapter.sa").run()
    _assert_ok(app)
    assert not app.error
    changed = normalize_assembly(app.session_state[lab_ui._DRAFT_KEY])
    assert changed["nodes"][1]["component"] == "adapter.sa"
    assert changed["nodes"][1]["input"] == before["nodes"][1]["input"]
    assert changed["nodes"][0]["return_from"] == "vns"
    assert changed["plan"] == before["plan"]
    app.run()
    _assert_ok(app)
    assert not app.error
    assert normalize_assembly(app.session_state[lab_ui._DRAFT_KEY]) == changed
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert trial_client["submitted"][0] == changed


def test_unit_capacity_edit_updates_initial_intake_without_changing_mother_pool(app, trial_client):
    population = next(item for item in app.number_input if item.key.endswith("::population_size"))
    population.set_value(8).run()
    _assert_ok(app)
    assert not app.error
    _widget(app.button, "开始小预算试跑").click().run()
    spec = trial_client["submitted"][0]
    assert spec["initial_count"] == 12
    assert spec["nodes"][0]["parameters"]["population_size"] == spec["nodes"][0]["input"]["count"] == 8


def test_problem_pipeline_bias_and_plugin_are_editable_on_same_document(app, trial_client):
    _widget(app.selectbox, "原始评估问题").set_value("problem.sphere").run()
    _widget(app.button, "使用这个演示问题").click().run()
    _widget(app.selectbox, "问题管线的可选变异").set_value("repr.gaussian_mutation").run()
    _widget(app.selectbox, "可选软评分 Bias").set_value("bias.l2_preference").run()
    _widget(app.multiselect, "生命周期 Plugin").set_value(["plugin.pareto_archive"]).run()
    _assert_ok(app)
    assert not app.error
    _widget(app.button, "开始小预算试跑").click().run()
    spec = trial_client["submitted"][0]
    assert spec["problem"]["component"] == "problem.sphere"
    assert spec["pipeline"]["mutator"]["component"] == "repr.gaussian_mutation"
    assert spec["bias"]["component"] == "bias.l2_preference"
    assert spec["plugins"][0]["component"] == "plugin.pareto_archive"


def test_visual_pool_editor_keeps_adapter_instance_selection_and_direction_sampling(app, trial_client):
    _widget(app.selectbox, "载入一个配方作为起点").set_value("ga_vns").run()
    _widget(app.button, "载入配方").click().run()
    app.selectbox(key=next(item.key for item in app.selectbox if "node::ga::component" in item.key)).set_value("adapter.moead").run()
    _widget(app.selectbox, "选择这些来源的哪些视图").set_value("random").run()
    _widget(app.number_input, "随机选择的视图数").set_value(2).run()
    _assert_ok(app)
    assert not app.error
    _widget(app.button, "开始小预算试跑").click().run()
    spec = trial_client["submitted"][0]
    assert spec["nodes"][0]["component"] == "adapter.moead"
    assert spec["nodes"][1]["input"]["source"] == {"adapter": "ga", "views": "random", "view_count": 2}
    assert spec["nodes"][0]["return_from"] == "vns"


def test_visual_serial_multi_repeat_controls_compile_to_same_exported_plan(app, trial_client):
    _widget(app.selectbox, "添加一种算法").set_value("adapter.vns").run()
    _widget(app.button, "添加算法实例").click().run()
    _widget(app.selectbox, "阶段如何执行").set_value("multi").run()
    _widget(app.number_input, "整个计划重复次数").set_value(3).run()
    _assert_ok(app)
    assert not app.error
    _widget(app.button, "开始小预算试跑").click().run()
    plan = trial_client["submitted"][0]["plan"]
    assert plan["kind"] == "repeat" and plan["times"] == 3
    assert plan["body"]["kind"] == "multi"
    assert len(plan["body"]["children"]) == 2


def test_advanced_nested_document_is_imported_explicitly_and_preserved_on_rerun(app, trial_client):
    from nsgablack.catalog.lab_assembly import normalize_assembly
    document = assembly_from_recipe("ga_vns")
    document["plan"] = {"kind": "repeat", "times": 2, "body": document["plan"]}
    document["plan"]["body"]["children"][0] = {"kind": "serial", "children": [document["plan"]["body"]["children"][0]]}
    checked = normalize_assembly(document)
    _widget(app.text_area, "完整装配 JSON").set_value(json.dumps(document)).run()
    assert app.session_state[lab_ui._DRAFT_KEY]["nodes"][0]["return_from"] is None
    _widget(app.button, "校验并应用 JSON").click().run()
    _assert_ok(app)
    assert app.session_state[lab_ui._DRAFT_KEY] == checked
    app.run()
    _assert_ok(app)
    assert app.session_state[lab_ui._DRAFT_KEY] == checked
    assert any("多层嵌套计划" in item.value for item in app.info)
    _widget(app.button, "开始小预算试跑").click().run()
    assert trial_client["submitted"][0] == checked


def test_invalid_json_never_overwrites_manual_document_or_submits_code(app, trial_client):
    before = deepcopy(app.session_state[lab_ui._DRAFT_KEY])
    _widget(app.text_area, "完整装配 JSON").set_value('{"schema":"python", "code":"import os"}').run()
    _widget(app.button, "校验并应用 JSON").click().run()
    _assert_ok(app)
    assert any("未应用" in item.value for item in app.error)
    assert app.session_state[lab_ui._DRAFT_KEY] == before
    assert trial_client["submitted"] == []


def test_json_buffer_tracks_visual_edits_but_preserves_unapplied_json(app, trial_client):
    seed = next(item for item in app.number_input if item.key.endswith("::seed"))
    seed.set_value(41).run()
    _assert_ok(app)
    assert json.loads(_widget(app.text_area, "完整装配 JSON").value)["seed"] == 41
    custom = json.loads(_widget(app.text_area, "完整装配 JSON").value)
    custom["seed"] = 42
    _widget(app.text_area, "完整装配 JSON").set_value(json.dumps(custom)).run()
    next(item for item in app.number_input if item.key.endswith("::seed")).set_value(43).run()
    _assert_ok(app)
    assert app.session_state[lab_ui._DRAFT_KEY]["seed"] == 43
    assert json.loads(_widget(app.text_area, "完整装配 JSON").value)["seed"] == 42
    assert any("尚未应用" in item.value for item in app.caption)
    _widget(app.button, "校验并应用 JSON").click().run()
    _assert_ok(app)
    assert app.session_state[lab_ui._DRAFT_KEY]["seed"] == 42
    app.run()
    _assert_ok(app)
    assert trial_client["submitted"] == []


def test_different_runner_catalog_disables_execution_and_preserves_edit_export(app, monkeypatch):
    metadata = assembly_catalog()
    metadata["components"]["adapters"][0]["defaults"]["population_size"] = 99
    monkeypatch.setattr(lab_client, "get_capabilities", lambda: {
        "enabled": True, "mode": "remote", "assembly_catalog": metadata})
    app.run()
    _assert_ok(app)
    assert _widget(app.button, "开始小预算试跑").disabled
    assert len(app.get("download_button")) == 3
    assert any("组件声明与当前页面不同" in item.value for item in app.info)


@pytest.fixture
def assistant_client(monkeypatch, app):
    state = {"submitted": [], "polled": [], "status": "succeeded", "questions": []}
    if lab_ui._AI_CAPS_KEY in app.session_state:
        del app.session_state[lab_ui._AI_CAPS_KEY]
    monkeypatch.setattr(lab_client, "assistant_capabilities", lambda: {
        "enabled": True, "mode": "remote", "limits": {"requests_per_utc_day": None},
        "quota": {"remaining": None, "resets_at": None}})

    def submit(spec, instruction, *, request_id, guide_context=None):
        state["submitted"].append((deepcopy(spec), instruction, request_id))
        state.setdefault("guide_contexts", []).append(deepcopy(guide_context))
        return {"job_id": "a" * 32, "status": "queued", "base_digest": spec_digest(spec)}

    def poll(job_id):
        state["polled"].append(job_id)
        original = state["submitted"][-1][0]
        proposal = deepcopy(state.get("draft_override", original))
        if "draft_override" not in state:
            proposal["seed"] = 123
        result = {"draft": None if state["questions"] else proposal, "base_digest": spec_digest(original),
                           "explanation": "按你的要求修改随机种子。", "changes": ["seed 改为 123"],
                           "questions": state["questions"], "evidence_keys": ["adapter.nsga2"],
                           "design_base_digest": notes_digest(state["guide_contexts"][-1]["design_notes"]),
                           "verification_status": "not_run"}
        result.update(deepcopy(state.get("result_override", {})))
        return {"job_id": job_id, "status": state["status"], "base_digest": spec_digest(original), "result": result}

    monkeypatch.setattr(lab_client, "assistant_submit", submit)
    monkeypatch.setattr(lab_client, "assistant_poll", poll)
    return state


@pytest.mark.parametrize("limits,quota,limited", [
    ({"requests_per_utc_day": None}, {"remaining": None, "resets_at": None}, False),
    ({}, {"remaining": 0}, False),
    ({"requests_per_utc_day": None}, {"remaining": 0}, False),
    ({"requests_per_utc_day": 20}, {"remaining": 0}, True),
])
def test_ai_daily_limit_is_explicit_and_legacy_zero_never_blocks_unlimited_service(
        app, trial_client, assistant_client, monkeypatch, limits, quota, limited):
    monkeypatch.setattr(lab_client, "assistant_capabilities", lambda: {
        "enabled": True, "mode": "remote", "limits": limits, "quota": quota})
    if lab_ui._AI_CAPS_KEY in app.session_state:
        del app.session_state[lab_ui._AI_CAPS_KEY]
    app.run()
    # Connecting, refreshing and editing an instruction cannot make a model call.
    assert _widget(app.button, "生成可编辑草案").disabled
    for label in ("描述要解决的问题", "描述想怎么调整算法", "针对运行结果，你想了解什么"):
        _widget(app.text_area, label).set_value("保留当前装配，解释下一步").run()
    _assert_ok(app)
    for label in ("生成可编辑草案", "请 AI 调整装配", "请 AI 解读结果"):
        assert _widget(app.button, label).disabled is limited
    assert assistant_client["submitted"] == trial_client["submitted"] == []
    visible_text = " ".join(item.value for item in list(app.markdown) + list(app.caption))
    assert "今日剩余" not in visible_text and "额度已用完" not in visible_text
    if not limited:
        _widget(app.button, "生成可编辑草案").click().run()
        _assert_ok(app)
        assert len(assistant_client["submitted"]) == 1
        assert trial_client["submitted"] == []
        app.run()
        assert len(assistant_client["submitted"]) == 1


def test_unlimited_ai_keeps_a_running_request_disabled_without_resubmission(
        app, trial_client, assistant_client):
    assistant_client["status"] = "running"
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("解释当前装配").run()
    _widget(app.button, "生成可编辑草案").click().run()
    _assert_ok(app)
    assert _widget(app.button, "生成可编辑草案").disabled
    assert len(assistant_client["submitted"]) == 1
    app.run()
    assert _widget(app.button, "生成可编辑草案").disabled
    assert len(assistant_client["submitted"]) == 1
    assert trial_client["submitted"] == []


def test_ai_preview_requires_explicit_apply_and_never_starts_trial(app, trial_client, assistant_client):
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("把随机种子改成 123").run()
    _widget(app.button, "生成可编辑草案").click().run()
    _assert_ok(app)
    assert app.session_state[lab_ui._DRAFT_KEY]["seed"] == 17
    assert not _widget(app.button, "应用这份 AI 草案").disabled
    assert len(assistant_client["submitted"]) == 1
    assert len(assistant_client["polled"]) == 1
    app.run()
    assert len(assistant_client["submitted"]) == 1
    assert len(assistant_client["polled"]) == 1
    _widget(app.button, "应用这份 AI 草案").click().run()
    _assert_ok(app)
    assert app.session_state[lab_ui._DRAFT_KEY]["seed"] == 123
    assert lab_ui._AI_JOB_KEY not in app.session_state
    assert trial_client["submitted"] == []


def _profit_document():
    document = assembly_from_recipe("ga")
    document["dimension"] = 1
    document["problem"] = {"component": "problem.expression", "parameters": {
        "variables": [{"name": "x", "low": 0., "high": 10., "type": "continuous"}],
        "objectives": [{"name": "利润", "expression": "8*x-x**2", "direction": "max"}],
        "constraints": [{"name": "资源", "expression": "x", "relation": "<=", "rhs": 6., "tolerance": 0.}]}}
    document["pipeline"]["initializer"] = {"component": "repr.problem_uniform", "parameters": {}}
    return document


def test_natural_problem_preview_apply_manual_edit_assembly_and_trial(app, trial_client, assistant_client):
    assistant_client["draft_override"] = _profit_document()
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("产量 x 在 0 到 10，最大化利润 8*x-x**2，资源 x<=6").run()
    _widget(app.button, "生成可编辑草案").click().run()
    _assert_ok(app)
    assert app.session_state[lab_ui._DRAFT_KEY]["problem"]["component"] == "problem.two_centers"
    assert any("AI 建议 · 尚未应用" in item.value and "最大化 利润" in item.value for item in app.markdown)
    assert assistant_client["guide_contexts"][0]["stage"] == "problem"
    _widget(app.button, "应用这份 AI 草案").click().run()
    _assert_ok(app)
    assert _widget(app.text_input, "变量 1 名称").value == "x"
    assert _widget(app.selectbox, "目标 1 方向").value == "max"
    _widget(app.text_input, "目标 1 公式").set_value("10*x-x**2").run()
    assert _widget(app.button, "开始小预算试跑").disabled
    _widget(app.button, "应用问题定义").click().run()
    _assert_ok(app)
    draft = app.session_state[lab_ui._DRAFT_KEY]
    assert draft["dimension"] == 1
    assert draft["problem"]["parameters"]["objectives"][0]["expression"] == "10*x-x**2"
    assert draft["pipeline"]["initializer"]["component"] == "repr.problem_uniform"
    _widget(app.selectbox, "算法组件").set_value("adapter.sa").run()
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    assert trial_client["submitted"][0]["problem"] == draft["problem"]
    assert trial_client["submitted"][0]["nodes"][0]["component"] == "adapter.sa"


def test_invalid_unapplied_problem_is_preserved_without_replacing_run_document(app, trial_client):
    before = deepcopy(app.session_state[lab_ui._DRAFT_KEY])
    _widget(app.text_input, "目标 1 公式").set_value("unknown_variable + 1").run()
    _widget(app.button, "应用问题定义").click().run()
    _assert_ok(app)
    assert any("问题未应用" in item.value for item in app.error)
    assert app.session_state[lab_ui._DRAFT_KEY] == before
    assert _widget(app.text_input, "目标 1 公式").value == "unknown_variable + 1"
    assert _widget(app.button, "开始小预算试跑").disabled
    _widget(app.button, "放弃尚未应用的问题修改").click().run()
    _assert_ok(app)
    assert not _widget(app.button, "开始小预算试跑").disabled
    assert trial_client["submitted"] == []


def test_result_table_restores_maximization_value_and_names(app, trial_client):
    _widget(app.text_area, "完整装配 JSON").set_value(json.dumps(_profit_document())).run()
    _widget(app.button, "校验并应用 JSON").click().run()
    trial_client["result_override"] = {"results": {"candidates": [[4.]], "raw_objectives": [[-16.]],
        "raw_violations": [0.], "refs": [{"candidate_token": "p1", "record_id": "v1", "row": 0}]}}
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    table = next(frame.value for frame in app.dataframe if "利润（最大化）" in frame.value.columns)
    assert table.iloc[0]["利润（最大化）"] == 16.
    assert table.iloc[0]["x"] == 4.
    assert any("最大化目标已恢复" in item.value for item in app.caption)


def test_ai_guidance_keeps_clarification_history_across_problem_and_assembly(app, trial_client, assistant_client):
    assistant_client["questions"] = ["产量 x 的范围是多少？"]
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("优化利润").run()
    _widget(app.button, "生成可编辑草案").click().run()
    _assert_ok(app)
    assert any("范围是多少" in item.value for item in app.info)
    assistant_client["questions"] = []
    _widget(app.text_area, "描述想怎么调整算法").set_value("产量范围是 0 到 10，先保留 GA").run()
    _widget(app.button, "请 AI 调整装配").click().run()
    _assert_ok(app)
    context = assistant_client["guide_contexts"][-1]
    assert context["stage"] == "assembly"
    assert any("范围是多少" in row["content"] for row in context["history"])
    assert trial_client["submitted"] == []


def test_results_ai_gets_only_checked_summary_and_marks_old_run(app, trial_client, assistant_client):
    _widget(app.button, "开始小预算试跑").click().run()
    next(item for item in app.number_input if item.key.endswith("::seed")).set_value(71).run()
    _widget(app.text_area, "针对运行结果，你想了解什么").set_value("解释预算和计划完成情况").run()
    _widget(app.button, "请 AI 解读结果").click().run()
    _assert_ok(app)
    context = assistant_client["guide_contexts"][-1]
    assert context["stage"] == "results"
    assert context["trial"]["steps"] == 8
    assert context["trial"]["evaluations"] == 42
    assert context["trial"]["matches_current"] is False
    assert "logs" not in context["trial"] and "refs" not in context["trial"]


@pytest.mark.parametrize("best,has_chart", [(-16., True), (None, False)])
def test_custom_single_objective_progress_only_claims_feasible_best(app, trial_client, best, has_chart):
    _widget(app.text_area, "完整装配 JSON").set_value(json.dumps(_profit_document())).run()
    _widget(app.button, "校验并应用 JSON").click().run()
    trial_client["result_override"] = {"records": [{"steps": 1, "evaluations": 6,
        "best_raw_sum": -25., "best_feasible_raw_sum": best, "feasible_count": int(best is not None)}]}
    _widget(app.button, "开始小预算试跑").click().run()
    _assert_ok(app)
    if has_chart:
        assert any("只统计原始约束违反量为 0" in item.value for item in app.caption)
        assert not any("暂无可行结果" in item.value for item in app.info)
    else:
        assert any("暂无可行结果" in item.value for item in app.info)
        assert not app.get("vega_lite_chart")


def test_ai_old_draft_cannot_overwrite_new_manual_edit(app, trial_client, assistant_client):
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("修改种子").run()
    _widget(app.button, "生成可编辑草案").click().run()
    next(item for item in app.number_input if item.key.endswith("::seed")).set_value(37).run()
    _assert_ok(app)
    assert _widget(app.button, "应用这份 AI 草案").disabled
    assert any("旧草案不能应用" in item.value for item in app.warning)
    assert app.session_state[lab_ui._DRAFT_KEY]["seed"] == 37


def test_ai_questions_have_no_apply_button_and_keep_manual_workbench_usable(app, trial_client, assistant_client):
    assistant_client["questions"] = ["这个模型需要数据源；请导出 Project 接入。"]
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("添加未支持模型").run()
    _widget(app.button, "生成可编辑草案").click().run()
    _assert_ok(app)
    assert not any(item.label == "应用这份 AI 草案" for item in app.button)
    assert any("需要数据源" in item.value for item in app.info)
    assert not _widget(app.button, "开始小预算试跑").disabled


def test_ai_uncertain_submission_reuses_request_identity(app, trial_client, assistant_client, monkeypatch):
    normal_submit = lab_client.assistant_submit
    calls = []

    def uncertain(spec, instruction, *, request_id, guide_context=None):
        calls.append((deepcopy(spec), instruction, request_id))
        if len(calls) == 1:
            raise lab_client.LabClientError("响应未确认")
        return normal_submit(spec, instruction, request_id=request_id, guide_context=guide_context)

    monkeypatch.setattr(lab_client, "assistant_submit", uncertain)
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("修改种子").run()
    _widget(app.button, "生成可编辑草案").click().run()
    _assert_ok(app)
    assert lab_ui._AI_INTENT_KEY in app.session_state
    app.run()
    assert len(calls) == 1
    _widget(app.button, "生成可编辑草案").click().run()
    _assert_ok(app)
    assert calls[0] == calls[1]
    assert lab_ui._AI_INTENT_KEY not in app.session_state
    assert trial_client["submitted"] == []


def test_ai_capability_failure_is_cached_once_for_three_steps_and_does_not_block_manual(app, trial_client, monkeypatch):
    calls = []
    def failed():
        calls.append(1)
        raise lab_client.LabClientError("AI 连接暂不可用")
    monkeypatch.setattr(lab_client, "assistant_capabilities", failed)
    if lab_ui._AI_CAPS_KEY in app.session_state:
        del app.session_state[lab_ui._AI_CAPS_KEY]
    app.run()
    _assert_ok(app)
    assert len(calls) == 1
    assert not _widget(app.button, "开始小预算试跑").disabled
    next(item for item in app.number_input if item.key.endswith("::seed")).set_value(88).run()
    _assert_ok(app)
    assert len(calls) == 1
    assert not _widget(app.button, "开始小预算试跑").disabled
    _widget(app.button, "刷新 AI 连接").click().run()
    _assert_ok(app)
    assert len(calls) == 2


def test_algorithm_discussion_saves_confirmed_design_without_a_runnable_draft(app, trial_client, assistant_client):
    notes = "已确认：每成员步长归 PopulationUnit；成功判据待讨论，尚未实现。"
    assistant_client["result_override"] = {"draft": None, "changes": [], "design_notes": notes,
        "explanation": "先讨论成员状态，不替你选一个不同的现有算法。",
        "questions": ["成员替换后保留父代步长，还是初始化新步长？"]}
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("给 GA 加每成员独立步长，要不要扩展 Unit？").run()
    _widget(app.button, "生成可编辑草案").click().run()
    _assert_ok(app)
    before = deepcopy(app.session_state[lab_ui._DRAFT_KEY])
    assert _widget(app.text_area, "已确认的设计笔记").value == ""
    assert not any(item.label == "应用这份 AI 草案" for item in app.button)
    assert not _widget(app.button, "确认并保存这份设计笔记").disabled
    assert any("成员替换后" in item.value for item in app.info)
    _widget(app.button, "确认并保存这份设计笔记").click().run()
    _assert_ok(app)
    assert _widget(app.text_area, "已确认的设计笔记").value == notes
    assert app.session_state[lab_ui._DRAFT_KEY] == before
    assert trial_client["submitted"] == []
    source_names = _widget(app.selectbox, "项目文件").options
    assert any(name.endswith("DESIGN.md") for name in source_names)
    _widget(app.selectbox, "项目文件").set_value(next(name for name in source_names if name.endswith("DESIGN.md"))).run()
    assert any(notes in item.value for item in app.code)


@pytest.mark.parametrize("change", ["notes", "assembly"])
def test_old_design_suggestion_cannot_overwrite_later_manual_decisions(app, trial_client, assistant_client, change):
    assistant_client["result_override"] = {"draft": None, "design_notes": "AI 建议的成员步长方案"}
    app.run()
    _widget(app.text_area, "已确认的设计笔记").set_value("原先设计").run()
    _widget(app.text_area, "描述要解决的问题").set_value("继续讨论成员步长").run()
    _widget(app.button, "生成可编辑草案").click().run()
    assert not _widget(app.button, "确认并保存这份设计笔记").disabled
    if change == "notes":
        _widget(app.text_area, "已确认的设计笔记").set_value("手动确认了另一种方案").run()
    else:
        next(item for item in app.number_input if item.key.endswith("::seed")).set_value(52).run()
    _assert_ok(app)
    assert _widget(app.button, "确认并保存这份设计笔记").disabled
    assert any("旧笔记建议" in item.value for item in app.warning)
    assert _widget(app.text_area, "已确认的设计笔记").value != "AI 建议的成员步长方案"
    assert trial_client["submitted"] == []


def test_ai_notes_remain_a_separate_confirmation_when_assembly_draft_is_applied(app, trial_client, assistant_client):
    assistant_client["result_override"] = {"design_notes": "建议：改种子，保留 GA。"}
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("改种子，并整理设计").run()
    _widget(app.button, "生成可编辑草案").click().run()
    _widget(app.button, "应用这份 AI 草案").click().run()
    _assert_ok(app)
    assert app.session_state[lab_ui._DRAFT_KEY]["seed"] == 123
    assert _widget(app.text_area, "已确认的设计笔记").value == ""
    assert trial_client["submitted"] == []


@pytest.mark.parametrize("change", ["notes", "history"])
def test_ai_uncertain_identity_changes_with_design_or_conversation(app, trial_client, assistant_client, monkeypatch, change):
    calls = []

    def uncertain(spec, instruction, *, request_id, guide_context=None):
        calls.append((request_id, deepcopy(guide_context)))
        raise lab_client.LabClientError("请求状态未知")

    monkeypatch.setattr(lab_client, "assistant_submit", uncertain)
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("继续讨论这个算法").run()
    _widget(app.button, "生成可编辑草案").click().run()
    if change == "notes":
        _widget(app.text_area, "已确认的设计笔记").set_value("新的用户决定").run()
    else:
        app.session_state[lab_ui._HISTORY_KEY] = [{"role": "user", "content": "另外保留每成员步长。"}]
        app.run()
    _widget(app.button, "生成可编辑草案").click().run()
    _assert_ok(app)
    assert len(calls) == 2
    assert calls[0][0] != calls[1][0]
    assert calls[0][1] != calls[1][1]
    if change == "notes":
        assert calls[1][1]["design_notes"] == "新的用户决定"
    assert trial_client["submitted"] == []


def test_design_notes_follow_guidance_between_navigation_pages(app, trial_client, assistant_client):
    assistant_client["questions"] = ["交叉后哪些成员字段要重算？"]
    app.run()
    _widget(app.text_area, "已确认的设计笔记").set_value("只替换交叉，不改变问题和选择规则。").run()
    _widget(app.text_area, "描述想怎么调整算法").set_value("帮我确认可以复用哪些接口").run()
    _widget(app.button, "请 AI 调整装配").click().run()
    _assert_ok(app)
    context = assistant_client["guide_contexts"][-1]
    assert context["stage"] == "assembly"
    assert context["design_notes"] == "只替换交叉，不改变问题和选择规则。"
    assert _widget(app.text_area, "已确认的设计笔记").value == context["design_notes"]


@pytest.mark.parametrize("context_shape", ["context", "list"])
def test_framework_evidence_is_static_source_text_not_running_proof_or_links(app, trial_client, assistant_client, context_shape):
    source = {"path": "units/population.py", "line": 10, "end_line": 18, "sha256": "a" * 64}
    evidence = [
        {"id": "member-fields", "title": "成员字段维护", "source": source,
         "online_bound": False, "excerpt": "member_fields = (...)"},
        {"id": "bad-location", "title": "忽略任意地址", "source": {**source, "path": "https://external.invalid/"},
         "excerpt": "不应展示这个外部来源"}]
    if context_shape == "context":
        evidence = {"schema": "nsgablack.lab_framework_context/v1", "evidence_level": "static_source",
                    "contracts": evidence[:1], "components": evidence[1:], "limitations": []}
    assistant_client["result_override"] = {"draft": None, "framework_evidence": evidence}
    app.run()
    _widget(app.text_area, "描述要解决的问题").set_value("每成员步长怎样维护").run()
    _widget(app.button, "生成可编辑草案").click().run()
    _assert_ok(app)
    assert any("units/population.py:10–18" in item.value for item in app.caption)
    assert any("不构成实际运行" in item.value for item in app.caption)
    assert any("尚未绑定" in item.value for item in app.caption)
    assert not any("external.invalid" in str(item.value) for item in app.caption)
    assert any("member_fields" in item.value for item in app.code)
    assert not any("不应展示这个外部来源" in item.value for item in app.code)
    assert trial_client["submitted"] == []


def test_workspace_restore_is_explicit_and_never_restores_jobs_or_auto_runs(app, trial_client, assistant_client):
    from nsgablack.catalog.lab_design import export_workspace
    from nsgablack.catalog.lab_assembly import normalize_assembly

    _widget(app.button, "开始小预算试跑").click().run()
    saved_spec = normalize_assembly(_profit_document())
    imported = export_workspace(saved_spec, design_notes="保留利润最大化，步长方案待开发。",
        history=[{"role": "user", "content": "我们确认先保留 GA。"}]).decode("utf-8")
    before = deepcopy(app.session_state[lab_ui._DRAFT_KEY])
    _widget(app.text_area, "粘贴工作区 JSON").set_value(imported).run()
    assert app.session_state[lab_ui._DRAFT_KEY] == before
    assert lab_ui._JOB_KEY in app.session_state
    _widget(app.button, "校验并恢复工作区").click().run()
    _assert_ok(app)
    assert app.session_state[lab_ui._DRAFT_KEY] == saved_spec
    assert _widget(app.text_area, "已确认的设计笔记").value == "保留利润最大化，步长方案待开发。"
    assert app.session_state[lab_ui._HISTORY_KEY] == [{"role": "user", "content": "我们确认先保留 GA。"}]
    assert lab_ui._JOB_KEY not in app.session_state
    assert lab_ui._AI_JOB_KEY not in app.session_state
    assert len(trial_client["submitted"]) == 1
    assert assistant_client["submitted"] == []
    assert any("导入内容尚未运行" in item.value for item in app.success)


def test_invalid_workspace_cannot_overwrite_any_confirmed_data(app, trial_client):
    from nsgablack.catalog.lab_design import export_workspace
    _widget(app.text_area, "已确认的设计笔记").set_value("当前已确认设计").run()
    before = deepcopy(app.session_state[lab_ui._DRAFT_KEY])
    value = json.loads(export_workspace(before))
    value["job"] = {"status": "succeeded", "code": "import os"}
    _widget(app.text_area, "粘贴工作区 JSON").set_value(json.dumps(value)).run()
    _widget(app.button, "校验并恢复工作区").click().run()
    _assert_ok(app)
    assert any("工作区未导入" in item.value for item in app.error)
    assert app.session_state[lab_ui._DRAFT_KEY] == before
    assert _widget(app.text_area, "已确认的设计笔记").value == "当前已确认设计"
    assert trial_client["submitted"] == []
