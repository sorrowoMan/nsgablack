"""Deployment acceptance preserves migration boundaries without executing tutorials."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def verifier(monkeypatch):
    root = Path(__file__).resolve().parents[1] / "deployment/catalog"
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module
    load("runtime", root / "runtime.py")
    return load("catalog_example_deployment_test", root / "verify_examples.py")


MAIN = "\n\n".join("**" + key + ":** " + value for key, value in (
    ("什么时候用", "检查明确的旧实现。"), ("先准备什么", "完整Project和明确输入。"),
    ("放在哪", "Case工厂与原正式入口。"), ("接入步骤", "核对现有接线并选择替代。"),
    ("怎样判断接对", "检查真实返回字段，不伪造运行。"), ("运行入口", "原Project运行入口。")))


def index_for(text=MAIN, *, migration=True):
    record = {"id": "current", "kind": "documentation", "binding": "focused",
        "component_keys": ["bias.legacy"], "run_command": "", "source_digest": "a" * 64,
        "verification": {"status": "source_checked"}, "snippets": [{
            "path": "nsgablack/docs/current.md", "text": text, "start_line": 1,
            "end_line": len(text.splitlines()), "complete": True,
            "sha256": hashlib.sha256(text.encode()).hexdigest(), "file_sha256": "b" * 64}]}
    if migration:
        record["usage_status"] = "migration_reference"
    return {"entries": {"bias.legacy": ["current"]}, "examples": {"current": record}, "issues": []}


def test_inventory_accepts_complete_prose_migration_without_invented_python(verifier):
    result = verifier._verify_material_inventory(index_for(), ("bias.legacy",), source_roots={})
    assert result["categories"] == {"migration_reference": 1}
    assert result["migration_keys"] == ["bias.legacy"]
    assert result["component_execution"] is result["ai_review"] is False


@pytest.mark.parametrize("damage", ["placeholder", "incomplete", "executed", "command", "missing_key"])
def test_inventory_does_not_complete_or_promote_invalid_migration(verifier, damage):
    index = index_for()
    item = index["examples"]["current"]
    keys = ("bias.legacy",)
    if damage == "placeholder":
        item["snippets"][0]["text"] = MAIN.replace("完整Project和明确输入。", "输入待补充。")
    elif damage == "incomplete":
        item["snippets"][0]["complete"] = False
    elif damage == "executed":
        item["verification"]["status"] = "executed"
    elif damage == "command":
        item["run_command"] = "python old.py"
    else:
        keys += ("absent",)
    with pytest.raises(verifier.VerificationError):
        verifier._verify_material_inventory(index, keys, source_roots={})


def test_inventory_retains_known_api_failure_and_does_not_execute_code(verifier, monkeypatch, tmp_path):
    destination = tmp_path / "must-not-exist"
    index = index_for(MAIN + "\n\n```python\n" +
        f"open({str(destination)!r}, 'w').write('never')\n```", migration=False)
    calls = []
    def inspect(code, *, source_roots):
        calls.append(code)
        return {"issues": [{"code": "known-api-invalid"}], "unknown_calls": []}
    monkeypatch.setattr("nsgablack.catalog.usage_api_validation.inspect_usage_api", inspect)
    with pytest.raises(verifier.VerificationError, match="known API"):
        verifier._verify_material_inventory(index, ("bias.legacy",), source_roots={})
    assert calls and not destination.exists()


def test_migration_page_verifies_selected_guide_and_rejects_ai_replacement(verifier, monkeypatch):
    index = index_for()
    old = {**index["examples"]["current"], "id": "old", "usage_status": None,
        "snippets": [{**index["examples"]["current"]["snippets"][0],
                      "text": MAIN + "\n\n```python\nvalue = 7\n```"}]}
    index["examples"]["old"] = old
    index["entries"]["bias.legacy"].insert(0, "old")
    caption = SimpleNamespace(value="用法 · 源码已核对，未记录运行结果。")
    prose = MAIN + "\n输入与准备 接下来怎么接 预期得到什么 运行入口\n" + (
        "**迁移说明** · 替代示例不表示原组件已经实现或可直接装配。")
    app = SimpleNamespace(markdown=[SimpleNamespace(value=prose)], code=[], caption=[caption],
        main=SimpleNamespace(children={0: SimpleNamespace(type="markdown", value=prose)}))
    monkeypatch.setattr(verifier, "_open_app", lambda *a: app)
    monkeypatch.setattr("nsgablack.catalog.examples_ui.example_status", lambda *a: "迁移说明")
    entry = SimpleNamespace(key="bias.legacy", as_dict=lambda: {"key": "bias.legacy"})
    result = verifier._verify_usage_app(None, None, index, entry, "default")
    assert result["example_id"] == "current" and result["status"] == "migration_reference"
    def attempt_ai(*unused):
        from nsgablack.catalog.curation_ui import render_tutorial
        render_tutorial(None, entry_key="bias.legacy")
        return app
    monkeypatch.setattr(verifier, "_open_app", attempt_ai)
    with pytest.raises(verifier.VerificationError, match="AI tutorial"):
        verifier._verify_usage_app(None, None, index, entry, "default")


def test_usage_code_hidden_in_evidence_does_not_pass_main_assembly_acceptance(verifier, monkeypatch):
    block = "def actually_assemble(value):\n    return value ** 2\n"
    index = index_for(MAIN + "\n\n```python\n" + block + "```", migration=False)
    prose = MAIN + "\n输入与准备 接下来怎么接 预期得到什么 运行入口"
    app = SimpleNamespace(markdown=[SimpleNamespace(value=prose)],
        code=[SimpleNamespace(value=block.rstrip("\n"))], caption=[],
        main=SimpleNamespace(children={0: SimpleNamespace(type="markdown", value=prose),
            1: SimpleNamespace(type="expander", children={
                0: SimpleNamespace(type="code", value=block.rstrip("\n"))})}))
    monkeypatch.setattr(verifier, "_open_app", lambda *a: app)
    monkeypatch.setattr("nsgablack.catalog.examples_ui.example_status", lambda *a: "详细用法")
    entry = SimpleNamespace(key="bias.legacy", as_dict=lambda: {"key": "bias.legacy"})
    with pytest.raises(verifier.VerificationError, match="hidden in collapsed"):
        verifier._verify_usage_app(None, None, index, entry, "default")


def test_source_coverage_caption_keeps_migration_and_navigation_separate(verifier):
    categories = {"a": "detailed_with_variants", "b": "complete_main", "c": "migration_reference",
                  "d": "documentation_navigation", "e": "project_case_navigation"}
    app = SimpleNamespace(caption=[SimpleNamespace(value=(
        "用法资料 · 全部索引 5 项：详细用法 2 · 迁移说明 1 · 导航 2 · 待补资料 0\n"
        "源码说明、AI 审核和实际运行分别统计。"))])
    verifier._verify_material_caption(app, categories)
    app.caption[0].value = "AI 资料整理：5 / 5"
    with pytest.raises(verifier.VerificationError, match="conflated"):
        verifier._verify_material_caption(app, categories)


def test_material_acceptance_counts_unrecognized_categories_as_pending(verifier):
    categories = {"unknown": "future_category"}
    app = SimpleNamespace(caption=[SimpleNamespace(value=(
        "用法资料 · 全部索引 1 项：详细用法 0 · 迁移说明 0 · 导航 0 · 待补资料 1\n"
        "源码说明、AI 审核和实际运行分别统计。"))])
    verifier._verify_material_caption(app, categories)
    app.caption[0].value = app.caption[0].value.replace("待补资料 1", "待补资料 0")
    with pytest.raises(verifier.VerificationError, match="conflated"):
        verifier._verify_material_caption(app, categories)


@pytest.mark.parametrize("damage", ["pending_count", "legacy_claim", "migration_count"])
def test_source_material_acceptance_rejects_wrong_or_misleading_counts(verifier, damage):
    categories = {"a": "detailed_with_variants", "b": "migration_reference",
        "c": "documentation_navigation", "d": "source_fragment", "e": "missing_source"}
    caption = ("用法资料 · 全部索引 5 项：详细用法 1 · 迁移说明 1 · 导航 1 · 待补资料 2\n"
               "源码说明、AI 审核和实际运行分别统计。")
    app = SimpleNamespace(caption=[SimpleNamespace(value=caption)])
    verifier._verify_material_caption(app, categories)
    if damage == "pending_count":
        app.caption[0].value = caption.replace("待补资料 2", "待补资料 0")
    elif damage == "migration_count":
        app.caption[0].value = caption.replace("迁移说明 1", "迁移说明 0")
    else:
        app.caption[0].value = caption + "\n仍缺完整说明 0 项。"
    with pytest.raises(verifier.VerificationError, match="conflated"):
        verifier._verify_material_caption(app, categories)


def _publication_file(path, content=b"unchanged public source\n"):
    image = "/opt/src/" + path if path.startswith(("nsgablack/", "blackbase/", "mlblack/")) else "/opt/catalog/" + path
    return {"path": path, "image_path": image, "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content)}


def _seal_publication(manifest):
    files = manifest["files"]
    manifest.update(content_sha256=hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        source_file_count=len(files), source_bytes=sum(row["bytes"] for row in files))
    return manifest


def _status_publications():
    base = _seal_publication({"schema": "nsgablack.catalog_deployment_context/v1", "files": [
        _publication_file("nsgablack/adapters/nsga2/adapter.py"),
        _publication_file("nsgablack/core/state/solution_pool.py"),
        _publication_file("mlblack/core/model.py"),
        _publication_file("blackbase/src/blackbase/runtime.py"),
        _publication_file("nsgablack/catalog/examples_ui.py"),
        _publication_file("nsgablack/catalog/curation_ui.py"),
        _publication_file("verify_examples.py"),
        _publication_file("verify_knowledge.py"),
        _publication_file("runtime.py"),
    ]})
    current = deepcopy(base)
    for row in current["files"]:
        if row["path"] in {"nsgablack/catalog/examples_ui.py", "nsgablack/catalog/curation_ui.py",
                           "verify_examples.py", "verify_knowledge.py"}:
            row.update(_publication_file(row["path"], b"presentation-only update\n"))
    for path in ("verify_material_status.py", "status-overlay.Dockerfile", "status-overlay.json",
                 "status-base-manifest.json"):
        current["files"].append(_publication_file(path, b"new presentation-only metadata\n"))
    _seal_publication(current)
    preserved = hashlib.sha256(b"fixed source and independent example receipts").hexdigest()
    current["derivation"] = {"schema": "nsgablack.catalog_status_overlay/v1",
                             "base_content_sha256": base["content_sha256"],
                             "preserved_artifacts": {"examples.json": preserved}}
    return current, base, preserved


def test_plain_publication_uses_its_own_digest_even_when_a_base_is_supplied(verifier):
    current, base, preserved = _status_publications()
    current.pop("derivation")
    original = deepcopy(current)
    assert verifier._example_publication_digest(current) == current["content_sha256"]
    assert verifier._example_publication_digest(current, base, preserved, preserved) == current["content_sha256"]
    assert current == original and current["content_sha256"] != base["content_sha256"]


def test_status_only_publication_reuses_exactly_preserved_base_evidence(verifier):
    current, base, preserved = _status_publications()
    originals = deepcopy((current, base))
    assert verifier._example_publication_digest(current, base, preserved, preserved) == base["content_sha256"]
    assert (current, base) == originals


@pytest.mark.parametrize("path", [
    "nsgablack/catalog/examples_ui.py", "nsgablack/catalog/curation_ui.py",
    "verify_examples.py", "verify_knowledge.py", "verify_material_status.py",
    "status-overlay.Dockerfile", "status-overlay.json", "status-base-manifest.json",
])
def test_each_documented_status_overlay_file_is_permitted(verifier, path):
    current, base, preserved = _status_publications()
    current["files"] = deepcopy(base["files"])
    replacement = _publication_file(path, b"a presentation-only change\n")
    if any(row["path"] == path for row in current["files"]):
        current["files"] = [replacement if row["path"] == path else row for row in current["files"]]
    else:
        current["files"].append(replacement)
    _seal_publication(current)
    assert verifier._example_publication_digest(current, base, preserved, preserved) == base["content_sha256"]


@pytest.mark.parametrize("path", [
    "nsgablack/adapters/nsga2/adapter.py", "nsgablack/core/state/solution_pool.py",
    "mlblack/core/model.py", "blackbase/src/blackbase/runtime.py", "runtime.py",
    "nsgablack/catalog/new_behavior.py", "unregistered-overlay-metadata.json",
])
def test_validly_hashed_runtime_changes_or_unknown_additions_cannot_reuse_receipts(verifier, path):
    current, base, preserved = _status_publications()
    replacement = _publication_file(path, b"unapproved change\n")
    current["files"] = [replacement if row["path"] == path else row for row in current["files"]]
    if not any(row["path"] == path for row in current["files"]):
        current["files"].append(replacement)
    _seal_publication(current)  # This is a valid new manifest, not a broken digest fixture.
    with pytest.raises(verifier.VerificationError):
        verifier._example_publication_digest(current, base, preserved, preserved)


@pytest.mark.parametrize("path", ["nsgablack/adapters/nsga2/adapter.py", "nsgablack/catalog/examples_ui.py"])
def test_overlay_cannot_delete_any_base_file_even_from_the_ui_allowlist(verifier, path):
    current, base, preserved = _status_publications()
    current["files"] = [row for row in current["files"] if row["path"] != path]
    _seal_publication(current)
    with pytest.raises(verifier.VerificationError):
        verifier._example_publication_digest(current, base, preserved, preserved)


@pytest.mark.parametrize("side", ["current", "base"])
@pytest.mark.parametrize("damage", [
    "schema", "missing_files", "empty_files", "bad_record", "bad_path", "absolute_path", "parent_path",
    "backslash_path", "duplicate_path", "missing_image_path", "relative_image_path", "private_image_path",
    "parent_image_path", "backslash_image_path", "invalid_sha", "negative_bytes", "boolean_bytes",
    "content_digest", "file_count", "total_bytes", "boolean_count", "boolean_total_bytes",
])
def test_both_manifests_need_complete_valid_file_identities(verifier, side, damage):
    current, base, preserved = _status_publications()
    target = current if side == "current" else base
    if damage == "schema":
        target["schema"] = "untrusted.schema/v1"
    elif damage == "missing_files":
        target.pop("files")
    elif damage == "empty_files":
        target["files"] = []
        _seal_publication(target)
    elif damage == "bad_record":
        target["files"][0] = "not a source file"
    elif damage in {"content_digest", "file_count", "total_bytes", "boolean_count", "boolean_total_bytes"}:
        if damage == "content_digest":
            target["content_sha256"] = "0" * 64
        elif damage == "file_count":
            target["source_file_count"] += 1
        elif damage == "total_bytes":
            target["source_bytes"] += 1
        else:
            # bool must not be accepted merely because it compares equal to 1.
            target["files"] = [_publication_file("runtime.py", b"x")]
            _seal_publication(target)
            target["source_file_count" if damage == "boolean_count" else "source_bytes"] = True
    else:
        row = target["files"][0]
        if damage == "bad_path":
            row["path"] = ""
        elif damage == "absolute_path":
            row["path"] = "/opt/private/source.py"
        elif damage == "parent_path":
            row["path"] = "nsgablack/../private.py"
        elif damage == "backslash_path":
            row["path"] = "nsgablack\\private.py"
        elif damage == "duplicate_path":
            target["files"].append(deepcopy(row))
        elif damage == "missing_image_path":
            row.pop("image_path")
        elif damage == "relative_image_path":
            row["image_path"] = "relative/source.py"
        elif damage == "private_image_path":
            row["image_path"] = "/opt/private/source.py"
        elif damage == "parent_image_path":
            row["image_path"] = "/opt/src/nsgablack/../private.py"
        elif damage == "backslash_image_path":
            row["image_path"] = "/opt/src/nsgablack\\private.py"
        elif damage == "invalid_sha":
            row["sha256"] = "not-a-sha256"
        elif damage == "negative_bytes":
            row["bytes"] = -1
        elif damage == "boolean_bytes":
            row["bytes"] = True
        _seal_publication(target)
    with pytest.raises(verifier.VerificationError):
        verifier._example_publication_digest(current, base, preserved, preserved)


@pytest.mark.parametrize("damage", [
    "missing_base", "wrong_base_digest", "unsupported_schema", "derivation_list",
    "preserved_artifacts_list", "missing_artifact", "invalid_artifact_digest", "preserved_parameter",
    "actual_artifact", "missing_preserved_parameter", "missing_actual_artifact",
])
def test_overlay_requires_its_exact_base_and_unchanged_published_index(verifier, damage):
    current, base, preserved = _status_publications()
    supplied, actual = preserved, preserved
    if damage == "missing_base":
        base = None
    elif damage == "wrong_base_digest":
        current["derivation"]["base_content_sha256"] = "0" * 64
    elif damage == "unsupported_schema":
        current["derivation"]["schema"] = "nsgablack.catalog_status_overlay/v2"
    elif damage == "derivation_list":
        current["derivation"] = []
    elif damage == "preserved_artifacts_list":
        current["derivation"]["preserved_artifacts"] = []
    elif damage == "missing_artifact":
        current["derivation"]["preserved_artifacts"] = {}
    elif damage == "invalid_artifact_digest":
        current["derivation"]["preserved_artifacts"]["examples.json"] = "invalid"
    elif damage == "preserved_parameter":
        supplied = "0" * 64
    elif damage == "actual_artifact":
        actual = "0" * 64
    elif damage == "missing_preserved_parameter":
        supplied = None
    elif damage == "missing_actual_artifact":
        actual = None
    with pytest.raises(verifier.VerificationError):
        verifier._example_publication_digest(current, base, supplied, actual)


@pytest.fixture
def executed_markdown_first_project(tmp_path, monkeypatch, verifier):
    """Run one fixed, source-only CPU Project; browsing must never rerun it."""
    pytest.importorskip("streamlit.testing.v1")
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    from nsgablack.catalog import dashboard, examples, examples_ui, registry

    root = Path(__file__).resolve().parents[1]
    roots = {name: root.parent / name for name in ("nsgablack", "mlblack", "blackbase")}
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    monkeypatch.setenv("NSGABLACK_CATALOG_KNOWLEDGE_ENABLED", "0")
    index = {"schema": examples.SCHEMA, "publication_digest": "d" * 64,
             "entries": {"adapter.fixed_candidate": []}, "examples": {}, "issues": []}
    for name in ("fixed_candidate", "nsgablack_usage"):
        manifest = tomllib.loads((root / "catalog/example_manifests" / f"{name}.toml").read_text(encoding="utf-8-sig"))
        for spec in manifest["example"]:
            if spec["component_keys"] != ["adapter.fixed_candidate"]:
                continue
            record = examples._base_record(spec, roots, index["publication_digest"])
            index["examples"][record["id"]] = record
            index["entries"]["adapter.fixed_candidate"].append(record["id"])
    assert len(index["examples"]) == 2
    examples.validate_example_index(index)
    module_spec = importlib.util.spec_from_file_location("fixed_project_receipt_test", root / "deployment/catalog/run_example_receipts.py")
    runner = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(runner)
    receipts = runner.run_preset("fixed-candidate", roots, index, timeout=60)
    assert len(receipts) == 1 and receipts[0]["exit_code"] == 0
    assert any("independently checked raw objective=0.625" in line for line in receipts[0]["observed_outputs"])
    project = index["examples"]["fixed-candidate-project"]
    project["verification"] = examples._receipt(project, receipts)
    assert project["verification"]["status"] == "executed"
    examples.validate_example_index(index)
    path = tmp_path / "fixed-project-index.json"
    path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv(examples_ui.INDEX_ENV, str(path))
    examples_ui._load_snapshot.cache_clear()
    for name in ("_cached_summary", "_cached_schema", "_cached_source_info", "_cached_items", "_cached_facets",
                 "_cached_selected", "_cached_neighbors", "_cached_other_kind_hits"):
        getattr(dashboard, name).cache_clear()

    def forbidden(*args, **kwargs):
        raise AssertionError("Reading a receipt must not call a model, build a Unit or rerun its Solver")

    from nsgablack.catalog.curation_provider import DeepSeekGenerator
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.units import UnitBinding
    monkeypatch.setattr(DeepSeekGenerator, "_complete", forbidden)
    monkeypatch.setattr(UnitBinding, "build", forbidden)
    monkeypatch.setattr(SolverBase, "run", forbidden)
    return index, dashboard, registry


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_deployment_verifier_accepts_actual_markdown_first_project_receipt(
        verifier, executed_markdown_first_project, monkeypatch, profile):
    """Exercise the production receipt assertions against actual Streamlit UI.

    Only the deployment-owned MySQL precondition is isolated: this local test
    opens the real registry-backed page. No rendered element is a fake View.
    """
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from nsgablack.catalog import examples_ui
    from nsgablack.catalog.usage_learning import snippet_parts

    index, dashboard, registry = executed_markdown_first_project
    opened = []

    def open_local_registry(app_test, module, key, current_profile):
        app = app_test.from_file(module.__file__, default_timeout=90)
        app.query_params.update({"profile": current_profile, "scope": "framework", "kind": "all", "query": key,
                                 "selected": key, "detail_tab": "overview"})
        app.run()
        assert not app.exception
        assert app.session_state["catalog_ui_source_mode"] == "off"
        assert app.session_state["catalog_ui_selected"] == key
        assert app.session_state["catalog_ui_profile"] == current_profile
        assert tuple(app.session_state["catalog_ui_result_keys"]).count(key) == 1
        snapshot = examples_ui.examples_snapshot()
        assert snapshot["available"]
        verifier._verify_material_caption(app, snapshot["material_categories"])
        opened.append(app)
        return app

    monkeypatch.setattr(verifier, "_open_app", open_local_registry)
    entry = registry.get_source_catalog(profile=profile, refresh=True).get("adapter.fixed_candidate")
    result = verifier._verify_app(AppTest, dashboard, index, entry, profile)
    assert result["status"] == "executed" and result["teaching"]["example_id"] == "usage-adapter-fixed_candidate"
    app = opened[0]
    project = index["examples"]["fixed-candidate-project"]
    readme = project["snippets"][0]
    assert readme["path"].endswith("/README.md")
    assert readme["text"] not in [item.value for item in app.code]
    source_blocks = [value for snippet in project["snippets"] for kind, value, _ in snippet_parts(snippet)
                     if kind == "code" and value.strip()]
    assert len(source_blocks) >= 8
    evidence = next(item for item in app.expander if item.label.startswith("完整 Project 与运行记录"))
    assert not evidence.proto.expanded
    assert all(block in [item.value for item in evidence.code] for block in source_blocks)
    assert "\n".join(project["verification"]["observed_outputs"]) in [item.value for item in evidence.code]
    # Damage a later native block in the actual widget tree, including its
    # duplicate in source evidence. The first README command alone cannot pass.
    observed_example = next(value for kind, value, language in snippet_parts(readme)
                            if kind == "code" and language == "text")
    removed = 0
    for item in app.code:
        if item.value == observed_example:
            item.proto.code_text = ""
            removed += 1
    assert removed >= 1
    monkeypatch.setattr(verifier, "_open_app", lambda *args: app)
    with pytest.raises(verifier.VerificationError, match="actual usage code"):
        verifier._verify_app(AppTest, dashboard, index, entry, profile)
