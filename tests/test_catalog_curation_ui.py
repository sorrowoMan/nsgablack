from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from nsgablack.catalog import curation_ui


DIGEST = "a" * 64


@pytest.fixture(autouse=True)
def clean_knowledge_cache(monkeypatch):
    from nsgablack.catalog.curation_provider import DeepSeekGenerator

    def forbidden(*args, **kwargs):
        raise AssertionError("Knowledge presentation must not generate, review or complete AI material")

    for name in ("generate", "review", "_complete"):
        monkeypatch.setattr(DeepSeekGenerator, name, forbidden)
    curation_ui._load_snapshot.cache_clear()
    monkeypatch.delenv("NSGABLACK_CATALOG_KNOWLEDGE_ENABLED", raising=False)
    monkeypatch.delenv("NSGABLACK_CATALOG_KNOWLEDGE_INDEX", raising=False)
    monkeypatch.delenv("NSGABLACK_CATALOG_PROGRESS_PATH", raising=False)
    yield
    curation_ui._load_snapshot.cache_clear()


@pytest.fixture
def record():
    return {
        "entry_key": "adapter.vns", "source_digest": DIGEST, "model": "example-model",
        "prompt_version": "v1", "generated_at": "2026-10-22T06:00:00Z",
        "note": {
            "summary": "从当前候选开始进行邻域搜索。", "inputs_outputs": "输入候选，返回已评估的搜索结果。",
            "use_when": ["对已有候选做精修"], "assembly_steps": ["在标准 Case 绑定 VNS"],
            "pitfalls": ["比较规则须与任务一致"], "related_keys": ["adapter.nsga2", "example.demo"],
            "missing_information": ["未提供此装配的运行证据"], "evidence_ids": ["source-1"],
        },
        "evidence": [{"id": "source-1", "path": "nsgablack/adapters/vns/adapter.py",
                      "start_line": 10, "end_line": 11, "text": "class VNSAdapter:\n    pass",
                      "sha256": hashlib.sha256(b"class VNSAdapter:\n    pass").hexdigest()}],
    }


def configure_reader(monkeypatch, tmp_path, records, *, entries=None, profiles=None, prompt_version=None):
    path = tmp_path / "knowledge-sources.json"
    index = {
        "schema": curation_ui.INDEX_SCHEMA,
        "entries": entries if entries is not None else {
            "adapter.vns": DIGEST, "adapter.nsga2": "b" * 64, "example.demo": "c" * 64},
        "profiles": profiles if profiles is not None else {
            "default": ["adapter.vns", "adapter.nsga2", "example.demo"],
            "framework-core": ["adapter.vns", "adapter.nsga2"]},
    }
    if prompt_version is not None:
        index["prompt_version"] = prompt_version
    path.write_text(json.dumps(index), encoding="utf-8")
    monkeypatch.setenv("NSGABLACK_CATALOG_KNOWLEDGE_ENABLED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_KNOWLEDGE_INDEX", str(path))
    reads = []

    def read_records():
        reads.append(True)
        return records

    monkeypatch.setattr(curation_ui, "_read_records", read_records)
    return path, reads


def maintenance_panel(app):
    assert not app.exception, [item.message for item in app.exception]
    assert not app.get("progress"), "AI cache availability is not a completion progress bar"
    panels = [item for item in app.expander if item.label == "资料维护详情"]
    assert len(panels) == 1
    assert panels[0].proto.expanded is False
    return panels[0]


def visible_captions(block):
    """Read the initial page without treating collapsed maintenance as visible."""
    for node in block.children.values():
        if node.type == "expander":
            continue
        if hasattr(node, "children"):
            yield from visible_captions(node)
        elif node.type == "caption":
            yield node.value


def render_status_app(profile="default"):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    return AppTest.from_string(
        "import streamlit as st\nfrom nsgablack.catalog.curation_ui import render_status\n"
        f"render_status(st, profile={profile!r})\n", default_timeout=20).run()


def test_disabled_feature_reads_no_index_database_or_model(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Disabled feature must not load knowledge")

    monkeypatch.setattr(curation_ui, "_read_index", forbidden)
    monkeypatch.setattr(curation_ui, "_read_records", forbidden)
    assert curation_ui.entry_knowledge("adapter.vns") == {"status": "disabled"}
    app = render_status_app()
    assert not app.exception and not app.expander and not app.get("progress")


def test_read_snapshot_reuses_one_reader_for_component_and_summary(monkeypatch, tmp_path, record):
    _path, reads = configure_reader(monkeypatch, tmp_path, [record])
    assert curation_ui.entry_knowledge("adapter.vns")["status"] == "current"
    assert curation_ui.entry_knowledge("adapter.nsga2")["status"] == "missing"
    assert curation_ui.entry_knowledge("project.custom")["status"] == "unindexed"
    assert reads == [True]


def test_new_source_digest_invalidates_old_note(monkeypatch, tmp_path, record):
    record["source_digest"] = "d" * 64
    configure_reader(monkeypatch, tmp_path, [record])
    assert curation_ui.entry_knowledge("adapter.vns") == {"status": "stale"}


def test_new_prompt_version_invalidates_note_even_when_source_unchanged(monkeypatch, tmp_path, record):
    path, _reads = configure_reader(monkeypatch, tmp_path, [record])
    index = json.loads(path.read_text(encoding="utf-8"))
    index["prompt_version"] = "catalog-explainer-zh-v2"
    path.write_text(json.dumps(index), encoding="utf-8")
    assert curation_ui.entry_knowledge("adapter.vns") == {"status": "stale"}


def test_unknown_evidence_reference_is_not_renderable(monkeypatch, tmp_path, record):
    record["note"]["evidence_ids"] = ["invented-file"]
    configure_reader(monkeypatch, tmp_path, [record])
    assert curation_ui.entry_knowledge("adapter.vns") == {"status": "invalid"}


@pytest.mark.parametrize(("field", "value"), [
    ("path", "/opt/private/config.json"),
    ("path", "C:/private/config.json"),
    ("path", "nsgablack/../secrets/config.json"),
    ("sha256", "d" * 64),
    ("end_line", 99),
])
def test_corrupt_evidence_is_not_published_as_current_guidance(monkeypatch, tmp_path, record, field, value):
    record["evidence"][0][field] = value
    configure_reader(monkeypatch, tmp_path, [record])
    assert curation_ui.entry_knowledge("adapter.vns") == {"status": "invalid"}


def test_reader_error_discloses_no_private_configuration(monkeypatch, tmp_path):
    configure_reader(monkeypatch, tmp_path, [])

    def fail():
        raise RuntimeError("mysql://reader:do-not-show@private-db/catalog")

    monkeypatch.setattr(curation_ui, "_read_records", fail)
    state = curation_ui.entry_knowledge("adapter.vns")
    assert state == {"status": "unavailable", "error_type": "RuntimeError"}
    assert "do-not-show" not in repr(state)
    app = render_status_app()
    panel = maintenance_panel(app)
    assert any("暂不可读" in item.value and "RuntimeError" in item.value for item in panel.caption)
    assert "do-not-show" not in "\n".join(item.value for item in app.caption)
    assert not list(visible_captions(app.main))


def test_source_index_shape_failure_remains_separate_from_catalog(monkeypatch, tmp_path):
    path, _reads = configure_reader(monkeypatch, tmp_path, [])
    path.write_text('{"schema":"old","entries":{}}', encoding="utf-8")
    assert curation_ui.entry_knowledge("adapter.vns") == {"status": "unavailable", "error_type": "ValueError"}


@pytest.mark.parametrize("status", ["current", "missing", "stale"])
def test_real_streamlit_renders_freshness_and_evidence(monkeypatch, tmp_path, record, status):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    records = [] if status == "missing" else [deepcopy(record)]
    if status == "stale":
        records[0]["source_digest"] = "d" * 64
    configure_reader(monkeypatch, tmp_path, records)
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from nsgablack.catalog.curation_ui import render_note, render_status\n"
        "render_status(st, profile='framework-core')\n"
        "render_note(st, entry_key='adapter.vns', profile='framework-core')\n",
        default_timeout=20,
    ).run()
    assert not app.exception, [item.message for item in app.exception]
    panel = maintenance_panel(app)
    text = "\n".join(item.value for item in app.markdown)
    captions = "\n".join(item.value for item in app.caption)
    maintenance = "\n".join(item.value for item in panel.caption)
    assert "AI 缓存 · 当前目录范围 2 项" in maintenance
    assert "不代表源码用法缺失" in maintenance and "也不是组件运行验收" in maintenance
    assert "AI 缓存 · 当前目录范围" not in "\n".join(visible_captions(app.main))
    assert "当前范围剩余" not in captions
    if status == "current":
        assert record["note"]["summary"] in text
        assert "未进行运行验收" in captions
        assert "nsgablack/adapters/vns/adapter.py:10-11" in captions
        assert "example-model" in captions
        assert "可复用 1 · 已过期 0 · 未生成 1 · 校验未通过 0" in maintenance
        codes = "\n".join(item.value for item in app.code)
        assert "adapter.nsga2" in codes and "example.demo" not in codes
    else:
        assert ("可复用 0 · 已过期 0 · 未生成 2 · 校验未通过 0" if status == "missing" else
                "可复用 0 · 已过期 1 · 未生成 1 · 校验未通过 0") in maintenance
        assert record["note"]["summary"] not in text
        assert app.info
        assert ("尚无" if status == "missing" else "已过期") in app.info[0].value


def test_zero_ai_cache_does_not_make_complete_source_guides_look_pending(monkeypatch, tmp_path):
    from nsgablack.catalog.curation_provider import DeepSeekGenerator

    def forbidden(*args, **kwargs):
        raise AssertionError("Reading source coverage must not populate the AI cache")

    for name in ("generate", "review", "_complete"):
        monkeypatch.setattr(DeepSeekGenerator, name, forbidden)
    configure_reader(monkeypatch, tmp_path, [])
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from nsgablack.catalog.examples_ui import render_material_status\n"
        "from nsgablack.catalog.curation_ui import render_status\n"
        "render_material_status(st, snapshot={'available':True, 'material_categories':{"
        "'adapter.vns':'detailed_with_variants', 'adapter.nsga2':'complete_main',"
        "'legacy':'migration_reference'}})\n"
        "render_status(st)\n"
    ).run()
    assert not app.exception
    panel = maintenance_panel(app)
    captions = "\n".join(item.value for item in app.caption)
    assert "详细用法 2" in captions and "迁移说明 1" in captions
    assert "待补资料 0" in captions and "仍缺完整说明" not in captions
    assert any("当前目录范围 3 项：可复用 0 · 已过期 0 · 未生成 3 · 校验未通过 0" in item.value
               for item in panel.caption)
    assert "当前范围剩余" not in captions and "等待按当前源码" not in captions


def test_cache_summary_is_mutually_exclusive_and_scoped_to_the_current_profile(
        monkeypatch, tmp_path, record, deployment_knowledge_verifier):
    keys = ["current", "source_stale", "prompt_stale", "invalid", "missing", "outside"]
    records = []
    for key in keys:
        if key == "missing":
            continue
        item = deepcopy(record)
        item["entry_key"] = key
        if key == "source_stale":
            item["source_digest"] = "d" * 64
            # A stale record is not counted a second time as invalid.
            item["note"]["evidence_ids"] = ["unknown"]
        elif key == "prompt_stale":
            item["prompt_version"] = "old-rule"
        elif key == "invalid":
            item["note"]["evidence_ids"] = ["unknown"]
        records.append(item)
    _, reads = configure_reader(monkeypatch, tmp_path, records,
        entries={key: DIGEST for key in keys}, prompt_version="v1",
        profiles={"default": keys[:-1], "framework-core": ["current", "missing"]})
    app = render_status_app()
    panel = maintenance_panel(app)
    assert any("当前目录范围 5 项：可复用 1 · 已过期 2 · 未生成 1 · 校验未通过 1" in item.value
               for item in panel.caption)
    counts = {"current": 1, "stale": 2, "missing": 1, "invalid": 1}
    deployment_knowledge_verifier.verify_maintenance_panel(app, counts, 5)
    with pytest.raises(AssertionError, match="scoped freshness"):
        deployment_knowledge_verifier.verify_maintenance_panel(app,
            {"current": 2, "stale": 1, "missing": 1, "invalid": 1}, 5)
    panel.proto.expanded = True
    with pytest.raises(AssertionError, match="start collapsed"):
        deployment_knowledge_verifier.verify_maintenance_panel(app, counts, 5)
    panel.proto.expanded = False
    assert not list(visible_captions(app.main))
    assert {key: curation_ui.entry_knowledge(key)["status"] for key in keys} == {
        "current": "current", "source_stale": "stale", "prompt_stale": "stale",
        "invalid": "invalid", "missing": "missing", "outside": "current"}
    narrower = render_status_app("framework-core")
    panel = maintenance_panel(narrower)
    assert any("当前目录范围 2 项：可复用 1 · 已过期 0 · 未生成 1 · 校验未通过 0" in item.value
               for item in panel.caption)
    assert reads == [True]


def test_empty_registered_profile_and_unknown_profile_never_count_the_whole_index(monkeypatch, tmp_path, record):
    configure_reader(monkeypatch, tmp_path, [record], profiles={"empty": []})
    empty = render_status_app("empty")
    panel = maintenance_panel(empty)
    text = "\n".join(item.value for item in panel.caption)
    assert "当前目录范围为空，没有需要统计的 AI 缓存。" in text
    assert "当前目录范围 0 项：可复用 0 · 已过期 0 · 未生成 0 · 校验未通过 0" in text
    unknown = render_status_app("not-registered")
    panel = maintenance_panel(unknown)
    text = "\n".join(item.value for item in panel.caption)
    assert "当前目录范围未在资料索引登记，暂不汇总此范围的 AI 缓存。" in text
    assert "AI 缓存 · 当前目录范围" not in text and "当前目录范围 3 项" not in text


@pytest.fixture
def deployment_knowledge_verifier(monkeypatch):
    directory = Path(__file__).resolve().parents[1] / "deployment/catalog"
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location("deployment_cache_freshness_test", directory / "verify_knowledge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deployment_accepts_empty_cache_and_excludes_old_source_or_prompt(
        deployment_knowledge_verifier, monkeypatch):
    verification = deployment_knowledge_verifier

    def forbidden(*args):
        raise AssertionError("Old cache identities cannot be reviewed as current")

    monkeypatch.setattr(verification, "validate_published_note", forbidden)
    packets = {"adapter.vns": {"source_digest": DIGEST}}
    assert verification.current_published_notes([], packets, prompt_version="current") == []
    records = [
        {"entry_key": "adapter.vns", "source_digest": "b"*64, "prompt_version": "current", "note": {}},
        {"entry_key": "adapter.vns", "source_digest": DIGEST, "prompt_version": "old", "note": {}},
        {"entry_key": "removed", "source_digest": DIGEST, "prompt_version": "current", "note": {}},
    ]
    before = deepcopy(records)
    assert verification.current_published_notes(records, packets, prompt_version="current") == []
    assert records == before


def test_deployment_still_requires_review_for_matching_cached_identity(deployment_knowledge_verifier, monkeypatch):
    from nsgablack.catalog.curation import CurationValidationError

    verification = deployment_knowledge_verifier
    records = [{"entry_key": "adapter.vns", "source_digest": DIGEST,
                "prompt_version": "current", "note": {"unreviewed": True}}]
    packets = {"adapter.vns": {"source_digest": DIGEST}}
    calls = []

    def reject(note, packet):
        calls.append((note, packet))
        raise CurationValidationError("Independent current review is required")

    monkeypatch.setattr(verification, "validate_published_note", reject)
    with pytest.raises(CurationValidationError):
        verification.current_published_notes(records, packets, prompt_version="current")
    assert calls == [(records[0]["note"], packets["adapter.vns"])]


def test_deployment_checks_reader_guard_even_without_cached_records(deployment_knowledge_verifier, monkeypatch):
    from nsgablack.catalog.curation_store import CatalogKnowledgeStore

    store = object.__new__(CatalogKnowledgeStore)
    store.readonly = True

    def forbidden():
        raise AssertionError("Readonly verification cannot connect or write")

    monkeypatch.setattr(store, "_connect", forbidden)
    deployment_knowledge_verifier.verify_reader_write_denied(store)


def test_deployment_rejects_a_store_that_does_not_enforce_readonly(deployment_knowledge_verifier):
    class Writable:
        def put(self, record):
            return record

    with pytest.raises(AssertionError, match="before record validation"):
        deployment_knowledge_verifier.verify_reader_write_denied(Writable())


def test_public_completion_never_overrides_actual_database_freshness(monkeypatch, tmp_path, record):
    from nsgablack.catalog.curation_progress import ENV, SCHEMA, source_identity
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    index_path, _reads = configure_reader(monkeypatch, tmp_path, [record])
    index = json.loads(index_path.read_text())
    progress_path = tmp_path / "public-progress.json"
    progress_path.write_text(json.dumps({"schema": SCHEMA, "source_index_sha256": source_identity(index["entries"]),
                                        "total": 3, "current": 3, "daily_limit": 100, "reserved_today": 100,
                                        "checked_at": "2026-10-23T01:00:00Z", "status": "complete"}))
    monkeypatch.setenv(ENV, str(progress_path))
    app = AppTest.from_string("import streamlit as st\nfrom nsgablack.catalog.curation_ui import render_status\nrender_status(st)\n").run()
    assert not app.exception
    panel = maintenance_panel(app)
    assert any("当前目录范围 3 项：可复用 1 · 已过期 0 · 未生成 2 · 校验未通过 0" in item.value
               for item in panel.caption)
    captions = "\n".join(item.value for item in app.caption)
    assert "对账" in captions and "已全部整理" not in captions


@pytest.mark.parametrize("status", [None, "pending", "paused", "user_paused"])
def test_browsing_and_refresh_preserve_pause_and_do_not_start_ai(monkeypatch, tmp_path, record, status):
    from nsgablack.catalog import curation_provider
    from nsgablack.catalog.curation_progress import ENV, SCHEMA, source_identity
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    def forbidden(*args, **kwargs):
        raise AssertionError("Browsing and refresh must not generate or review AI material")
    monkeypatch.setattr(curation_provider.DeepSeekGenerator, "generate", forbidden)
    monkeypatch.setattr(curation_provider.DeepSeekGenerator, "review", forbidden)
    index_path, _reads = configure_reader(monkeypatch, tmp_path, [record])
    if status is not None:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        progress_path = tmp_path / "public-progress.json"
        progress_path.write_text(json.dumps({
            "schema": SCHEMA, "source_index_sha256": source_identity(index["entries"]),
            "total": 3, "current": 3 if status in {"paused", "user_paused"} else 1,
            "daily_limit": 100, "reserved_today": 100, "next_eligible_at": 2000000000,
            "checked_at": "2026-10-23T01:00:00Z", "status": status,
        }), encoding="utf-8")
        monkeypatch.setenv(ENV, str(progress_path))
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from nsgablack.catalog.curation_ui import render_status, render_note\n"
        "render_status(st)\nrender_note(st, entry_key='adapter.vns')\n",
        default_timeout=20,
    )
    for _ in range(2):
        app.run()
        assert not app.exception, [item.message for item in app.exception]
        captions = "\n".join(item.value for item in app.caption)
        assert "浏览目录或刷新页面不会启动 AI 整理" in captions
        assert all(text not in captions for text in ("后台独立运行", "自动整理已启用", "后续自动检查"))
        if status in {"paused", "user_paused"}:
            assert "已暂停" in captions and "不会自动恢复" in captions
            assert "对账" in captions and "暂停状态不变" in captions
            assert "模型服务暂停" not in captions and "可处理时间" not in captions
        else:
            assert "状态尚未确认" in captions or "状态暂不可用" in captions
        # Source freshness, the existing AI explanation and execution evidence
        # remain separate facts even while the maintenance job is paused.
        assert curation_ui.entry_knowledge("adapter.vns")["status"] == "current"
        assert record["note"]["summary"] in "\n".join(item.value for item in app.markdown)
        assert "nsgablack/adapters/vns/adapter.py:10-11" in captions
        assert "未进行运行验收" in captions
        panel = maintenance_panel(app)
        assert any("当前目录范围 3 项：可复用 1 · 已过期 0 · 未生成 2 · 校验未通过 0" in item.value
                   for item in panel.caption)


def test_related_navigation_uses_existing_callback_without_html_privileges(monkeypatch, tmp_path, record):
    class View:
        def __init__(self):
            self.markdown_calls = []
            self.buttons = []

        def markdown(self, text, **kwargs):
            self.markdown_calls.append((text, kwargs))

        def caption(self, *args):
            pass

        def expander(self, *args, **kwargs):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def code(self, *args, **kwargs):
            pass

        def button(self, label, **kwargs):
            self.buttons.append((label, kwargs))

    record["note"]["summary"] = "<script>bad()</script>"
    record["note"]["related_keys"] = ["adapter.nsga2", "adapter.nsga2", "example.demo"]
    configure_reader(monkeypatch, tmp_path, [record])
    callback = lambda **kwargs: None
    view = View()
    curation_ui.render_note(view, entry_key="adapter.vns", profile="framework-core",
                            on_navigate=callback, navigation_kwargs={"scope": "framework"})
    assert len(view.buttons) == 1
    label, options = view.buttons[0]
    assert label == "adapter.nsga2" and options["on_click"] is callback
    assert options["kwargs"] == {"scope": "framework", "target_key": "adapter.nsga2"}
    generated_call = next(call for call in view.markdown_calls if call[0] == record["note"]["summary"])
    assert generated_call[1]["unsafe_allow_html"] is False


def test_actual_dashboard_interface_preserves_legacy_generated_note(monkeypatch, tmp_path, record):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    configure_reader(monkeypatch, tmp_path, [record])
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "catalog/dashboard.py"), default_timeout=40)
    app.query_params.update({"profile": "framework-core", "kind": "all", "query": "adapter.vns",
                             "selected": "adapter.vns", "detail_tab": "interface"})
    app.run()
    assert not app.exception, [item.message for item in app.exception]
    assert any(item.value == record["note"]["summary"] for item in app.markdown)
    assert app.session_state["catalog_ui_selected"] == "adapter.vns"
    assert any("未进行运行验收" in item.value for item in app.caption)
