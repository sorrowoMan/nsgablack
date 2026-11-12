"""The editor loads only visible work and preserves formal experiment bindings."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nsgablack.catalog import lab_workspace_ui as ui


AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


class FakeStore:
    def __init__(self):
        self.root = Path("fake-local-workspaces")
        self.source_reads = 0
        self.workspace_reads, self.revision_reads, self.revision_lists, self.file_reads = [], [], [], []
        self.saves = []
        self.creates = []
        self.workspaces = {}
        self.revisions = {}
        self.contents = {}
        for suffix in ("a", "b"):
            wid, rid = suffix * 32, suffix * 31 + "0"
            content = {"project_config.py": "PROJECT_NAME = 'small'\n",
                "run_project.py": "pass\n", "cases/__init__.py": "",
                "cases/search/__init__.py": "",
                "cases/search/build_solver.py": "def build_solver():\n    return None\n",
                "cases/search/run_solver.py": "def main():\n    pass\n",
                "cases/search/change.py": "def change(value):\n    return value + 1\n",
                "cases/search/input.csv": "value\n1\n"}
            self.workspaces[wid] = {"workspace_id": wid, "head_revision": rid,
                "source_project_id": f"examples:project_{suffix}", "title": f"工作副本 {suffix.upper()}"}
            self._revision(wid, rid, content)

    def _revision(self, wid, rid, contents, parent=None):
        self.contents[wid, rid] = deepcopy(contents)
        self.revisions[wid, rid] = {"workspace_id": wid, "revision_id": rid,
            "parent_revision": parent, "source_digest": hashlib.sha256(json.dumps(contents).encode()).hexdigest(),
            "created_at": 1., "message": "",
            "files": [{"path": p, "size_bytes": len(text.encode()),
                       "sha256": hashlib.sha256(text.encode()).hexdigest(),
                       "kind": "data" if p.endswith(".csv") else "source"} for p, text in sorted(contents.items())]}

    def list_sources(self):
        self.source_reads += 1
        return [{"project_id": "examples:new", "title": "登记的 Project", "case_ids": ["search"]}]

    def list_workspaces(self):
        return deepcopy(list(self.workspaces.values()))

    def get_workspace(self, wid):
        self.workspace_reads.append(wid)
        return deepcopy(self.workspaces[wid])

    def get_revision(self, wid, revision_id=None):
        rid = revision_id or self.workspaces[wid]["head_revision"]
        self.revision_reads.append((wid, rid))
        return deepcopy(self.revisions[wid, rid])

    def list_revisions(self, wid):
        self.revision_lists.append(wid)
        return deepcopy([r for (w, _), r in self.revisions.items() if w == wid])

    def read_file(self, wid, rid, path):
        self.file_reads.append((wid, rid, path))
        value = self.contents[wid, rid][path]
        return {"path": path, "content": value, "encoding": "utf-8",
                "editable": not path.endswith(".csv"), "sha256": hashlib.sha256(value.encode()).hexdigest()}

    def save_files(self, wid, changes, *, expected_revision, message=""):
        if expected_revision != self.workspaces[wid]["head_revision"]:
            raise ValueError("最新修订已改变")
        self.saves.append((wid, deepcopy(changes), expected_revision, message))
        contents = {**self.contents[wid, expected_revision], **changes}
        rid = "c" * 31 + str(len(self.saves))
        self._revision(wid, rid, contents, expected_revision)
        self.revisions[wid, rid]["message"] = message
        self.workspaces[wid]["head_revision"] = rid
        return deepcopy(self.revisions[wid, rid])

    def create_workspace(self, project_id, *, title=None):
        self.creates.append((project_id, title))
        previous = self.workspaces["a" * 32]
        wid, rid = "d" * 32, "e" * 32
        self.workspaces[wid] = {"workspace_id": wid, "head_revision": rid,
            "source_project_id": project_id, "title": title or "新工作副本"}
        self._revision(wid, rid, self.contents[previous["workspace_id"], previous["head_revision"]])
        return deepcopy(self.workspaces[wid])


class FakeRunner:
    def __init__(self):
        self.submissions, self.checks, self.schemas = [], [], []
        self.jobs = {}
        self.submit_error = False
        self.parameter_properties = {}
        self.job_reads, self.job_lists = [], []

    def parameter_schema(self, wid, rid, case):
        self.schemas.append((wid, rid, case))
        return {"properties": deepcopy(self.parameter_properties),
                "parameter_mode": "declared" if self.parameter_properties else "none"}

    def check(self, wid, rid, case, **options):
        self.checks.append((wid, rid, case, deepcopy(options)))
        return {"ok": True, "diagnostics": [], "revision_id": rid}

    def submit(self, wid, rid, case, **options):
        self.submissions.append((wid, rid, case, deepcopy(options)))
        if self.submit_error:
            raise ValueError("暂未确认提交结果")
        identity = "1" * 31 + str(len(self.jobs))
        row = {"job_id": identity, "workspace_id": wid, "revision_id": rid,
            "source_digest": "f" * 64, "case_name": case, "status": "succeeded",
            "created_at": 1., "finished_at": 2., "error": None,
            "result": {"run_id": "project-trial-" + identity, "steps": 2,
                       "evaluations": 4, "elapsed_seconds": 1.25,
                       "resource_binding": {"current": True},
                       "raw_results": {"scope": "last_16_accepted", "refs": [{"token": "actual-token", "version": 1}],
                           "candidates": [[.25, .75]], "raw_objectives": [[.625]], "raw_violations": [0.]}}}
        self.jobs[identity] = row
        return deepcopy(row)

    def get_job(self, wid, identity):
        self.job_reads.append((wid, identity))
        row = self.jobs[identity]
        assert row["workspace_id"] == wid
        return deepcopy(row)

    def list_jobs(self, wid):
        self.job_lists.append(wid)
        return deepcopy([row for row in self.jobs.values() if row["workspace_id"] == wid])


@pytest.fixture
def runtime(monkeypatch):
    # AppTest exercises Python draft/runtime contracts. Production CodeMirror
    # behavior is covered by the independent headless editor acceptance.
    monkeypatch.setenv("NSGABLACK_WORKSPACE_PLAINTEXT_EDITOR", "1")
    from nsgablack.catalog.curation_provider import DeepSeekGenerator
    def forbidden(*args, **kwargs):
        raise AssertionError("Workspace UI contracts must not invoke a model")
    for method in ("generate", "review", "_complete"):
        monkeypatch.setattr(DeepSeekGenerator, method, forbidden)
    value = SimpleNamespace(store=FakeStore(), runner=FakeRunner())
    monkeypatch.setattr(ui, "_test_runtime", value, raising=False)
    return value


@pytest.fixture
def app(runtime):
    # Every widget rerun uses this bound too, not only the initial app.run.
    # Real Project validation/browser checks can share the same local CPU.
    return open_app()


def open_app():
    return AppTest.from_string("""import streamlit as st
from nsgablack.catalog import lab_workspace_ui as ui
ui.render_workspace(st, ui._test_runtime)
""", default_timeout=15).run()


def widget(elements, label):
    return next(item for item in elements if item.label == label)


def ok(app):
    assert not app.exception, [item.message for item in app.exception]


def test_hosted_workspace_can_use_explicit_remote_runtime(runtime):
    runtime.mode = "remote"
    app = AppTest.from_string("""import streamlit as st
from nsgablack.catalog import lab_workspace_ui as ui
ui.render_workspace(st, ui._test_runtime, hosted=True)
""", default_timeout=15).run()
    ok(app)
    assert widget(app.text_area, "文件内容").value
    assert runtime.runner.submissions == runtime.runner.checks == []
    assert runtime.runner.schemas == []


@pytest.mark.parametrize("hosted", [False, True])
def test_streamlit_file_entrypoint_renders_and_reaches_run_result(runtime, monkeypatch, hosted):
    # Match both the launcher and Docker CMD, not a package-import wrapper.
    from nsgablack.catalog import lab_workspace
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1" if hosted else "0")
    if hosted:
        monkeypatch.setenv(lab_workspace.REMOTE_ENV, "explicit-test-remote-client.json")
    else:
        monkeypatch.delenv(lab_workspace.REMOTE_ENV, raising=False)
    runtime.mode = "remote" if hosted else "local"
    monkeypatch.setattr(lab_workspace, "get_workspace_runtime", lambda: runtime)
    app = AppTest.from_file(ui.__file__, default_timeout=15).run()
    ok(app)
    assert not app.error
    assert widget(app.radio, "文件范围").value == "all"
    assert not runtime.runner.schemas
    assert not any(item.label == "参数填写方式" for item in app.radio)
    assert runtime.runner.submissions == []
    edit(app)
    save(app)
    show_run(app)
    widget(app.button, "静态校验").click().run()
    widget(app.button, "开始试跑").click().run()
    ok(app)
    assert not app.error
    assert len(runtime.runner.submissions) == 1
    assert any("Case 试跑完成" in row.value for row in app.success)
    assert widget(app.text_area, "文件内容").value
    assert not runtime.runner.job_lists and not runtime.runner.job_reads
    widget(app.button, "查看本次结果").click().run()
    ok(app)
    assert widget(app.selectbox, "查看实验记录").value in runtime.runner.jobs


def test_hosted_workspace_refuses_local_runtime_even_if_remote_env_present(runtime, monkeypatch):
    from nsgablack.catalog.lab_workspace import REMOTE_ENV
    monkeypatch.setenv(REMOTE_ENV, "operator-configured-client.json")
    runtime.mode = "local"
    runtime.store.list_workspaces = lambda: pytest.fail("hosted page entered local store")
    app = AppTest.from_string("""import streamlit as st
from nsgablack.catalog import lab_workspace_ui as ui
ui.render_workspace(st, ui._test_runtime, hosted=True)
""", default_timeout=15).run()
    ok(app)
    assert any("不能在网页服务内执行" in item.value for item in app.error)
    assert not app.text_area


def test_remote_offline_shows_connection_error_without_execution(runtime):
    runtime.mode = "remote"
    def offline():
        raise ValueError("本机连接不可用，请确认电脑在线。")
    runtime.store.list_workspaces = offline
    app = AppTest.from_string("""import streamlit as st
from nsgablack.catalog import lab_workspace_ui as ui
ui.render_workspace(st, ui._test_runtime, hosted=True)
""", default_timeout=15).run()
    ok(app)
    assert any("本机" in item.value and ("连接" in item.value or "离线" in item.value)
               for item in app.warning)
    assert not app.text_area
    assert runtime.runner.submissions == []


def edit(app, value="def build_solver():\n    return 123\n"):
    wid = widget(app.selectbox, "工作副本").value
    if app.session_state.filtered_state.get(ui._PREFIX + f"panel::{wid}") == "results":
        widget(app.button, "返回代码").click().run()
    widget(app.text_area, "文件内容").set_value(value).run()
    ok(app)


def all_files(app):
    widget(app.radio, "文件范围").set_value("all").run()
    ok(app)


def show_run(app):
    wid = widget(app.selectbox, "工作副本").value
    if app.session_state.filtered_state.get(ui._PREFIX + f"panel::{wid}") != "run":
        widget(app.button, "试跑设置").click().run()
    ok(app)


def show_results(app):
    wid = widget(app.selectbox, "工作副本").value
    if app.session_state.filtered_state.get(ui._PREFIX + f"panel::{wid}") != "results":
        widget(app.button, "实验结果").click().run()
    ok(app)


def json_parameters(app):
    show_run(app)
    widget(app.radio, "参数填写方式").set_value("JSON").run()
    ok(app)


def save(app):
    widget(app.button, "保存").click().run()
    ok(app)


def test_reading_and_switching_files_do_not_execute_or_import_project(app, runtime):
    ok(app)
    all_files(app)
    widget(app.selectbox, "工程文件").select("cases/search/change.py").run()
    ok(app)
    assert runtime.runner.submissions == runtime.runner.checks == []
    assert runtime.runner.schemas == []
    assert runtime.store.saves == []
    assert "return value + 1" in widget(app.text_area, "文件内容").value


def test_save_changes_whole_draft_with_revision_compare_and_swap(app, runtime):
    base = runtime.store.workspaces["a" * 32]["head_revision"]
    edit(app)
    show_run(app)
    assert widget(app.button, "开始试跑").disabled
    assert widget(app.button, "静态校验").disabled
    widget(app.text_input, "修订说明").set_value("改变返回值").run()
    save(app)
    assert runtime.store.saves == [("a" * 32,
        {"cases/search/build_solver.py": "def build_solver():\n    return 123\n"}, base, "改变返回值")]
    assert runtime.runner.submissions == []
    assert not widget(app.button, "开始试跑").disabled


def test_drafts_survive_file_workspace_and_page_reruns(app, runtime):
    edit(app)
    all_files(app)
    widget(app.selectbox, "工程文件").select("cases/search/change.py").run()
    edit(app, "def change(value):\n    return value + 2\n")
    widget(app.selectbox, "工作副本").select("b" * 32).run()
    ok(app)
    show_run(app)
    assert not widget(app.button, "开始试跑").disabled
    widget(app.selectbox, "工作副本").select("a" * 32).run()
    ok(app)
    assert len(app.session_state[ui._DRAFTS]["a" * 32]["changes"]) == 2
    widget(app.selectbox, "工程文件").select("cases/search/build_solver.py").run()
    assert "return 123" in widget(app.text_area, "文件内容").value
    save(app)
    assert len(runtime.store.saves[0][1]) == 2


def test_discard_reloads_original_instead_of_retaining_stale_widget_value(app, runtime):
    edit(app)
    widget(app.button, "放弃草稿并载入最新修订").click().run()
    ok(app)
    assert widget(app.text_area, "文件内容").value == "def build_solver():\n    return None\n"
    assert widget(app.button, "保存").disabled
    assert runtime.store.saves == []


def test_external_head_change_preserves_but_blocks_stale_draft(app, runtime):
    edit(app)
    wid = "a" * 32
    runtime.store.save_files(wid, {"project_config.py": "PROJECT_NAME = 'outside'\n"},
                            expected_revision=runtime.store.workspaces[wid]["head_revision"])
    app.run()
    ok(app)
    assert widget(app.button, "保存").disabled
    assert any("草稿保留" in item.value and "新版本" in item.value for item in app.warning)
    assert app.session_state[ui._DRAFTS][wid]["changes"]["cases/search/build_solver.py"].endswith("123\n")


def test_static_check_and_parameter_contract_do_not_submit_run(app, runtime):
    show_run(app)
    ok(app)
    assert any("没有可调整的额外参数" in item.value for item in app.info)
    widget(app.button, "静态校验").click().run()
    ok(app)
    assert len(runtime.runner.schemas) == len(runtime.runner.checks) == 1
    assert runtime.runner.submissions == []
    assert any("静态校验通过" in item.value for item in app.success)


def test_explicit_run_is_bound_to_saved_revision_and_not_repeated_by_refresh(app, runtime):
    edit(app)
    save(app)
    wid, rid = "a" * 32, runtime.store.workspaces["a" * 32]["head_revision"]
    show_run(app)
    widget(app.button, "开始试跑").click().run()
    ok(app)
    assert len(runtime.runner.submissions) == 1
    submitted = runtime.runner.submissions[0]
    assert submitted[:3] == (wid, rid, "search")
    assert submitted[3]["max_steps"] == 2 and submitted[3]["parameters"] == {}
    assert len(submitted[3]["request_id"]) == 32
    assert any("Case 试跑完成" in row.value for row in app.success)
    app.run()
    assert len(runtime.runner.submissions) == 1
    assert widget(app.text_area, "文件内容").value
    assert not runtime.runner.job_lists and not runtime.runner.job_reads
    widget(app.button, "查看本次结果").click().run()
    ok(app)
    assert [row.value for row in app.metric] == ["2", "4", "1.25 s"]


def test_failed_submit_reuses_exact_intent_identity(app, runtime):
    show_run(app)
    runtime.runner.submit_error = True
    widget(app.button, "开始试跑").click().run()
    ok(app)
    first = deepcopy(runtime.runner.submissions[-1])
    runtime.runner.submit_error = False
    widget(app.button, "开始试跑").click().run()
    ok(app)
    assert runtime.runner.submissions[-1] == first


def test_new_revision_marks_previous_result_as_old(app, runtime):
    show_run(app)
    widget(app.button, "开始试跑").click().run()
    old = runtime.runner.submissions[0][1]
    edit(app)
    save(app)
    assert runtime.store.workspaces["a" * 32]["head_revision"] != old
    show_results(app)
    assert any("旧修订的实验记录" in item.value for item in app.warning)
    assert len(runtime.runner.submissions) == 1
    assert next(iter(runtime.runner.jobs.values()))["revision_id"] == old


def test_history_revision_is_read_only_and_data_does_not_become_code(app, runtime):
    original = runtime.store.workspaces["a" * 32]["head_revision"]
    edit(app)
    save(app)
    widget(app.selectbox, "工程修订").select(original).run()
    ok(app)
    assert not app.text_area or all(item.label != "文件内容" for item in app.text_area)
    assert any("历史版本" in item.value and "只读" in item.value for item in app.caption)
    assert widget(app.button, "保存").disabled
    all_files(app)
    widget(app.selectbox, "工程文件").select("cases/search/input.csv").run()
    ok(app)
    assert any("数据文件保持只读" in item.value for item in app.info)


def test_invalid_parameter_json_disables_execution(app, runtime):
    json_parameters(app)
    widget(app.text_area, "Case 参数 JSON").set_value("[]").run()
    ok(app)
    assert widget(app.button, "开始试跑").disabled
    assert widget(app.button, "静态校验").disabled
    assert runtime.runner.submissions == []


@pytest.mark.parametrize("invalid", ['{"weight": NaN}', '{"weight": Infinity}',
    '{"weight": -Infinity}', '{"weight": 1e999}', '{"nested": [0, NaN]}'])
def test_non_finite_json_does_not_crash_action_signatures(app, runtime, invalid):
    json_parameters(app)
    widget(app.text_area, "Case 参数 JSON").set_value(invalid).run()
    ok(app)
    assert widget(app.button, "开始试跑").disabled
    assert widget(app.button, "静态校验").disabled
    assert runtime.runner.submissions == runtime.runner.checks == []


@pytest.mark.parametrize("label,value", [("逻辑步预算", 3), ("超时（秒）", 65), ("随机种子", 43)])
def test_changed_run_options_mark_old_static_check(app, runtime, label, value):
    show_run(app)
    widget(app.button, "静态校验").click().run()
    assert any("静态校验通过" in row.value for row in app.success)
    widget(app.number_input, label).set_value(value).run()
    ok(app)
    assert any("另一个修订或运行配置" in row.value for row in app.warning)
    assert not any("静态校验通过" in row.value for row in app.success)
    assert len(runtime.runner.checks) == 1 and not runtime.runner.submissions


def test_changed_case_parameters_mark_old_static_check(app, runtime):
    show_run(app)
    widget(app.button, "静态校验").click().run()
    json_parameters(app)
    widget(app.text_area, "Case 参数 JSON").set_value('{"weight": 0.5}').run()
    ok(app)
    assert any("另一个修订或运行配置" in row.value for row in app.warning)
    assert not any("静态校验通过" in row.value for row in app.success)


def test_editing_after_check_does_not_claim_draft_was_checked(app, runtime):
    show_run(app)
    widget(app.button, "静态校验").click().run()
    edit(app)
    assert any("不覆盖当前未保存草稿" in row.value for row in app.warning)
    assert not any("静态校验通过" in row.value for row in app.success)
    assert len(runtime.runner.checks) == 1 and not runtime.runner.submissions


def test_new_submission_selects_its_own_record(app, runtime):
    show_run(app)
    widget(app.button, "开始试跑").click().run()
    widget(app.button, "查看本次结果").click().run()
    first = widget(app.selectbox, "查看实验记录").value
    show_run(app)
    widget(app.number_input, "逻辑步预算").set_value(3).run()
    widget(app.button, "开始试跑").click().run()
    ok(app)
    assert len(runtime.runner.submissions) == 2
    assert widget(app.text_area, "文件内容").value
    widget(app.button, "查看本次结果").click().run()
    assert widget(app.selectbox, "查看实验记录").value != first
    assert widget(app.selectbox, "查看实验记录").value == list(runtime.runner.jobs)[-1]


def test_history_selection_labels_do_not_cache_dynamic_job_status(app, runtime):
    show_run(app)
    widget(app.button, "开始试跑").click().run()
    widget(app.button, "查看本次结果").click().run()
    before = list(widget(app.selectbox, "查看实验记录").options)
    identity = next(iter(runtime.runner.jobs))
    runtime.runner.jobs[identity]["status"] = "failed"
    runtime.runner.jobs[identity]["error"] = {"message": "本次受控失败"}
    app.run()
    ok(app)
    assert widget(app.selectbox, "查看实验记录").options == before
    assert all("成功" not in label and "失败" not in label and "运行中" not in label for label in before)
    assert any("本次受控失败" in item.value for item in app.error)


def test_create_uses_registered_handle_and_opens_new_copy(app, runtime):
    widget(app.button, "打开工程").click().run()
    ok(app)
    widget(app.text_input, "工作副本名称（可选）").set_value("我的实验").run()
    widget(app.button, "创建工作副本").click().run()
    ok(app)
    assert runtime.store.creates == [("examples:new", "我的实验")]
    assert widget(app.selectbox, "工作副本").value == "d" * 32
    assert runtime.runner.submissions == []


def test_source_display_cache_survives_editing_until_explicit_refresh(app, runtime):
    assert runtime.store.source_reads == 0
    widget(app.button, "打开工程").click().run()
    ok(app)
    assert runtime.store.source_reads == 1
    widget(app.button, "刷新来源 Project").click().run()
    assert runtime.store.source_reads == 2
    widget(app.button, "返回编辑").click().run()
    edit(app)
    all_files(app)
    widget(app.selectbox, "工程文件").select("cases/search/change.py").run()
    edit(app, "def change(value):\n    return value + 2\n")
    ok(app)
    assert runtime.store.source_reads == 2
    widget(app.button, "打开工程").click().run()
    ok(app)
    assert runtime.store.source_reads == 2
    assert len(app.session_state[ui._DRAFTS]["a" * 32]["changes"]) == 2
    app.run()
    assert runtime.store.source_reads == 2


def test_source_display_cache_is_scoped_to_store_root(app, runtime):
    assert runtime.store.source_reads == 0
    widget(app.button, "打开工程").click().run()
    assert runtime.store.source_reads == 1
    runtime.store.root = Path("another-local-workspaces")
    app.run()
    ok(app)
    assert runtime.store.source_reads == 2
    runtime.store.root = Path("fake-local-workspaces")
    app.run()
    ok(app)
    assert runtime.store.source_reads == 2


def test_editor_first_load_and_edits_do_not_scan_sources_parameters_or_results(runtime):
    runtime.store.list_sources = lambda: pytest.fail("closed Project dialog scanned source Projects")
    runtime.runner.parameter_schema = lambda *a, **k: pytest.fail("closed run panel read parameters")
    runtime.runner.list_jobs = lambda *a, **k: pytest.fail("closed results panel read history")
    runtime.runner.get_job = lambda *a, **k: pytest.fail("closed results panel read a full result")
    app = open_app()
    ok(app)
    assert widget(app.text_area, "文件内容").value
    assert not any(item.label == "参数填写方式" for item in app.radio)
    assert not any(item.label == "查看实验记录" for item in app.selectbox)
    edit(app)
    all_files(app)
    widget(app.selectbox, "工程文件").select("cases/search/change.py").run()
    app.run()
    ok(app)
    assert runtime.store.saves == runtime.runner.submissions == []


def test_editor_reuses_head_manifest_and_reads_only_the_selected_file(app, runtime):
    wid = "a" * 32
    rid = runtime.store.workspaces[wid]["head_revision"]
    assert runtime.store.revision_lists == [wid]
    assert runtime.store.file_reads == [(wid, rid, "cases/search/build_solver.py")]
    edit(app)
    app.run()
    ok(app)
    assert runtime.store.revision_lists == [wid]
    assert runtime.store.file_reads == [(wid, rid, "cases/search/build_solver.py")]
    all_files(app)
    widget(app.selectbox, "工程文件").select("cases/search/change.py").run()
    ok(app)
    assert runtime.store.revision_lists == [wid]
    assert runtime.store.file_reads == [(wid, rid, "cases/search/build_solver.py"),
                                        (wid, rid, "cases/search/change.py")]
    save(app)
    assert runtime.store.revision_lists == [wid, wid]
    assert runtime.store.file_reads[-1] == (wid, runtime.store.workspaces[wid]["head_revision"],
                                          "cases/search/change.py")


def test_lost_local_connection_preserves_loaded_editor_and_reconnects_without_saving(app, runtime):
    wid = "a" * 32
    list_workspaces = runtime.store.list_workspaces
    def offline():
        raise ValueError("本机连接不可用")
    runtime.store.list_workspaces = offline
    app.run()
    ok(app)
    assert widget(app.text_area, "文件内容").value
    edit(app)
    assert widget(app.button, "保存").disabled
    assert any("离线" in row.value for row in app.warning)
    pending = deepcopy(app.session_state[ui._DRAFTS][wid]["changes"])
    runtime.store.list_workspaces = list_workspaces
    app.run()
    ok(app)
    assert not widget(app.button, "保存").disabled
    assert app.session_state[ui._DRAFTS][wid]["changes"] == pending
    assert runtime.store.saves == runtime.runner.submissions == []


def test_only_explicitly_opened_panel_reads_its_own_data(app, runtime):
    assert runtime.store.source_reads == 0
    assert runtime.runner.schemas == runtime.runner.job_lists == runtime.runner.job_reads == []
    show_run(app)
    assert len(runtime.runner.schemas) == 1
    assert runtime.store.source_reads == 0 and runtime.runner.job_lists == []
    widget(app.button, "关闭").click().run()
    ok(app)
    assert not any(item.label == "参数填写方式" for item in app.radio)
    show_results(app)
    assert runtime.runner.job_lists
    assert runtime.runner.job_reads == []
    assert runtime.store.source_reads == 0 and len(runtime.runner.schemas) == 1
    before = len(runtime.runner.job_lists)
    widget(app.button, "返回代码").click().run()
    edit(app)
    assert len(runtime.runner.job_lists) == before


def test_empty_workspace_first_view_does_not_automatically_read_sources(runtime):
    runtime.store.workspaces.clear()
    app = open_app()
    ok(app)
    assert runtime.store.source_reads == 0
    assert runtime.runner.schemas == runtime.runner.job_lists == []
    widget(app.button, "打开工程").click().run()
    ok(app)
    assert runtime.store.source_reads == 1


def test_run_panel_closing_preserves_budget_seed_and_explicit_parameters(runtime):
    runtime.runner.parameter_properties = {"weight": {"type": "float", "default": .5,
                                                      "minimum": 0., "maximum": 1.}}
    app = open_app()
    show_run(app)
    widget(app.checkbox, "调整 weight").check().run()
    widget(app.number_input, "weight").set_value(.8).run()
    widget(app.number_input, "逻辑步预算").set_value(5).run()
    widget(app.number_input, "随机种子").set_value(123).run()
    widget(app.button, "关闭").click().run()
    edit(app)
    save(app)
    show_run(app)
    assert widget(app.number_input, "weight").value == .8
    assert widget(app.number_input, "逻辑步预算").value == 5
    assert widget(app.number_input, "随机种子").value == 123
    widget(app.button, "开始试跑").click().run()
    ok(app)
    options = runtime.runner.submissions[-1][-1]
    assert options["max_steps"] == 5 and options["seed"] == 123
    assert options["parameters"] == {"weight": .8}


def test_hosted_mode_returns_before_loading_local_runtime(runtime):
    app = AppTest.from_string("""import streamlit as st
from nsgablack.catalog import lab_workspace_ui as ui
ui.render_workspace(st, ui._test_runtime, hosted=True)
""", default_timeout=15).run()
    ok(app)
    assert not app.button and not app.text_area
    assert any("未配置" in item.value for item in app.info)
    assert runtime.runner.submissions == []


def test_declared_parameter_form_submits_only_enabled_overrides(runtime):
    runtime.runner.parameter_properties = {
        "weight": {"type": "float", "default": .5, "minimum": 0., "maximum": 1., "description": "软偏好权重"},
        "use_bias": {"type": "bool", "default": True},
    }
    app = open_app()
    ok(app)
    show_run(app)
    assert not any(item.label == "Case 参数 JSON" for item in app.text_area)
    widget(app.button, "静态校验").click().run()
    assert runtime.runner.checks[-1][-1]["parameters"] == {}
    widget(app.checkbox, "调整 weight").check().run()
    widget(app.number_input, "weight").set_value(.8).run()
    widget(app.checkbox, "调整 use_bias").check().run()
    widget(app.checkbox, "use_bias").uncheck().run()
    widget(app.button, "开始试跑").click().run()
    ok(app)
    assert runtime.runner.submissions[-1][-1]["parameters"] == {"weight": .8, "use_bias": False}
    draft_key = ui._PREFIX + f"parameter_draft::{'a' * 32}::search"
    assert app.session_state[draft_key]["overrides"] == {"weight": .8, "use_bias": False}, "after first submission"
    show_run(app)
    assert app.session_state[draft_key]["overrides"] == {"weight": .8, "use_bias": False}, "after reopen"
    assert widget(app.checkbox, "调整 use_bias").value
    assert widget(app.checkbox, "use_bias").value is False
    widget(app.checkbox, "调整 weight").uncheck().run()
    assert app.session_state[draft_key]["overrides"] == {"use_bias": False}, "after removing weight"
    widget(app.button, "开始试跑").click().run()
    assert runtime.runner.submissions[-1][-1]["parameters"] == {"use_bias": False}


def test_large_original_default_is_never_automatically_shrunk(runtime):
    runtime.runner.parameter_properties = {"population_size": {
        "type": "int", "default": 300, "minimum": 1, "maximum": 128,
        "requires_override": True, "bounds_source": "trial_resource_policy"}}
    app = open_app()
    ok(app)
    show_run(app)
    assert widget(app.button, "开始试跑").disabled
    assert runtime.runner.submissions == []
    assert any("原默认值超出快速试跑范围" in row.value for row in app.warning)
    widget(app.checkbox, "调整 population_size").check().run()
    ok(app)
    assert widget(app.number_input, "population_size").value is None
    assert widget(app.button, "开始试跑").disabled
    widget(app.number_input, "population_size").set_value(30).run()
    widget(app.button, "开始试跑").click().run()
    ok(app)
    assert runtime.runner.submissions[-1][-1]["parameters"] == {"population_size": 30}
    assert runtime.runner.parameter_properties["population_size"]["default"] == 300


def test_historical_source_outline_cannot_read_current_unsaved_draft(app, runtime, monkeypatch):
    from nsgablack.catalog import lab_workspace_review
    seen, original_outline = [], lab_workspace_review.review_source
    def capture(path, source):
        seen.append((path, source))
        return original_outline(path, source)
    monkeypatch.setattr(lab_workspace_review, "review_source", capture)
    original = runtime.store.workspaces["a" * 32]["head_revision"]
    edit(app)
    save(app)
    edit(app, "def newest_draft():\n    return 99\n")
    widget(app.selectbox, "工程修订").select(original).run()
    ok(app)
    assert seen[-1] == ("cases/search/build_solver.py", "def build_solver():\n    return None\n")
    assert app.session_state[ui._DRAFTS]["a" * 32]["changes"]["cases/search/build_solver.py"].startswith("def newest_draft")


def test_case_switch_changes_execution_target_without_discarding_edits(runtime):
    wid, rid = "a" * 32, runtime.store.workspaces["a" * 32]["head_revision"]
    contents = {**runtime.store.contents[wid, rid],
        "cases/second/build_solver.py": "def build_solver():\n    return 2\n",
        "cases/second/run_solver.py": "def main():\n    pass\n"}
    runtime.store._revision(wid, rid, contents)
    app = open_app()
    show_run(app)
    edit(app)
    widget(app.selectbox, "运行 Case").select("second").run()
    ok(app)
    assert widget(app.selectbox, "工程文件").value == "cases/second/build_solver.py"
    # Moving to the other Case returns to its file; execution stays explicit.
    assert app.session_state.filtered_state.get(ui._PREFIX + f"panel::{wid}") is None
    show_run(app)
    assert widget(app.button, "开始试跑").disabled
    assert app.session_state[ui._DRAFTS][wid]["changes"]["cases/search/build_solver.py"].endswith("123\n")
    assert {item[2] for item in runtime.runner.schemas} == {"search", "second"}
    save(app)
    widget(app.button, "开始试跑").click().run()
    ok(app)
    assert runtime.runner.submissions[-1][2] == "second"


def test_result_comparison_uses_selected_records_and_keeps_scope_clear(app, runtime):
    show_run(app)
    widget(app.button, "开始试跑").click().run()
    first = next(iter(runtime.runner.jobs))
    edit(app)
    widget(app.text_input, "修订说明").set_value("加入精英规则").run()
    save(app)
    show_run(app)
    widget(app.button, "开始试跑").click().run()
    widget(app.button, "查看本次结果").click().run()
    widget(app.selectbox, "对照实验").select(first).run()
    ok(app)
    assert any("与对照实验相比" in row.value for row in app.markdown)
    assert any("接纳历史" in row.value for row in app.caption)
    assert any("数据" in row.value and ("未" in row.value or "核验" in row.value) for row in app.caption)
    assert len(runtime.runner.submissions) == 2


def test_json_unknown_parameter_stops_before_formal_submission(app, runtime):
    json_parameters(app)
    widget(app.text_area, "Case 参数 JSON").set_value('{"invented": 3}').run()
    ok(app)
    assert widget(app.button, "开始试跑").disabled
    assert any("未公开声明" in row.value for row in app.error)
    assert not runtime.runner.submissions


@pytest.fixture
def lookup_reference(monkeypatch):
    from nsgablack.catalog import lab_workspace_reference as reference
    source = reference.ReferenceSource([
        {"key": "adapter.vns", "title": "VNSAdapter", "kind": "adapter", "summary": "从精英池进行邻域精修",
         "import_path": "nsgablack.adapters:VNSAdapter", "companions": ["tool.pool"],
         "minimal_wiring": ["from nsgablack.adapters import VNSAdapter", "adapter = VNSAdapter()"]},
        {"key": "tool.pool", "title": "Pool", "kind": "tool", "summary": "候选集合",
         "minimal_wiring": ["from nsgablack.adapters import Pool"]},
    ])
    monkeypatch.setattr(reference, "reference_source", lambda: source)
    return source


def test_component_dialog_search_copy_and_close_keeps_pending_file(app, runtime, lookup_reference):
    runtime.runner.parameter_properties = {"weight": {"type": "float", "default": .5,
                                                      "minimum": 0., "maximum": 1.}}
    show_run(app)
    widget(app.checkbox, "调整 weight").check().run()
    widget(app.number_input, "weight").set_value(.8).run()
    widget(app.number_input, "逻辑步预算").set_value(5).run()
    edit(app)
    widget(app.button, "查组件").click().run()
    ok(app)
    assert app.session_state[ui._PREFIX + f"panel::{'a' * 32}"] == "run"
    assert app.session_state["project_workspace::reference::open"] is True
    widget(app.text_input, "查组件").set_value("精英池").run()
    ok(app)
    assert any("VNSAdapter()" in row.value for row in app.code)
    assert runtime.store.saves == runtime.runner.submissions == []
    app.button(key="project_workspace::reference::close").click().run()
    ok(app)
    assert "return 123" in widget(app.text_area, "文件内容").value
    assert widget(app.selectbox, "工程文件").value == "cases/search/build_solver.py"
    assert not widget(app.button, "保存").disabled
    show_run(app)
    assert widget(app.checkbox, "调整 weight").value
    assert widget(app.number_input, "weight").value == .8
    assert widget(app.number_input, "逻辑步预算").value == 5


def test_component_dialog_relation_back_and_session_favorite(app, runtime, lookup_reference):
    widget(app.button, "查组件").click().run()
    ok(app)
    widget(app.button, "收藏组件").click().run()
    assert app.session_state["project_workspace::reference::favorites"] == ["adapter.vns"]
    relation = next(item for item in app.button if item.key == "project_workspace::reference::relation::adapter.vns::tool.pool")
    relation.click().run()
    ok(app)
    assert any(row.value == "Pool" for row in app.subheader)
    widget(app.button, "返回上一组件").click().run()
    ok(app)
    assert any(row.value == "VNSAdapter" for row in app.subheader)
    app.button(key="project_workspace::reference::close").click().run()
    assert app.session_state["project_workspace::reference::favorites"] == ["adapter.vns"]
    widget(app.button, "查组件").click().run()
    ok(app)
    assert app.session_state["project_workspace::reference::open"]
    assert app.session_state["project_workspace::reference::favorites"] == ["adapter.vns"]
    assert any(row.label == "adapter.vns" for row in app.button), " | ".join(row.label for row in app.button)
    assert runtime.runner.submissions == runtime.store.saves == []


def test_empty_reference_closes_without_losing_editor(app, runtime, monkeypatch):
    from nsgablack.catalog import lab_workspace_reference as reference
    monkeypatch.setattr(reference, "reference_source", lambda: reference.ReferenceSource(available=False))
    edit(app)
    widget(app.button, "查组件").click().run()
    ok(app)
    assert any("没有发布的组件资料" in row.value for row in app.info)
    widget(app.button, "返回编辑").click().run()
    assert "return 123" in widget(app.text_area, "文件内容").value
    assert not runtime.store.saves


def test_recent_file_return_preserves_both_unsaved_buffers(app, runtime):
    edit(app)
    all_files(app)
    app.button(key=ui._PREFIX + f"tree::{'a' * 32}::cases/search/change.py").click().run()
    edit(app, "def change(value):\n    return value + 7\n")
    app.button(key=ui._PREFIX + f"tab::{'a' * 32}::cases/search/build_solver.py").click().run()
    ok(app)
    assert "return 123" in widget(app.text_area, "文件内容").value
    assert len(app.session_state[ui._DRAFTS]["a" * 32]["changes"]) == 2
    assert runtime.store.saves == []


def test_collapsed_tree_only_reads_the_file_after_explicit_open(runtime):
    wid, rid = "a" * 32, runtime.store.workspaces["a" * 32]["head_revision"]
    target = "cases/search/extra/deep.py"
    runtime.store._revision(wid, rid, {**runtime.store.contents[wid, rid], target: "x = 2\n"})
    app = open_app()
    ok(app)
    tree_key = ui._PREFIX + f"tree::{wid}::{target}"
    assert not any(item.key == tree_key for item in app.button)
    before = list(runtime.store.file_reads)
    app.button(key=ui._PREFIX + f"folder::{wid}::cases/search/extra/::toggle").click().run()
    ok(app)
    assert any(item.key == tree_key for item in app.button)
    assert runtime.store.file_reads == before
    app.button(key=tree_key).click().run()
    ok(app)
    assert widget(app.text_area, "文件内容").value == "x = 2\n"
    assert runtime.store.file_reads == [*before, (wid, rid, target)]
    assert runtime.store.saves == runtime.runner.submissions == []


def test_review_previews_fix_then_applies_only_to_draft_and_can_undo(app, runtime):
    broken = "def build_solver()\n    return 123\n"
    repaired = "def build_solver():\n    return 123\n"
    edit(app, broken)
    widget(app.button, "审查").click().run()
    ok(app)
    assert any(row.proto.language == "diff" and "-def build_solver()" in row.value
               and "+def build_solver():" in row.value for row in app.code)
    assert widget(app.text_area, "文件内容").value == broken
    assert runtime.store.saves == runtime.runner.checks == runtime.runner.submissions == []
    widget(app.button, "应用到草稿").click().run()
    ok(app)
    assert widget(app.text_area, "文件内容").value == repaired
    assert any("尚未保存或运行" in row.value for row in app.caption)
    assert runtime.store.saves == runtime.runner.checks == runtime.runner.submissions == []
    widget(app.button, "撤销这次修复").click().run()
    ok(app)
    assert widget(app.text_area, "文件内容").value == broken
    assert runtime.store.saves == runtime.runner.checks == runtime.runner.submissions == []


@pytest.fixture
def component_app(runtime, monkeypatch):
    """Drive the host event protocol without claiming to run CodeMirror JS."""
    from nsgablack.catalog import lab_workspace_editor
    monkeypatch.delenv("NSGABLACK_WORKSPACE_PLAINTEXT_EDITOR", raising=False)
    props = []
    def component(**kwargs):
        import streamlit as st
        props.append(deepcopy(kwargs))
        return st.session_state.get(kwargs["key"])
    monkeypatch.setattr(lab_workspace_editor, "_declare_editor_component", lambda: component)
    app = open_app()
    ok(app)
    assert not any(row.label == "文件内容" for row in app.text_area)
    assert props[-1]["identity"] == app.session_state[ui._PREFIX + "active_editor"]["identity"]
    return app, props


def pending_event(app, text, sequence, command=None, *, identity=None):
    binding = deepcopy(app.session_state[ui._PREFIX + "active_editor"])
    app.session_state[binding["key"]] = {"identity": identity or binding["identity"],
        "text": text, "sequence": sequence, "command": command}
    return binding


def test_save_captures_newest_pending_component_buffer_before_persisting(component_app, runtime):
    app, _ = component_app
    pending_event(app, "def build_solver():\n    return 1\n", 1)
    app.run()
    ok(app)
    assert not widget(app.button, "保存").disabled
    latest = "def build_solver():\n    return 999\n"
    binding = pending_event(app, latest, 2)
    widget(app.button, "保存").click().run()
    ok(app)
    assert len(runtime.store.saves) == 1
    assert runtime.store.saves[0][1] == {binding["path"]: latest}
    assert runtime.store.saves[0][2] == binding["rid"]
    assert runtime.runner.checks == runtime.runner.submissions == []
    app.run()
    ok(app)
    assert len(runtime.store.saves) == 1


@pytest.mark.parametrize("damage", ["identity", "epoch"])
def test_stale_component_identity_or_epoch_cannot_write_a_draft(component_app, runtime, damage):
    app, _ = component_app
    binding = deepcopy(app.session_state[ui._PREFIX + "active_editor"])
    pending_event(app, "must not become a draft", 1,
                  identity=binding["identity"] + "-wrong" if damage == "identity" else None)
    if damage == "epoch":
        # Model discard/review replacing the editor before a queued blur event.
        app.session_state[ui._PREFIX + f"editor_epoch::{binding['wid']}"] = "replacement-epoch"
    app.run()
    ok(app)
    assert app.session_state[ui._DRAFTS][binding["wid"]]["changes"] == {}
    assert runtime.store.saves == runtime.runner.submissions == []


def test_duplicate_component_sequence_does_not_replace_the_accepted_buffer(component_app, runtime):
    app, _ = component_app
    accepted = "def build_solver():\n    return 1\n"
    binding = pending_event(app, accepted, 1)
    app.run()
    ok(app)
    pending_event(app, "out of order stale content", 1)
    app.run()
    ok(app)
    assert app.session_state[ui._DRAFTS][binding["wid"]]["changes"] == {binding["path"]: accepted}
    assert runtime.store.saves == runtime.runner.submissions == []


def test_ctrl_save_commits_its_newest_text_once_without_running(component_app, runtime):
    app, _ = component_app
    latest = "def build_solver():\n    return 777\n"
    binding = pending_event(app, latest, 1, "save")
    app.run()
    ok(app)
    assert len(runtime.store.saves) == 1
    assert runtime.store.saves[0][1] == {binding["path"]: latest}
    app.run()
    ok(app)
    assert len(runtime.store.saves) == 1
    assert runtime.runner.checks == runtime.runner.submissions == []


def test_file_switch_stages_the_old_component_buffer_under_its_own_identity(component_app, runtime):
    app, _ = component_app
    latest = "def build_solver():\n    return 222\n"
    binding = pending_event(app, latest, 1)
    widget(app.selectbox, "工程文件").select("cases/search/change.py").run()
    ok(app)
    assert app.session_state[ui._DRAFTS][binding["wid"]]["changes"] == {binding["path"]: latest}
    assert app.session_state[ui._PREFIX + "active_editor"]["path"] == "cases/search/change.py"
    assert runtime.store.saves == runtime.runner.submissions == []


def test_pending_edit_acknowledges_its_sequence_before_switch_and_remount(component_app, runtime):
    app, props = component_app
    first = "def build_solver():\n    return 111\n"
    binding = pending_event(app, first, 1)
    widget(app.selectbox, "工程文件").select("cases/search/change.py").run()
    ok(app)
    assert app.session_state[ui._DRAFTS][binding["wid"]]["changes"] == {binding["path"]: first}
    app.button(key=ui._PREFIX + f"tab::{binding['wid']}::{binding['path']}").click().run()
    ok(app)
    assert props[-1]["identity"] == binding["identity"]
    assert props[-1]["sequence_base"] >= 1, "Remount must continue after the old iframe's accepted event"
    second = "def build_solver():\n    return 222\n"
    pending_event(app, second, 2)
    app.run()
    ok(app)
    assert app.session_state[ui._DRAFTS][binding["wid"]]["changes"] == {binding["path"]: second}
    assert runtime.store.saves == runtime.runner.checks == runtime.runner.submissions == []


@pytest.mark.parametrize("action", ["apply", "undo"])
def test_review_action_never_overwrites_a_newer_pending_component_buffer(component_app, runtime, action):
    app, _ = component_app
    pending_event(app, "def build_solver()\n    return 123\n", 1)
    app.run()
    widget(app.button, "审查").click().run()
    ok(app)
    if action == "undo":
        widget(app.button, "应用到草稿").click().run()
        ok(app)
    latest = "def build_solver():\n    return 888\n"
    binding = pending_event(app, latest, 2)
    widget(app.button, "应用到草稿" if action == "apply" else "撤销这次修复").click().run()
    ok(app)
    assert app.session_state[ui._DRAFTS][binding["wid"]]["changes"] == {binding["path"]: latest}
    assert any("草稿已改变" in row.value for row in app.error)
    assert runtime.store.saves == runtime.runner.checks == runtime.runner.submissions == []


def test_file_search_with_no_match_retains_original_edit(app, runtime):
    edit(app)
    widget(app.text_input, "查找工程文件").set_value("does-not-exist").run()
    ok(app)
    assert any("没有匹配文件" in row.value for row in app.info)
    assert "return 123" in widget(app.text_area, "文件内容").value
    assert not widget(app.button, "保存").disabled
    widget(app.button, "清空文件搜索").click().run()
    assert widget(app.text_input, "查找工程文件").value == ""


def test_cross_case_file_search_keeps_execution_target_until_explicit_change(runtime):
    wid, rid = "a" * 32, runtime.store.workspaces["a" * 32]["head_revision"]
    runtime.store._revision(wid, rid, {**runtime.store.contents[wid, rid],
        "cases/second/build_solver.py": "def build_solver():\n    return 2\n",
        "cases/second/run_solver.py": "def main():\n    pass\n"})
    app = open_app()
    edit(app)
    widget(app.text_input, "查找工程文件").set_value("second").run()
    ok(app)
    assert widget(app.selectbox, "运行 Case").value == "search"
    assert "return 123" in widget(app.text_area, "文件内容").value
    widget(app.selectbox, "工程文件").select("cases/second/build_solver.py").run()
    ok(app)
    assert widget(app.selectbox, "运行 Case").value == "search"
    assert widget(app.selectbox, "工程文件").value == "cases/second/build_solver.py"
    assert app.session_state[ui._DRAFTS][wid]["changes"]
    assert any("正在查看 second" in row.value and "运行目标仍为 search" in row.value for row in app.caption)
    widget(app.button, "设为运行目标").click().run()
    ok(app)
    assert widget(app.selectbox, "运行 Case").value == "second"
    assert widget(app.selectbox, "工程文件").value == "cases/second/build_solver.py"
    assert runtime.runner.submissions == runtime.runner.checks == []


def test_static_diagnostic_opens_exact_file_and_source_line(app, runtime):
    show_run(app)
    def check(wid, rid, case, **options):
        return {"ok": False, "diagnostics": [{"path": "cases/search/change.py", "line": 2,
                "message": "测试诊断"}], "revision_id": rid}
    runtime.runner.check = check
    widget(app.button, "静态校验").click().run()
    widget(app.button, "打开 change.py").click().run()
    ok(app)
    assert widget(app.selectbox, "工程文件").value == "cases/search/change.py"
    assert any("报错位置" in row.value and "L2" in row.value for row in app.caption)
    assert any("2  " in row.value and "return value + 1" in row.value for row in app.code)
    assert not runtime.runner.submissions


def test_saving_source_keeps_the_same_case_parameter_overrides(runtime):
    runtime.runner.parameter_properties = {"weight": {"type": "float", "default": .5, "minimum": 0., "maximum": 1.}}
    app = open_app()
    show_run(app)
    widget(app.checkbox, "调整 weight").check().run()
    widget(app.number_input, "weight").set_value(.8).run()
    edit(app)
    save(app)
    ok(app)
    assert widget(app.checkbox, "调整 weight").value
    assert widget(app.number_input, "weight").value == .8
    widget(app.button, "开始试跑").click().run()
    assert runtime.runner.submissions[-1][-1]["parameters"] == {"weight": .8}


def test_case_switch_leaves_old_case_file_even_in_all_files_view(runtime):
    wid, rid = "a" * 32, runtime.store.workspaces["a" * 32]["head_revision"]
    runtime.store._revision(wid, rid, {**runtime.store.contents[wid, rid],
        "cases/second/build_solver.py": "def build_solver():\n    return 2\n",
        "cases/second/run_solver.py": "def main():\n    pass\n"})
    app = open_app()
    edit(app)
    all_files(app)
    widget(app.text_input, "查找工程文件").set_value("build_solver").run()
    widget(app.selectbox, "运行 Case").select("second").run()
    ok(app)
    assert widget(app.selectbox, "工程文件").value == "cases/second/build_solver.py"
    assert widget(app.text_input, "查找工程文件").value == ""
    assert app.session_state[ui._DRAFTS][wid]["changes"]["cases/search/build_solver.py"].endswith("123\n")


def test_responsibility_navigation_keeps_the_open_file_and_its_draft(app, runtime):
    edit(app)
    wid = "a" * 32
    selected = widget(app.selectbox, "工程文件").value
    reads = list(runtime.store.file_reads)
    # The fake Project has no problem group. Navigation still must not close
    # the currently edited file or select a different execution target.
    widget(app.radio, "文件范围").set_value("problem").run()
    ok(app)
    assert widget(app.selectbox, "工程文件").value == selected
    assert "return 123" in widget(app.text_area, "文件内容").value
    assert widget(app.selectbox, "运行 Case").value == "search"
    assert runtime.store.file_reads == reads
    assert app.session_state[ui._DRAFTS][wid]["changes"]
    assert runtime.store.saves == runtime.runner.submissions == []


def test_theme_switch_preserves_pending_editor_text_identity_and_scope(component_app, runtime):
    app, props = component_app
    assert widget(app.selectbox, "界面主题").value == "dark"
    assert props[-1]["theme"] == "dark"
    latest = "def build_solver():\n    return 987\n"
    binding = pending_event(app, latest, 1)
    for theme in ("light", "system", "dark"):
        widget(app.selectbox, "界面主题").select(theme).run()
        ok(app)
        assert props[-1]["theme"] == theme
        assert props[-1]["identity"] == binding["identity"]
        assert props[-1]["sequence_base"] >= 1
        assert app.session_state[ui._DRAFTS][binding["wid"]]["changes"] == {binding["path"]: latest}
        assert widget(app.selectbox, "运行 Case").value == "search"
    assert runtime.store.saves == runtime.runner.checks == runtime.runner.submissions == []


def test_running_job_status_updates_without_replacing_the_editor_or_reading_history(app, runtime):
    submit = runtime.runner.submit
    def running_submit(*args, **kwargs):
        job = submit(*args, **kwargs)
        runtime.runner.jobs[job["job_id"]]["status"] = "running"
        job["status"] = "running"
        return job
    runtime.runner.submit = running_submit
    show_run(app)
    path = widget(app.selectbox, "工程文件").value
    widget(app.button, "开始试跑").click().run()
    ok(app)
    assert widget(app.selectbox, "工程文件").value == path
    assert widget(app.text_area, "文件内容").value
    assert app.session_state[ui._PREFIX + f"panel::{'a' * 32}"] == "run"
    assert not runtime.runner.job_lists
    assert len(runtime.runner.submissions) == 1
    edit(app)
    identity = next(iter(runtime.runner.jobs))
    runtime.runner.jobs[identity]["status"] = "succeeded"
    app.run()
    ok(app)
    assert any("Case 试跑完成" in row.value for row in app.success)
    assert any("未覆盖未保存草稿" in row.value for row in app.caption)
    assert "return 123" in widget(app.text_area, "文件内容").value
    reads = list(runtime.runner.job_reads)
    app.run()
    ok(app)
    assert runtime.runner.job_reads == reads, "completed status must not poll the result on every keystroke"
    assert len(runtime.runner.submissions) == 1 and not runtime.runner.job_lists


def test_component_popup_can_be_pinned_without_losing_the_task_inputs(app, runtime, lookup_reference):
    edit(app)
    widget(app.button, "查组件").click().run()
    widget(app.text_input, "查组件").set_value("精英池").run()
    widget(app.button, "固定到右侧").click().run()
    ok(app)
    assert app.session_state[ui._PREFIX + f"panel::{'a' * 32}"] == "reference"
    assert not app.session_state["project_workspace::reference::open"]
    assert widget(app.text_input, "查组件").value == "精英池"
    assert "return 123" in widget(app.text_area, "文件内容").value
    assert runtime.store.saves == runtime.runner.submissions == []


def test_old_static_diagnostic_cannot_jump_to_a_new_draft_line(app, runtime):
    show_run(app)
    runtime.runner.check = lambda wid, rid, case, **options: {
        "ok": False, "diagnostics": [{"path": "cases/search/change.py", "line": 2, "message": "旧诊断"}]}
    widget(app.button, "静态校验").click().run()
    assert not widget(app.button, "打开 change.py").disabled
    edit(app)
    assert widget(app.button, "打开 change.py").disabled


@pytest.fixture
def frontend_verifier():
    path = Path(__file__).resolve().parents[1] / "deployment/workspace/verify_frontend.py"
    spec = importlib.util.spec_from_file_location("workspace_frontend_contract_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def editor_asset_fixture(tmp_path):
    directory = tmp_path / "editor"
    directory.mkdir()
    bundle = b"/* test-only asset bytes; no JavaScript is executed */"
    data = {"index.html": b"<script src='editor.bundle.js'></script>",
            "editor.css": b"body{}", "editor.bundle.js": bundle,
            "THIRD_PARTY_LICENSES.txt": b"fixture license"}
    data["build-manifest.json"] = json.dumps({"schema": "nsgablack.workspace-editor-assets/v1",
        "bundle": "editor.bundle.js", "bytes": len(bundle),
        "sha256": hashlib.sha256(bundle).hexdigest()}).encode()
    rows = []
    for name, content in data.items():
        path = directory / name
        path.write_bytes(content)
        rows.append({"image_path": str(path), "sha256": hashlib.sha256(content).hexdigest()})
    return directory, rows


def test_frontend_verifier_checks_editor_assets_without_claiming_javascript_execution(tmp_path, frontend_verifier):
    directory, rows = editor_asset_fixture(tmp_path)
    result = frontend_verifier.verify_editor_assets(directory, rows)
    assert result["javascript_executed"] is False
    assert result["files"] == {Path(row["image_path"]).name: row["sha256"] for row in rows}


@pytest.mark.parametrize("damage", ["unlisted", "changed_bundle", "build_digest"])
def test_frontend_verifier_rejects_missing_or_different_editor_assets(tmp_path, frontend_verifier, damage):
    directory, rows = editor_asset_fixture(tmp_path)
    if damage == "unlisted":
        rows = [row for row in rows if Path(row["image_path"]).name != "index.html"]
    elif damage == "changed_bundle":
        (directory / "editor.bundle.js").write_bytes(b"different bytes")
    else:
        path = directory / "build-manifest.json"
        data = json.loads(path.read_text())
        data["sha256"] = "f" * 64
        path.write_text(json.dumps(data), encoding="utf-8")
        next(row for row in rows if row["image_path"] == str(path))["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(AssertionError, match="editor_"):
        frontend_verifier.verify_editor_assets(directory, rows)
