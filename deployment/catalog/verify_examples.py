#!/usr/bin/env python3
"""Read-only example acceptance against the published source and MySQL dashboard.

Run inside the web reader container after the independent example runner has
published its source-bound receipts. This script never executes example commands.
"""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
import re
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from runtime import configure_reader


MANIFEST = Path("/opt/catalog/release-manifest.json")
_STATUS_OVERLAY_PATHS = frozenset({
    "nsgablack/catalog/examples_ui.py", "nsgablack/catalog/curation_ui.py",
    "verify_examples.py", "verify_knowledge.py", "verify_material_status.py",
    "status-overlay.Dockerfile", "status-overlay.json", "status-base-manifest.json",
})


def _example_publication_digest(manifest, base_manifest=None,
                                preserved_index_sha256=None, actual_index_sha256=None):
    """Keep old receipts bound to their original, unchanged source publication.

    A presentation-only derived reader can display those artifacts without
    claiming new algorithm execution. Every runtime/source record must remain
    byte-identical; the normal source-file and receipt checks still apply.
    """
    def checked(value):
        require(isinstance(value, dict) and value.get("schema") == "nsgablack.catalog_deployment_context/v1",
                "Invalid source publication manifest")
        files = value.get("files")
        require(isinstance(files, list) and bool(files), "Missing source publication whitelist")
        rows = {}
        for row in files:
            require(isinstance(row, dict), "Invalid source publication file")
            name, size, digest = row.get("path"), row.get("bytes"), row.get("sha256")
            require(isinstance(name, str) and bool(name) and "\\" not in name and name not in rows
                    and not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts,
                    "Unsafe source publication path")
            require(type(size) is int and size >= 0 and isinstance(digest, str)
                    and re.fullmatch(r"[0-9a-f]{64}", digest), "Invalid source publication file identity")
            image = row.get("image_path")
            require(isinstance(image, str) and "\\" not in image and PurePosixPath(image).is_absolute()
                    and ".." not in PurePosixPath(image).parts and any(
                        PurePosixPath(image).is_relative_to(root) for root in (
                            PurePosixPath("/opt/src/nsgablack"), PurePosixPath("/opt/src/blackbase"),
                            PurePosixPath("/opt/src/mlblack"), PurePosixPath("/opt/catalog"))),
                    "Unsafe source publication image path")
            rows[name] = row
        digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        require(value.get("content_sha256") == digest and type(value.get("source_file_count")) is int
                and type(value.get("source_bytes")) is int and value.get("source_file_count") == len(rows)
                and value.get("source_bytes") == sum(row["bytes"] for row in rows.values()),
                "Source publication whitelist identity mismatch")
        return rows, digest

    current, digest = checked(manifest)
    derivation = manifest.get("derivation")
    if derivation is None:
        return digest
    require(isinstance(derivation, dict)
            and derivation.get("schema") == "nsgablack.catalog_status_overlay/v1",
            "Unsupported derived source publication")
    base, base_digest = checked(base_manifest)
    require(base_digest == derivation.get("base_content_sha256"), "Derived publication base mismatch")
    require(set(base) <= set(current), "Presentation overlay removed source files")
    changed = {name for name in current if current[name] != base.get(name)}
    require(changed <= _STATUS_OVERLAY_PATHS, "Presentation overlay changed runtime or unknown source files")
    artifacts = derivation.get("preserved_artifacts")
    require(isinstance(artifacts, dict), "Missing preserved artifact identities")
    expected = artifacts.get("examples.json")
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected)
            and preserved_index_sha256 == actual_index_sha256 == expected,
            "Presentation overlay changed its published example index")
    return base_digest


SOURCE_ROOTS = {name: Path("/opt/src") / name for name in ("nsgablack", "blackbase", "mlblack")}
FOCUSED_KEYS = ("adapter.nsga2", "adapter.vns", "adapter.moead", "adapter.fixed_candidate", "tool.solution_pool",
                "mlblack.codec.linear_point")
USAGE_KEYS = ("adapter.astar", "bias.surrogate_control", "mlblack.backend.numpy",
              "mlblack.problem.supervised_classification", "tool.runtime_participant",
              "tool.population_change", "mlblack.integration.nsgablack_learning_case_evaluator")
MIGRATION_KEYS = ("bias.surrogate_control", "plugin.dynamic_switch", "mlblack.problem.training_proxy")
LEARNING_KEYS = (
    "adapter.composite", "adapter.fixed_candidate", "adapter.moead", "adapter.nsga2", "adapter.vns",
    "adapter.bayesian_optimization", "bias.callable", "bias.risk", "tool.unit_binding",
    "tool.population_unit", "repr.gaussian_mutation", "repr.context_gaussian", "plugin.pareto_archive", "repr.pipeline",
    "plugin.monte_carlo_eval",
    "tool.solution_pool", "mlblack.integration.learning_solver", "mlblack.trainer.learning_solver",
    "mlblack.data_view.numeric", "mlblack.codec.linear_point", "mlblack.representation.linear_point",
    "tool.pool", "tool.subpools", "tool.pool_task_spec", "adapter.search_plan", "adapter.serial_strategy", "adapter.multi_strategy",
    "mlblack.head.point", "mlblack.head.binary_logistic", "mlblack.head.softmax", "mlblack.head.probability_calibration",
    "mlblack.head.two_model_interval", "mlblack.head.interval", "mlblack.head.center_radius_interval",
    "adapter.nsga3", "adapter.spea2", "adapter.de", "adapter.cmaes", "adapter.map_elites",
    "adapter.sa", "adapter.gaussian_search", "adapter.gradient_optimizer", "adapter.pattern_search",
    "adapter.trust_region_dfo", "adapter.astar", "adapter.moa_star",
    "tool.unit_view", "bias.population_diversity", "bias.unit_preference", "bias.module",
    "bias.tabu", "bias.dynamic_penalty", "plugin.checkpoint_resume", "plugin.module_report",
    "plugin.profiler", "plugin.decision_trace", "plugin.surrogate_eval", "plugin.multi_fidelity_eval",
    "plugin.newton_solver", "plugin.broyden_solver",
    "mlblack.core.artifact_bundle",
)
LEARNING_FIELDS = ("放在哪", "先准备什么", "接入步骤", "怎样判断接对")
COMPLETE_FIELDS = ("什么时候用", *LEARNING_FIELDS, "运行入口")


class VerificationError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def _native_code(text):
    """Streamlit's native code widget removes one outer newline, not spaces.

    Preserve every interior line and indentation when checking source fidelity.
    Markdown-first examples can legitimately quote a module with a blank first
    line; that line is omitted by CodeMixin.code before the widget is rendered.
    """
    return text.removeprefix("\n").removesuffix("\n")


def _verify_source_files(index, whitelist, roots):
    """Check every indexed source and excerpt against fixed whitelisted roots."""
    checked, references = {}, 0
    for example in index["examples"].values():
        for name, expected in example["source_files"].items():
            relative = PurePosixPath(name)
            parts = relative.parts
            require(len(parts) >= 2 and parts[0] in roots and not relative.is_absolute()
                    and ".." not in parts and "\\" not in name and ":" not in name,
                    "Example source has an unsafe framework-relative identity")
            root = roots[parts[0]].resolve()
            target = root
            for part in parts[1:]:
                target /= part
                require(not target.is_symlink() and not bool(getattr(target, "is_junction", lambda: False)()),
                        "Example source must not traverse links")
            target = target.resolve()
            require(target.is_relative_to(root) and target.is_file(), "Example source is outside published roots")
            require(name in whitelist and whitelist[name]["resolved"] == target,
                    "Example source is absent from the release whitelist")
            if name not in checked:
                require(target.stat().st_size <= 2 * 1024 * 1024, "Example source exceeds its size bound")
                data = target.read_bytes()
                checked[name] = {"sha256": hashlib.sha256(data).hexdigest(),
                                 "text": data.decode("utf-8-sig")}
            require(checked[name]["sha256"] == expected == whitelist[name]["sha256"],
                    "Example source differs from its published file checksum")
            references += 1
        for snippet in example["snippets"]:
            lines = checked[snippet["path"]]["text"].splitlines()
            selected = "\n".join(lines[snippet["start_line"] - 1:snippet["end_line"]])
            require(selected == snippet["text"], "Example excerpt differs from its published source lines")
    return {"unique_files": len(checked), "source_references": references}


def _verify_material_inventory(index, entry_keys, *, source_roots=SOURCE_ROOTS):
    """Keep complete teaching, migrations and navigation as separate facts."""
    from nsgablack.catalog.material_plan import build_material_plan
    from nsgablack.catalog.usage_api_validation import inspect_usage_api
    from nsgablack.catalog.usage_learning import documentation_fields, snippet_parts

    keys = set(entry_keys)
    require(keys <= set(index["entries"]), "Published Catalog key is absent from the source material index")
    require(not index.get("issues"), "Published source material has unresolved index issues")
    plan = build_material_plan(index)
    rows = [item for item in plan["entries"] if item["key"] in keys]
    categories = Counter(row["category"] for row in rows)
    require(not categories["source_fragment"] and not categories["missing_source"],
            "Published Catalog still has incomplete source material")
    migrations, checked, unknown_calls = [], set(), 0
    for row in rows:
        require(not any(field["placeholder_values"] for field in row["fields"].values()),
                "Published source material still has placeholder instructions")
        if row["category"] in {"documentation_navigation", "project_case_navigation"}:
            continue
        guide = index["examples"][row["primary_example_id"]]
        fields = documentation_fields(guide["snippets"])
        require(all(fields.get(name) for name in COMPLETE_FIELDS),
                "Published component guide has incomplete assembly instructions")
        if row["category"] == "migration_reference":
            require(guide.get("usage_status") == "migration_reference"
                    and guide["kind"] == "documentation" and not guide.get("run_command")
                    and guide["verification"]["status"] == "source_checked",
                    "Migration material was promoted to executable or verified implementation")
            migrations.append(row["key"])
        if guide["id"] in checked:
            continue
        checked.add(guide["id"])
        code = "\n\n".join(text for snippet in guide["snippets"]
                            for kind, text, language in snippet_parts(snippet)
                            if kind == "code" and language == "python")
        if code:
            analysis = inspect_usage_api(code, source_roots=source_roots)
            require(not analysis["issues"], "Published guide calls a known API with an invalid interface")
            unknown_calls += len(analysis["unknown_calls"])
    return {"components": len(rows), "categories": dict(categories),
            "migration_keys": sorted(migrations), "checked_guides": len(checked),
            "unknown_api_calls": unknown_calls, "component_execution": False, "ai_review": False}


def _open_app(AppTest, dashboard, key, profile):
    app = AppTest.from_file(dashboard.__file__, default_timeout=90)
    app.query_params.update({"profile": profile, "scope": "framework", "kind": "all", "query": key,
                             "selected": key, "detail_tab": "overview"})
    app.run()
    require(not app.exception, "Dashboard raised while displaying a component example")
    require(app.session_state["catalog_ui_source_mode"] == "only",
            "Example page did not retain its deployment-owned MySQL source")
    require(app.session_state["catalog_ui_selected"] == key, "Example page lost the selected component")
    require(app.session_state["catalog_ui_profile"] == profile, "Example page lost its requested Catalog profile")
    keys = tuple(app.session_state["catalog_ui_result_keys"])
    lists = [item for item in app.radio if str(item.key).startswith("catalog_ui::component_list::")]
    require(len(lists) == 1 and len(lists[0].options) == len(keys), "Example search has no selectable component list")
    require(keys.count(key) == 1, "Example search did not preserve the component identity")
    from nsgablack.catalog.examples_ui import examples_snapshot
    material = examples_snapshot()
    require(material.get("available"), "Example page lost its fixed source material index")
    _verify_material_caption(app, material["material_categories"])
    return app


def _verify_material_caption(app, categories):
    counts = Counter(categories.values())
    complete = counts["detailed_with_variants"] + counts["complete_main"]
    navigation = counts["documentation_navigation"] + counts["project_case_navigation"]
    pending = len(categories) - complete - counts["migration_reference"] - navigation
    captions = "\n".join(item.value for item in app.caption)
    require(f"全部索引 {len(categories)} 项" in captions
            and f"详细用法 {complete} · 迁移说明 {counts['migration_reference']} · 导航 {navigation}" in captions
            and f"· 待补资料 {pending}" in captions
            and "仍缺完整说明" not in captions
            and "源码说明、AI 审核和实际运行分别统计" in captions,
            "Example page conflated source coverage, migration, AI review or execution")


def _visible_nodes(block):
    """Inspect the main page in display order, leaving expander evidence separate."""
    for node in block.children.values():
        if node.type == "expander":
            continue
        if hasattr(node, "children"):
            yield from _visible_nodes(node)
        else:
            yield node


def _verify_learning_fields(app, index, entry):
    from nsgablack.catalog.usage_learning import (documentation_fields, documentation_followup_parts,
        select_documentation_guide, snippet_parts, source_link_text)

    records = [index["examples"][identifier] for identifier in index["entries"].get(entry.key, ())]
    guide = select_documentation_guide(records)
    fields = documentation_fields(guide["snippets"]) if guide is not None else {}
    require(guide is not None and all(fields.get(field) for field in LEARNING_FIELDS),
            "Selected component guide has no complete human preparation and wiring instructions")
    fields = {field: tuple(source_link_text(value, guide["snippets"][0]["path"]) for value in values)
              for field, values in fields.items()}
    nodes = list(_visible_nodes(app.main))
    visible_text = "\n".join(str(node.value) for node in nodes if node.type == "markdown")
    all_code = [item.value for item in app.code]
    blocks = [_native_code(text) for snippet in guide["snippets"] for kind, text, _ in snippet_parts(snippet)
              if kind == "code" and text.strip()]
    require(blocks and all(block in all_code for block in blocks), "Teaching guide lost its exact native code blocks")
    primary_positions = [i for i, node in enumerate(nodes) if node.type == "code" and node.value == blocks[0]]
    require(primary_positions, "A Project receipt replaced the human guide in the main usage area")
    primary_position = primary_positions[0]
    for field in LEARNING_FIELDS:
        require(all(value in visible_text for value in fields[field]),
                f"Teaching guide did not expose its explicit {field} instructions")
    for field in ("放在哪", "先准备什么"):
        require(any(i < primary_position and node.type == "markdown" and fields[field][0] in node.value
                    for i, node in enumerate(nodes)), "Placement and preparation must precede the first component call")
    require(any(node.type == "markdown" and "接下来怎么接" in node.value
                for node in nodes), "Teaching guide lost its wiring instructions")
    leading, followup = documentation_followup_parts(guide["snippets"][0])
    for value in leading:
        expected = source_link_text(value, guide["snippets"][0]["path"])
        require(any(i < primary_position and node.type == "markdown" and expected in node.value
                    for i, node in enumerate(nodes)), "Teaching guide lost instructions for its first file")
    for kind, value, _ in followup:
        if kind == "text":
            value = re.sub(r"(?m)^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", r"**\1**", value)
            require(source_link_text(value, guide["snippets"][0]["path"]) in visible_text,
                    "Teaching guide lost an explanation between its code blocks")
    require("同一正式Case已构造的solver与问题候选管线" not in visible_text
            and "得到已装配组件或回调返回值" not in visible_text,
            "Generic manifest sentences replaced concrete preparation or output instructions")
    require(any(item.label.startswith("第一次装配") and not item.proto.expanded for item in app.expander),
            "The standard Project onboarding is missing or no longer collapsed")
    if entry.key == "bias.risk":
        require(all(value in visible_text for value in ("mc_mean", "mc_std", "mc_min", "mc_max", "safe_zero")),
                "RiskBias guide omitted its actual metrics or zero-fallback behavior")
        require(all(value in "\n".join(blocks) for value in ("MonteCarloEvaluationConfig", "mc_samples=8",
                                                              'reduce="mean"', "cvar_alpha=0.25", "random_seed=7")),
                "RiskBias guide uses a stale Monte Carlo configuration interface")
    return {"example_id": guide["id"], "fields": list(LEARNING_FIELDS)}


def _verify_app(AppTest, dashboard, index, entry, profile):
    from nsgablack.catalog.examples_ui import example_status
    from nsgablack.catalog.usage_learning import source_link_text, snippet_parts

    key = entry.key
    app = _open_app(AppTest, dashboard, key, profile)
    payload = {"key": key, "minimal_wiring": entry.minimal_wiring, "example_entry": entry.example_entry}
    require(example_status(payload) == "已运行示例",
            "Example search status does not match its published execution receipt")

    examples = [index["examples"][identifier] for identifier in index["entries"].get(key, ())]
    executed = [example for example in examples if example["verification"]["status"] == "executed"]
    require(bool(executed), "Representative component has no current successful execution receipt")
    primary = executed[0]
    text = "\n".join(item.value for item in app.markdown)
    code = [item.value for item in app.code]
    captions = "\n".join(item.value for item in app.caption)
    require("**用法**" in captions and f"**{primary['title']}**" in text,
            "Component detail did not render its focused usage example")
    source_blocks = [_native_code(value) for snippet in primary["snippets"] for kind, value, _ in snippet_parts(snippet)
                     if kind == "code" and value.strip()]
    require(source_blocks and all(block in code for block in source_blocks),
            "Component detail did not expose its actual usage code")
    require(primary["run_command"] in code, "Component detail omitted the supported Project command")
    require("**预期得到什么**" in text and "**实际运行结果**" in text,
            "Component detail did not separate expected and observed results")
    observed = "\n".join(primary["verification"]["observed_outputs"])
    require(observed in code, "Component detail omitted the receipt's observed execution output")
    require("退出码：0" in captions and "UTC+08:00" in captions,
            "Component detail omitted its successful receipt or localized execution time")
    require("已有运行收据" in captions, "Executed example lost its visible evidence status")
    require("运行依赖" in text and "输入与准备" in text and "可以修改什么" in text,
            "Component example omitted practical inputs, dependencies or configuration")
    source_path = primary["snippets"][0]["path"] if primary["snippets"] else ""
    require(all(source_link_text(value, source_path) in text for value in primary["inputs"])
            and all(source_link_text(value, source_path) in text for value in primary["expected_outputs"]),
            "Project evidence lost its original declared inputs or expected outputs")
    result = {"profile": profile, "entry_key": key, "example_id": primary["id"], "status": "executed"}
    if key in LEARNING_KEYS:
        result["teaching"] = _verify_learning_fields(app, index, entry)
        projects = [item for item in app.expander if item.label.startswith("完整 Project 与运行记录")]
        require(projects and all(not item.proto.expanded for item in projects),
                "Complete Project execution evidence is missing from its collapsed follow-up section")
        require(any(all(block in [item.value for item in project.code] for block in source_blocks)
                    and observed in [item.value for item in project.code] for project in projects),
                "Collapsed Project evidence lost its original source or observed receipt output")
    return result


def _verify_usage_app(AppTest, dashboard, index, entry, profile):
    from nsgablack.catalog.examples_ui import example_status
    from nsgablack.catalog.usage_learning import (documentation_baseline_parts, documentation_fields,
        select_documentation_guide, snippet_parts, source_link_text)

    records = [index["examples"][identifier] for identifier in index["entries"][entry.key]]
    focused = select_documentation_guide(records)
    require(focused is not None, "Published usage has no selected human guide")
    migration = focused.get("usage_status") == "migration_reference"
    with ExitStack() as stack:
        if migration:
            def reject_ai_replacement(*args, **kwargs):
                raise VerificationError("A migration page attempted to display an AI tutorial as current usage")
            stack.enter_context(patch("nsgablack.catalog.curation_ui.render_tutorial", reject_ai_replacement))
        app = _open_app(AppTest, dashboard, entry.key, profile)
    text = "\n".join(item.value for item in app.markdown)
    code = [item.value for item in app.code]
    blocks = [_native_code(value) for snippet in focused["snippets"] for kind, value, _ in snippet_parts(snippet)
              if kind == "code" and value.strip()]
    require((migration or bool(blocks)) and all(block in code for block in blocks),
            "Markdown usage lost its native copyable source code blocks")
    visible = list(_visible_nodes(app.main))
    main_text = "\n".join(str(node.value) for node in visible if node.type == "markdown")
    main_code = [node.value for node in visible if node.type == "code"]
    baseline_blocks = [_native_code(value) for snippet in focused["snippets"]
                       for kind, value, _ in documentation_baseline_parts(snippet)
                       if kind == "code" and value.strip()]
    require(all(block in main_code for block in baseline_blocks),
            "A later source chapter's main assembly code was hidden in collapsed evidence or variations")
    require(not any("```" in item.value for item in app.markdown),
            "Markdown code fences leaked into the rendered prose")
    captions = "\n".join(item.value for item in app.caption)
    fields = documentation_fields(focused["snippets"])
    require(all(fields.get(field) for field in COMPLETE_FIELDS)
            and "输入与准备" in main_text and "接下来怎么接" in main_text
            and "预期得到什么" in main_text and "运行入口" in main_text,
            "Usage card omitted its complete preparation, wiring or result checks")
    for snippet in focused["snippets"]:
        for field, values in documentation_fields((snippet,)).items():
            if field in COMPLETE_FIELDS:
                require(all(source_link_text(value, snippet["path"]) in main_text for value in values),
                        "A source or migration instruction was hidden outside the main usage area")
    expected = "迁移说明" if migration else "详细用法"
    require(example_status(entry.as_dict()) == expected,
            "Usage card was confused with a fragment, migration or execution evidence")
    if migration:
        require("**迁移说明**" in main_text and "替代示例不表示原组件已经实现或可直接装配" in main_text,
                "Migration page omitted its explicit implementation boundary")
        require("AI依据本版源码整理的用法" not in main_text and "### AI 使用说明" not in main_text,
                "Migration page displayed AI usage as a current implementation")
    require(any("源码已核对" in item.value and "未记录运行结果" in item.value for item in app.caption),
            "Source-checked usage lost its visible unexecuted evidence status")
    return {"profile": profile, "entry_key": entry.key, "example_id": focused["id"],
            "status": "migration_reference" if migration else "source_checked"}


def _verify_learning_app(AppTest, dashboard, index, entry, profile):
    app = _open_app(AppTest, dashboard, entry.key, profile)
    return {"profile": profile, "entry_key": entry.key, "status": "teaching_guide",
            "teaching": _verify_learning_fields(app, index, entry)}


def verify():
    require(configure_reader(os.environ) == "only"
            and os.environ.get("NSGABLACK_CATALOG_HOSTED_SOURCE") == "database",
            "Example acceptance requires the deployment-owned MySQL reader")
    require(os.environ.get("NSGABLACK_CATALOG_DB_READONLY") == "1", "Example reader must be read-only")
    require(not Path("/run/secrets/deepseek.json").exists(), "Web reader must not hold a model credential")

    from verify_release import verify_manifest
    from nsgablack.catalog import dashboard, examples_ui, facade
    from nsgablack.catalog.curation_provider import DeepSeekGenerator
    from nsgablack.catalog.examples import load_example_index
    from nsgablack.catalog.example_audit import audit_usage
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.units import UnitBinding
    from streamlit.testing.v1 import AppTest

    manifest, whitelist, _summary = verify_manifest(MANIFEST, None)
    configured = os.environ.get(examples_ui.INDEX_ENV, "").strip()
    require(bool(configured), "Web reader has no fixed example index")
    index = load_example_index(Path(configured))
    base = None
    index_digest = None
    if manifest.get("derivation") is not None:
        base = json.loads(Path("/opt/catalog/status-base-manifest.json").read_text())
        index_digest = hashlib.sha256(Path(configured).read_bytes()).hexdigest()
    publication = _example_publication_digest(manifest, base,
        preserved_index_sha256=manifest.get("derivation", {}).get("preserved_artifacts", {}).get("examples.json"),
        actual_index_sha256=index_digest)
    require(index["publication_digest"] == publication,
            "Example index belongs to a different source publication")
    source_summary = _verify_source_files(index, whitelist, SOURCE_ROOTS)
    counts = Counter(example["verification"]["status"] for example in index["examples"].values())
    executed_ids = sorted(identifier for identifier, example in index["examples"].items()
                          if example["verification"]["status"] == "executed")
    require(bool(executed_ids), "No independently executed examples were published")
    examples_ui._load_snapshot.cache_clear()
    calls = {"model": 0, "unit": 0, "solver": 0}

    def forbidden(kind):
        def reject(*args, **kwargs):
            calls[kind] += 1
            raise VerificationError("Example page crossed a model or algorithm execution boundary")
        return reject

    profiles, app_runs = {}, []
    with ExitStack() as stack:
        stack.enter_context(patch.object(DeepSeekGenerator, "generate", forbidden("model")))
        stack.enter_context(patch.object(DeepSeekGenerator, "_complete", forbidden("model")))
        stack.enter_context(patch.object(UnitBinding, "build", forbidden("unit")))
        stack.enter_context(patch.object(SolverBase, "run", forbidden("solver")))
        for profile in ("default", "framework-core"):
            source = facade.catalog_source_info(profile=profile, scope="framework", source_mode="only")
            require(source.get("effective_source") == source.get("route_db_backend") == "mysql"
                    and not source.get("db_error"), "Example acceptance did not read the actual MySQL Catalog")
            entries = facade.list_entries(profile=profile, scope="framework", source_mode="only", limit=None)
            by_key = {entry.key: entry for entry in entries}
            coverage = audit_usage(index, entries)
            require(coverage["complete_usage"], "A published component has no complete usage recipe")
            material = _verify_material_inventory(index, by_key)
            for key in material["migration_keys"]:
                require(examples_ui.example_status(by_key[key].as_dict()) == "迁移说明",
                        "A published migration component was labeled as working or executed usage")
            statuses = Counter(examples_ui.example_status({"key": entry.key, "minimal_wiring": entry.minimal_wiring,
                                                          "example_entry": entry.example_entry}) for entry in entries)
            for key in FOCUSED_KEYS:
                require(key in by_key, "Representative framework or ML component is absent from MySQL")
                app_runs.append(_verify_app(AppTest, dashboard, index, by_key[key], profile))
            for key in USAGE_KEYS:
                require(key in by_key, "New usage component is absent from MySQL")
                app_runs.append(_verify_usage_app(AppTest, dashboard, index, by_key[key], profile))
            for key in MIGRATION_KEYS:
                if key in USAGE_KEYS:
                    continue
                require(key in by_key, "Representative migration component is absent from MySQL")
                app_runs.append(_verify_usage_app(AppTest, dashboard, index, by_key[key], profile))
            for key in LEARNING_KEYS:
                if key in FOCUSED_KEYS:
                    continue  # Its receipt check also verified the primary teaching guide.
                require(key in by_key, "Representative teaching component is absent from MySQL")
                app_runs.append(_verify_learning_app(AppTest, dashboard, index, by_key[key], profile))
            require(by_key["bias.surrogate_control"].kind == "tool", "Control mapping was misclassified as scalar Bias")
            profiles[profile] = {"components": len(entries), "example_statuses": dict(statuses),
                                 "usage_coverage": coverage["counts"], "source_material": material}
    require(not any(calls.values()), "Example display invoked model inference or algorithm execution")
    return {"ok": True, "backend": "mysql", "read_only": True,
            "publication_digest": index["publication_digest"], "components": len(index["entries"]),
            "examples": len(index["examples"]), "verification_counts": dict(counts),
            "executed_ids": executed_ids, "source_verification": source_summary,
            "profiles": profiles, "app_runs": app_runs, "teaching_components": len(LEARNING_KEYS),
            "execution_calls": calls}


def main():
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = verify()
        code = 0
    except VerificationError as exc:
        result, code = {"ok": False, "error": str(exc)}, 1
    except Exception as exc:
        result, code = {"ok": False, "error_type": type(exc).__name__}, 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
