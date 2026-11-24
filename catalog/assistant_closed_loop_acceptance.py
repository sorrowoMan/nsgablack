"""Development-only acceptance of one model's inspect/edit/test/repair loop.

Expectations are fixed before model calls. A host validator runs every checked
candidate in a temporary standard Project while the same conversation is live.
This runner is not an arbitrary-Python sandbox or a public source executor.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import traceback

from .assistant_edit_acceptance import (
    EXECUTION_ALLOWED_MODULES, EXECUTION_ALLOWED_NAMESPACES, review_execution_source,
)
from .assistant_evaluation import content_digest, model_configuration_metadata
from .assistant_session_acceptance import create_teaching_project, _write
from .lab_assistant import AssistantProviderError
from .lab_api import verify_api_sources
from .lab_model_provider import complete_project_turn, create_assistant_generator, load_assistant_model_config
from .lab_project_assistant import ProjectAssistantRuntime


SCHEMA = "nsgablack.assistant_closed_loop_acceptance/v1"
TARGET = "cases/hybrid_search/adapter/closed_loop_ops.py"
EXECUTION_POLICY = ("开发验证器允许以下命名空间及其子模块：" + ", ".join(EXECUTION_ALLOWED_NAMESPACES)
                    + "；另外允许精确模块：" + ", ".join(sorted(EXECUTION_ALLOWED_MODULES))
                    + "。不允许I/O、动态导入、写入导入的全局模块/类或访问numpy.testing。"
                    "验证是在临时工程进行，原工程不写入。这不是任意Python安全沙箱。")
INITIALIZATION_CONTRACT = ("正式工厂还须显式绑定框架UniformInitializer(low=-4.0,high=4.0)，"
                           "使4个初始成员经正式repair/evaluate/admission建立，再提出3个后代；不要依赖旧默认数值bootstrap。")
IDEAS = (
    {"id": "grid_round_robin_survivor", "export": "grid_survivors",
     "instruction": "给NSGA-II新增一个确定性Pool生存选择函数grid_survivors(pool,*,count,rng=None)：候选至少二维，以前两维坐标向下取整形成单位网格cell=(floor(x0),floor(x1))，不是目标空间网格。先选selection feedback违反量<=0的可行行；每个cell内按第一选择目标升序、再按本次offered位置升序排队，cell按二元整数键字典序，逐轮每个非空cell取一行直到count满或可行行耗尽。若不够，再把不可行行按违反量、第一目标、offered位置升序补齐。返回本次输入Pool的派生Pool，保持精确版本和位置，不按数值或ref去重：同一ref占两个offered位置仍是不同位置。count=0返回空派生Pool，count<0或count>len(pool)明确拒绝。不得重评、改写输入/反馈或消耗RNG。实现完整独立Python模块到cases/hybrid_search/adapter/closed_loop_ops.py，导出grid_survivors与build_adapter()，工厂用NSGA2Adapter(population_size=4,offspring_size=3)绑定此survivor，保留默认父代、交叉和变化。先查真实接口，再用check_project_edit提交完整源码；本工具会在临时正式Project中执行预设验收，失败后根据真实诊断继续修改，直到交付通过验证的edit_digest或如实报告预算内失败。不要修改Problem、测试或原工程。"},
    {"id": "donor_direction_change", "export": "donor_direction_change",
     "instruction": "给NSGA-II新增完整change函数donor_direction_change(request,*,rng)：两个输入父代p0,p1的中点m=(p0+p1)/2；从本次request.pool的donor_bank子池读取首尾两个版本d0,d1，必须至少两个位置且首尾ref不同（允许同值不同身份），只物化选中的这两行。后继为clip(m+0.25*(d1-d0),-4,4)，恰好一个结果，用正式批次结果交付。max_outputs=0时返回空批次、不读取池、不消耗RNG；其它正数或None最多一个。正输出要求恰好两个输入父代且各有精确ref、存在可读donor_bank、候选维度一致；缺失、空或首尾同版本要明确拒绝。ChangeResult来源顺序严格为request.source_refs的两个版本后接d0、d1对应ref，不按数值合并，不修改父代、池成员或候选；不调用评估/选择，不额外使用随机数。实现完整独立模块到cases/hybrid_search/adapter/closed_loop_ops.py，导出donor_direction_change与build_adapter()，工厂使用NSGA2Adapter(population_size=4,offspring_size=3)只绑定这个完整change，不叠加旧交叉/mutator。先查真实ChangeRequest、ChangePool/Pool及结果接口；check_project_edit会在临时标准Project中立即执行预设验收，按其诊断自行修复后再提交。最终交付通过验收的edit_digest，不修改Problem或测试。"},
)


def source_digest(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _safe_error(error, directory):
    text = str(error).replace(str(directory), "<temporary_project>")
    return re.sub(r"(?i)(api[_-]?key|password|authorization|secret)\s*[:=]\s*\S+", r"\1=<redacted>", text)


def review_candidate_source(source):
    tree = review_execution_source(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("numpy.testing"):
                raise ValueError("validation_integrity_testing_access")
            imported.update(item.asname or item.name.split(".")[0] for item in node.names)
    def root_name(node):
        while isinstance(node, (ast.Attribute, ast.Subscript)):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "testing" and root_name(node) in imported:
            raise ValueError("validation_integrity_testing_access")
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign)) else ()
        for target in targets:
            if isinstance(target, (ast.Attribute, ast.Subscript)) and root_name(target) in imported:
                raise ValueError("validation_integrity_imported_object_write")
    return tree


def _fixture_pool(rows, *, run_id):
    from blackbase.types import CandidateBatch
    from nsgablack.core.state.solution_pool import SolutionPool
    from nsgablack.core.state.snapshot_store import InMemorySnapshotStore
    pool = SolutionPool(InMemorySnapshotStore(), run_id=run_id)
    refs = pool.put(CandidateBatch.from_candidates(rows,
        candidate_tokens=tuple(f"{run_id}:{i}" for i in range(len(rows)))))
    return pool, refs


def _grid_behavior(module):
    import numpy as np
    from types import SimpleNamespace
    from nsgablack.adapters.selection_pool import offered_pool, pool_selection_indices
    fn = module.grid_survivors
    # Repeated exact refs and repeated values exercise occurrence coordinates.
    rows = [[.1, .1], [.2, .2], [1.2, .1], [-.1, .1], [2.2, .1], [2.3, .2], [3.1, .1]]
    pool, refs = _fixture_pool(rows, run_id="closed-grid")
    offered_refs = (refs[0], refs[1], refs[2], refs[3], refs[4], refs[5], refs[0], refs[6])
    objectives = np.array([[3., 99.], [1., 88.], [2., 77.], [9., 66.], [0., 55.], [1., 44.], [1., 33.], [-99., 22.]])
    violations = np.array([0., 0., 0., 0., 0., 0., 0., 2.])
    # cell(-1,0):3; cell(0,0):1,6,0; cell(1,0):2; cell(2,0):4,5
    expected = (3, 1, 2, 4, 6, 5, 0, 7)
    original = pool.read(refs).numeric_matrix.copy()
    checks = 0
    with offered_pool(SimpleNamespace(solution_pool=pool), offered_refs,
                      objectives=objectives, violations=violations) as offered:
        for count in range(9):
            rng = np.random.default_rng(916)
            rng_before = content_digest(rng.bit_generator.state)
            result = fn(offered, count=count, rng=rng)
            indices = pool_selection_indices(offered, result)
            assert indices == expected[:count], f"grid/feasibility/tie/occurrence order differs for count={count}"
            assert result.refs == tuple(offered_refs[i] for i in expected[:count]), "exact references changed"
            assert content_digest(rng.bit_generator.state) == rng_before, "deterministic survivor consumed RNG"
            checks += 1
        for count in (-1, 9):
            rejected = False
            try:
                fn(offered, count=count)
            except (ValueError, IndexError):
                rejected = True
            assert rejected, "invalid survivor count accepted"
            checks += 1
        np.testing.assert_array_equal(offered.objectives, objectives)
        np.testing.assert_array_equal(offered.violations, violations)
    # Infeasible rows must be globally ranked after the feasible stage.
    with offered_pool(SimpleNamespace(solution_pool=pool), refs[:4],
            objectives=[[8.], [4.], [4.], [0.]], violations=[1., .2, .2, 3.]) as offered:
        got = pool_selection_indices(offered, fn(offered, count=4))
        assert got == (1, 2, 0, 3), "infeasible ordering differs"
        checks += 1
    with offered_pool(SimpleNamespace(solution_pool=pool), (), objectives=np.empty((0, 1)),
                      violations=np.empty(0)) as offered:
        assert pool_selection_indices(offered, fn(offered, count=0)) == ()
        checks += 1
    np.testing.assert_array_equal(pool.read(refs).numeric_matrix, original)
    return {"checks": checks, "scope": "Finite 2D inputs; selection feedback, duplicate offered occurrences, stable cell rounds and count boundaries."}


def _donor_behavior(module):
    import numpy as np
    from nsgablack.adapters import ChangeBatchResult, ChangeRequest
    from nsgablack.adapters.change_pool import ChangePool
    pool, refs = _fixture_pool([[-3.9, .2], [3.7, -.1], [-3., -2.], [.7, .9], [3., 2.]], run_id="closed-donor")
    pool.create_subpool("donor_bank", refs[2:])
    fn = module.donor_direction_change
    original = pool.read(refs).numeric_matrix.copy()
    checks = 0
    for parents in (original[:2], np.array([[3.9, 3.8], [3.7, 3.6]])):
        for maximum in (0, 1, 3, None):
            scope = ChangePool(pool)
            try:
                request = ChangeRequest(parents, source_refs=refs[:2], pool=scope, max_outputs=maximum)
                rng = np.random.default_rng(313)
                before = content_digest(rng.bit_generator.state)
                result = fn(request, rng=rng)
                assert isinstance(result, ChangeBatchResult), "explicit batch result required"
                assert len(result.results) == (0 if maximum == 0 else 1), "output limit differs"
                assert content_digest(rng.bit_generator.state) == before, "deterministic change consumed RNG"
                if maximum != 0:
                    expected = np.clip((parents[0] + parents[1]) / 2 + .25 * (original[4] - original[2]), -4., 4.)
                    np.testing.assert_allclose(result.results[0].candidate, expected, rtol=1e-12, atol=1e-12)
                    assert result.results[0].source_refs == (*refs[:2], refs[2], refs[4]), "source order or exact identity differs"
                    assert set(scope.used_refs) == {refs[2], refs[4]}, "change materialized extra donor rows"
                else:
                    assert scope.used_refs == (), "zero-output change read pool values"
                np.testing.assert_array_equal(request.parents, parents)
                checks += 1
            finally:
                scope.close()
    zero = ChangeRequest([[1., 2.], [2., 3.]], max_outputs=0)
    assert not fn(zero, rng=np.random.default_rng(5)).results
    checks += 1
    for members in ((), (refs[2],), (refs[2], refs[2])):
        pool.replace_subpool_members("donor_bank", members)
        scope = ChangePool(pool)
        try:
            rejected = False
            try:
                fn(ChangeRequest(original[:2], source_refs=refs[:2], pool=scope, max_outputs=1), rng=np.random.default_rng(1))
            except (ValueError, RuntimeError, IndexError, KeyError):
                rejected = True
            assert rejected, "invalid donor collection accepted"
            checks += 1
        finally:
            scope.close()
    pool.replace_subpool_members("donor_bank", (refs[2], refs[4]))
    np.testing.assert_array_equal(pool.read(refs).numeric_matrix, original)
    return {"checks": checks, "scope": "Explicit donor subpool, first/last exact versions, zero-output no-read, bounded direction step and unchanged inputs."}


def _formal_case(module, project, idea):
    import numpy as np
    from functools import wraps
    from blackbase.project import build_case, load_case_builder
    from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
    from blackbase.types import CandidateBatch
    from nsgablack.adapters import NSGA2Adapter
    from nsgablack.plugins.base import Plugin
    from nsgablack.representation import UniformInitializer
    class Seed(Plugin):
        def __init__(self):
            super().__init__("closed_loop_donor_seed")
        def on_solver_init(self, solver):
            refs = solver.store_solutions(CandidateBatch.from_candidates(
                [[-3., -2.], [.1, .8], [3., 2.]], candidate_tokens=("donor-a", "donor-middle", "donor-z")), source="closed-loop-donors")
            solver.solution_pool.create_subpool("donor_bank", refs)
    adapter = module.build_adapter()
    assert isinstance(adapter, NSGA2Adapter), "factory must build the declared NSGA2Adapter"
    assert adapter.cfg.population_size == 4 and adapter.cfg.offspring_size == 3, "factory changed declared sizes"
    initializer = adapter.get_bound_initializer()
    assert isinstance(initializer, UniformInitializer), "explicit standard initializer was not bound"
    assert initializer.checkpoint_identity()["low"] == -4. and initializer.checkpoint_identity()["high"] == 4.
    target = getattr(module, next(row["export"] for row in IDEAS if row["id"] == idea))
    assert inspect.isfunction(target), "declared operation must be a normal Python function"
    bound = adapter.get_bound_selector() if idea == IDEAS[0]["id"] else adapter.get_bound_change()
    assert getattr(bound, "function", None) is target, "factory bound a different operation than its declared export"
    calls = 0
    def profile(frame, event, _arg):
        nonlocal calls
        if event == "call" and frame.f_code is target.__code__:
            calls += 1
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1), owner_id="ai-closed-loop", scope="optimization")
    try:
        grant = ResourceContext.from_mapping(lease.resource_context(namespace="assistant.closed_loop"))
        solver = build_case(load_case_builder(project, "hybrid_search"), resource_context=grant,
                            component_overrides={"adapter": adapter})
        solver.add_plugin(Seed())
        problem_calls = []
        evaluate = solver.problem.evaluate
        @wraps(evaluate)
        def counted(*args, **kwargs):
            problem_calls.append(solver.run_progress_steps)
            return evaluate(*args, **kwargs)
        solver.problem.evaluate = counted
        before_profile = sys.getprofile()
        try:
            sys.setprofile(profile)
            solver.run(max_steps=2)
        finally:
            sys.setprofile(before_profile)
        assert calls >= 1, "factory did not actually bind/invoke the declared operation"
        assert solver.run_progress_steps == 2 and solver.evaluation_count == 7, f"got steps={solver.run_progress_steps}, evaluations={solver.evaluation_count}"
        assert problem_calls == [0] * 4 + [1] * 3, "initial seed evaluation/offspring evaluation did not use the declared stages"
        member_refs = adapter.get_population_solution_refs(solver)
        assert len(member_refs) == 4
        final_values = solver.read_solutions(member_refs).numeric_matrix
        raw_objectives, raw_violations = solver.solution_pool.read_raw_feedback(member_refs)
        optimum = np.asarray(solver.problem.optimum)
        np.testing.assert_allclose(raw_objectives[:, 0], np.sum((final_values - optimum) ** 2, axis=1))
        np.testing.assert_array_equal(raw_violations, np.zeros(4))
        assert np.isfinite(adapter.get_population_snapshot()[1]).all()
        return {"committed_steps": 2, "evaluations": solver.evaluation_count, "members": 4,
                "actual_problem_calls": len(problem_calls), "evaluation_batches": [4, 3],
                "all_final_member_raw_feedback_matches_problem": True,
                "operation_invocations": calls, "resource_threads": 1,
                "entry": "canonical Case builder + L0 grant + Solver.run"}
    finally:
        allocator.release(lease)


def _oracle_descriptor():
    return {"behavior": inspect.getsource(_grid_behavior) + inspect.getsource(_donor_behavior) + inspect.getsource(_formal_case),
            "ideas": IDEAS, "initialization": INITIALIZATION_CONTRACT}


def oracle_math_sha256():
    """Algorithm intent, hidden behavioral expectations and formal assertions."""
    return content_digest(_oracle_descriptor())


def execution_guard_profile():
    source_file = Path(inspect.getsourcefile(review_execution_source))
    return {"shared_guard_source_sha256": source_digest(inspect.getsource(review_execution_source)),
            "shared_guard_module_sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
            "local_effect_guard_sha256": source_digest(inspect.getsource(review_candidate_source)),
            "allowed_namespaces": list(EXECUTION_ALLOWED_NAMESPACES),
            "allowed_exact_modules": sorted(EXECUTION_ALLOWED_MODULES), "policy": EXECUTION_POLICY}


def spec_identity():
    return "closed_loop:" + content_digest({"oracle_math_sha256": oracle_math_sha256(),
                                            "execution_guard": execution_guard_profile()})


def _child(idea, project, source, out):
    result = {"status": "failed", "executed": False, "failed_stage": "identity", "validation_identity": spec_identity()}
    try:
        raw = Path(source).read_bytes()
        result["executed_source_sha256"] = hashlib.sha256(raw).hexdigest()
        result["code_sha256"] = result["executed_source_sha256"]
        result["failed_stage"] = "import"
        specification = importlib.util.spec_from_file_location("closed_loop_proposal", source)
        module = importlib.util.module_from_spec(specification)
        sys.modules[specification.name] = module
        result["executed"] = True
        specification.loader.exec_module(module)
        result["failed_stage"] = "behavior"
        result["behavior"] = (_grid_behavior(module) if idea == IDEAS[0]["id"] else _donor_behavior(module))
        result["failed_stage"] = "formal_case"
        result["formal_case"] = _formal_case(module, project, idea)
        result.update(status="passed", failed_stage=None)
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=_safe_error(exc, project)[:800],
                      traceback=_safe_error(traceback.format_exc(limit=8), project)[-4000:])
        frames = traceback.extract_tb(exc.__traceback__)
        submitted = Path(source).resolve()
        lines = submitted.read_text(encoding="utf-8").splitlines()
        result["candidate_error_context"] = [{"line": frame.lineno, "function": frame.name,
            "excerpt": "\n".join(f"{i + 1}: {lines[i]}" for i in range(max(0, frame.lineno - 3),
                                                                   min(len(lines), frame.lineno + 2)))[:1400]}
            for frame in frames if Path(frame.filename).resolve() == submitted][-2:]
    _write(Path(out), result)


@dataclass(frozen=True)
class HostExecutionSpec:
    target: str
    identity: object
    review: object
    policy: str
    child_module: str


def execute_candidate(proposal, idea, *, timeout_seconds=45, host_execution=None):
    """Host-selected isolated test receipt, returned before the next model turn."""
    if host_execution is not None and not isinstance(host_execution, HostExecutionSpec):
        raise ValueError("host_execution_spec_invalid")
    host = host_execution
    source = proposal["source"]
    digest = source_digest(source)
    identity = spec_identity() if host is None else host.identity()
    target = TARGET if host is None else host.target
    reviewer = review_candidate_source if host is None else host.review
    policy = EXECUTION_POLICY if host is None else host.policy
    base = {"status": "failed", "executed": False, "code_sha256": digest, "validation_identity": identity}
    if (proposal.get("path") != target or proposal.get("code_sha256") != digest
            or proposal.get("check", {}).get("status") != "needs_runtime_validation"):
        return {**base, "failed_stage": "identity", "error": "proposal/source/check mismatch"}
    try:
        reviewer(source)
    except Exception as exc:
        return {**base, "failed_stage": "source_review", "error_type": type(exc).__name__,
                "error": str(exc)[:1000], "policy": policy}
    with tempfile.TemporaryDirectory(prefix="ai-closed-loop-candidate-") as directory:
        sources, project_id = create_teaching_project(Path(directory))
        project = sources.resolve_project(project_id)
        path = project / target
        path.write_bytes(source.encode("utf-8"))
        output = Path(directory) / "validation.json"
        env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC") if key in os.environ}
        env.update(PYTHONPATH=str(Path(__file__).resolve().parents[2]), PYTHONIOENCODING="utf-8",
                   TEMP=directory, TMP=directory, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        child_module = "nsgablack.catalog.assistant_closed_loop_acceptance" if host is None else host.child_module
        command = [sys.executable, "-m", child_module, "--child", idea,
                   "--project", str(project), "--source", str(path), "--out", str(output)]
        try:
            run = subprocess.run(command, cwd=project, env=env, capture_output=True, timeout=timeout_seconds,
                                 text=True, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return {**base, "failed_stage": "timeout", "error": "candidate test subprocess exceeded deadline"}
        if run.returncode or not output.is_file():
            return {**base, "failed_stage": "subprocess", "error": "candidate process did not return its receipt"}
        result = json.loads(output.read_text(encoding="utf-8"))
        if (result.get("executed_source_sha256") != digest or result.get("code_sha256") != digest
                or result.get("validation_identity") != identity):
            return {**base, "failed_stage": "identity", "error": "executed source or test identity changed"}
        receipt = {**result, "execution_scope": "temporary standard teaching Project; original Project not modified"}
        if host is not None:
            receipt["validation_project"] = {"project_id": project_id,
                "source_digest": sources.describe_project(project_id)["source_digest"],
                "platform": sys.platform, "temporary": True,
                "identity_scope": "execution Project; separate from the model-side frozen Project"}
        return receipt


def _public_messages(messages):
    return [{key: deepcopy(value) for key, value in message.items() if key != "reasoning_content"} for message in messages]


def _evict_resume_background(messages, *, protected_paths=()):
    """Project rereadable initial background only; leave the host packet intact."""
    if len(messages) < 2 or messages[1].get("role") != "user":
        raise ValueError("resume_initial_packet_missing")
    original = messages[1]["content"]
    packet = json.loads(original)
    evicted = []
    def project(value, source=None):
        if isinstance(value, list):
            return [project(item, source) for item in value]
        if not isinstance(value, dict):
            return value
        source = value.get("source") if isinstance(value.get("source"), dict) else source
        result = {}
        for key, item in value.items():
            if (key in {"excerpt", "text", "code"} and isinstance(item, str)
                    and len(item.encode("utf-8")) > 256 and isinstance(source, dict)
                    and isinstance(source.get("path"), str) and isinstance(source.get("sha256"), str)
                    and source["path"] not in protected_paths):
                pointer = {"context_evicted": True, "path": source["path"], "source_sha256": source["sha256"],
                    "content_sha256": source_digest(item), "original_utf8_bytes": len(item.encode("utf-8")),
                    "notice": "Resume background body evicted; reread Project path or current framework declaration."}
                result[key] = pointer
                evicted.append({name: pointer[name] for name in ("path", "source_sha256", "content_sha256", "original_utf8_bytes")})
            else:
                result[key] = project(item, source)
        return result
    if isinstance(packet.get("project_state"), dict) and "excerpts" in packet["project_state"]:
        packet["project_state"]["excerpts"] = project(packet["project_state"]["excerpts"])
    if "framework_context" in packet:
        packet["framework_context"] = project(packet["framework_context"])
    if evicted:
        messages[1]["content"] = json.dumps(packet, ensure_ascii=False)
    return {"changed": bool(evicted), "original_packet_content_sha256": source_digest(original),
        "projected_packet_content_sha256": source_digest(messages[1]["content"]),
        "original_packet_bytes": len(original.encode("utf-8")),
        "projected_packet_bytes": len(messages[1]["content"].encode("utf-8")),
        "evicted_bodies": evicted, "scope": "resume_initial_background_only; full host packet retained in row.input"}


def _compact_restored_context(messages, *, target_bytes=80 * 1024):
    latest_exchange = max((i for i, row in enumerate(messages) if row.get("tool_calls")), default=-1)
    # Old pointers contain no callable facts. Their query remains in the paired
    # call; repeated labels/ranges and notices need not be sent every turn.
    for index, message in enumerate(messages):
        if index >= latest_exchange or message.get("role") != "tool" or len(message.get("content", "").encode()) <= 384:
            continue
        try:
            data = json.loads(message["content"])
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict) or not data.get("api_pointer_only"):
            continue
        sources, seen = [], set()
        files = {row["file_id"]: row for row in data.get("source_files", ())}
        for row in data.get("sources", ()):
            row = {**files[row["file_id"]], **row} if "file_id" in row and row["file_id"] in files else row
            source = ({"path": row["path"], "sha256": row["sha256"]}
                      if isinstance(row, dict) and "path" in row and "sha256" in row else deepcopy(row))
            key = json.dumps(source, sort_keys=True)
            if key not in seen:
                seen.add(key)
                sources.append(source)
        retained = {"schema": data.get("schema"), "source_scope": data.get("source_scope"),
            "status": data.get("status"), "sources": sources, "context_evicted": True, "api_pointer_only": True}
        if "historical_api_metadata" in data:
            retained["historical_api_metadata"] = {"status": "requery"}
        message["content"] = json.dumps(retained, ensure_ascii=False, separators=(",", ":"))
    ProjectAssistantRuntime._compact_context(messages, target_bytes=target_bytes)
    if len(json.dumps(messages, ensure_ascii=False).encode()) <= target_bytes:
        return
    # Already-evicted API summaries can still repeat a full file path and SHA
    # for every field/method. Deduplicate only this metadata; preserve exact
    # signatures, names, locations and every candidate/error tool message.
    for message in messages:
        if message.get("role") != "tool":
            continue
        try:
            data = json.loads(message["content"])
        except (ValueError, TypeError, KeyError):
            continue
        if (not isinstance(data, dict) or data.get("schema") != "nsgablack.lab_api/v1"
                or not data.get("context_evicted") or data.get("source_metadata_deduplicated")
                or data.get("api_pointer_only")):
            continue
        files, indices = [], {}
        def compact(value):
            if isinstance(value, list):
                return [compact(item) for item in value]
            if not isinstance(value, dict):
                return value
            if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
                key = value["path"], value["sha256"]
                if key not in indices:
                    indices[key] = len(files)
                    files.append({"file_id": indices[key], "path": key[0], "sha256": key[1]})
                return {"file_id": indices[key], **{name: compact(item) for name, item in value.items()
                                                   if name not in {"path", "sha256"}}}
            return {name: compact(item) for name, item in value.items()}
        data = compact(data)
        data.update(source_metadata_deduplicated=True, source_files=files,
                    source_metadata_notice="Source file_id resolves through source_files; signatures/fields and line ranges are unchanged.")
        message["content"] = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if len(json.dumps(messages, ensure_ascii=False).encode()) <= target_bytes:
        return
    latest_exchange = max((i for i, row in enumerate(messages) if row.get("tool_calls")), default=-1)
    for index, message in enumerate(messages):
        if index >= latest_exchange or message.get("role") != "tool":
            continue
        try:
            data = json.loads(message["content"])
        except (ValueError, TypeError, KeyError):
            continue
        if (not isinstance(data, dict) or data.get("schema") != "nsgablack.lab_api/v1"
                or data.get("api_pointer_only")):
            continue
        # Repeatedly retaining every inherited method signature defeats the
        # normal source-body eviction for large classes. Keep source identity,
        # query and names, with an explicit reread notice. This affects only
        # older API reads, never any check result, candidate or latest exchange.
        if data.get("api_details_evicted"):
            retained = {key: deepcopy(value) for key, value in data.items() if key in {
                "schema", "status", "query", "symbol", "kind", "source_scope", "sources", "historical_api_metadata"}}
            files = {row["file_id"]: row for row in data.get("source_files", ())}
            retained["sources"] = [{key: value for key, value in ({**files[row["file_id"]], **row}
                if "file_id" in row and row["file_id"] in files else row).items() if key != "file_id"}
                for row in data.get("sources", ())]
            retained.update(context_evicted=True, api_pointer_only=True,
                prior_api_content_sha256=source_digest(message["content"]),
                notice="Earlier API details evicted; source identities retained. Reread symbol/member for declarations.")
            message["content"] = json.dumps(retained, ensure_ascii=False, separators=(",", ":"))
            if len(json.dumps(messages, ensure_ascii=False).encode()) <= target_bytes:
                break
            continue
        else:
            retained = {key: deepcopy(value) for key, value in data.items()
                        if key not in {"methods", "fields", "member", "excerpt", "content", "text", "docstring"}}
            for key in ("methods", "fields"):
                if key in data:
                    retained[key + "_names"] = [row["name"] for row in data[key] if isinstance(row, dict) and "name" in row]
            if isinstance(data.get("member"), dict):
                retained["member"] = {key: deepcopy(value) for key, value in data["member"].items()
                                      if key in {"name", "kind", "source"}}
        retained.update(api_details_evicted=True, prior_api_content_sha256=source_digest(message["content"]),
            source_metadata_notice="Source file_id resolves through source_files; detailed API entries were explicitly evicted and can be reread.",
            notice="较早API详细签名与字段正文已移出；保留名称及来源身份，需要时按symbol/member定向重新查询。完整原始响应仍在绑定的历史报告中。")
        message["content"] = json.dumps(retained, ensure_ascii=False, separators=(",", ":"))
        if len(json.dumps(messages, ensure_ascii=False).encode()) <= target_bytes:
            break
    if len(json.dumps(messages, ensure_ascii=False).encode()) > target_bytes:
        for message in messages:
            if message.get("role") != "tool":
                continue
            try:
                data = json.loads(message["content"])
            except (ValueError, TypeError, KeyError):
                continue
            if not isinstance(data, dict) or not isinstance(data.get("check"), dict):
                continue
            check = data["check"]
            if check.get("diagnostics") and check.get("unresolved") == check["diagnostics"]:
                check.pop("unresolved")
                check["context_projection"] = {"unresolved": "Identical to diagnostics; duplicate omitted."}
                message["content"] = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        for index, message in enumerate(messages):
            if (index >= latest_exchange or message.get("role") != "assistant" or message.get("tool_calls")
                    or not message.get("content")):
                continue
            content = message["content"]
            if content.startswith('{"context_evicted":true,'):
                continue
            message["content"] = json.dumps({"context_evicted": True, "prior_assistant_content_sha256": source_digest(content),
                "notice": "Earlier assistant text evicted; retained in bound history. Calls, feedback and latest candidate preserved."},
                ensure_ascii=False, separators=(",", ":"))
            if len(json.dumps(messages, ensure_ascii=False).encode()) <= target_bytes:
                break


def _validate_history(messages):
    pending, used = set(), set()
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"assistant", "tool", "user"}:
            raise ValueError("continuation_history_role_invalid")
        if message["role"] == "tool":
            identity = message.get("tool_call_id")
            if identity not in pending or not isinstance(message.get("content"), str):
                raise ValueError("continuation_tool_pair_invalid")
            pending.remove(identity)
        else:
            if pending:
                raise ValueError("continuation_tool_pair_incomplete")
            for call in message.get("tool_calls", ()):
                identity = call.get("id")
                if (not isinstance(identity, str) or identity in used
                        or call.get("type") != "function" or not isinstance(call.get("function"), dict)):
                    raise ValueError("continuation_tool_call_invalid")
                used.add(identity)
                pending.add(identity)
    if pending:
        raise ValueError("continuation_tool_pair_incomplete")


def _restored_public_history(last):
    messages = deepcopy(last["messages"])
    if len(messages) < 2 or messages[0].get("role") != "system" or messages[1].get("role") != "user":
        raise ValueError("continuation_initial_packet_missing")
    history, appended = messages[2:], "none_received"
    if last.get("status") == "received":
        if last.get("tool_calls"):
            appended = "omitted_unpaired_last_tool_response"
        else:
            try:
                final = json.loads(last["visible_content"])
                if not isinstance(final, dict) or not {"explanation", "questions", "proposal_digest"} <= final.keys():
                    raise ValueError()
                history.append({"role": "assistant", "content": last["visible_content"]})
                appended = "received_public_final"
            except (ValueError, TypeError, KeyError):
                appended = "omitted_invalid_last_final"
    _validate_history(history)
    return history, appended


def _verify_prior_math(prior, acceptance_spec=None):
    if acceptance_spec is not None:
        if not isinstance(acceptance_spec, HostAcceptanceSpec):
            raise ValueError("host_acceptance_spec_invalid")
        if (prior.get("acceptance_profile") != acceptance_spec.name
                or prior.get("oracle_math_sha256") != acceptance_spec.math_identity()
                or prior.get("validation_identity") != acceptance_spec.identity()
                or prior.get("execution_guard_profile") != acceptance_spec.guard_profile()
                or prior.get("execution_policy") != acceptance_spec.execution_policy
                or any(row["id"] not in {idea["id"] for idea in acceptance_spec.ideas} for row in prior["cases"])):
            raise ValueError("continuation_oracle_changed")
        return
    # Original v1 did not separate its mathematical oracle from the policy.
    if prior.get("oracle_math_sha256") is None:
        expected = "closed_loop:" + content_digest({**_oracle_descriptor(), "execution_policy": prior["execution_policy"]})
    else:
        if prior["oracle_math_sha256"] != oracle_math_sha256():
            raise ValueError("continuation_oracle_changed")
        expected = "closed_loop:" + content_digest({"oracle_math_sha256": prior["oracle_math_sha256"],
                                                   "execution_guard": prior["execution_guard_profile"]})
    if expected != prior.get("validation_identity"):
        raise ValueError("continuation_oracle_changed")


def _bound_report_chain(path, expected_sha256, seen=(), *, acceptance_spec=None):
    path = Path(path).resolve()
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("continuation_prior_report_changed")
    if digest in seen or len(seen) >= 16:
        raise ValueError("continuation_report_chain_cycle")
    report = json.loads(raw)
    if report.get("schema") != SCHEMA or report.get("kind") not in {
            "same_model_live_validation", "same_model_development_continuation"}:
        raise ValueError("continuation_requires_closed_loop_report")
    _verify_prior_math(report, acceptance_spec)
    chain = []
    if report["kind"] == "same_model_development_continuation":
        link = report.get("continuation", {})
        chain = _bound_report_chain(link["prior_report_local_path"], link["prior_report_sha256"], (*seen, digest),
                                    acceptance_spec=acceptance_spec)
        parent = chain[-1]["report"]
        if (link.get("prior_validation_identity") != parent.get("validation_identity")
                or report.get("model_configuration") != parent.get("model_configuration")):
            raise ValueError("continuation_report_chain_binding_changed")
        parent_cases = {row["id"]: row for item in chain for row in item["report"]["cases"]}
        for row in report["cases"]:
            if row["id"] not in parent_cases or row["input"]["project_id"] != parent_cases[row["id"]]["input"]["project_id"]:
                raise ValueError("continuation_original_project_binding_invalid")
            if row["input"]["project"]["source_digest"] != parent_cases[row["id"]]["input"]["project"]["source_digest"]:
                raise ValueError("continuation_original_project_binding_invalid")
    return [*chain, {"path": str(path), "sha256": digest, "report": report}]


def _chain_accounting(chain):
    reservations, observed, all_observed, local_failures = 0, 0, True, 0
    rows = []
    for item in chain:
        report = item["report"]
        own = report["summary"]["model_request_attempts"]
        if type(own) is not int or own < 0:
            raise ValueError("continuation_request_accounting_invalid")
        transport = report.get("transport", {})
        actual = transport.get("relay_request_attempts")
        if actual is not None and (type(actual) is not int or not 0 <= actual <= own):
            raise ValueError("continuation_actual_request_accounting_invalid")
        if actual is not None and isinstance(transport.get("records"), list) and len(transport["records"]) != actual:
            raise ValueError("continuation_actual_request_accounting_invalid")
        if rows:
            link = report["continuation"]
            if (link.get("prior_model_request_attempts") not in {reservations, observed if all_observed else reservations}
                    or report["summary"].get("cumulative_model_request_attempts") != link["prior_model_request_attempts"] + own):
                raise ValueError("continuation_cumulative_request_accounting_invalid")
            if (all_observed and transport.get("prior_actual_http_requests", observed) != observed):
                raise ValueError("continuation_actual_request_accounting_invalid")
        reservations += own
        all_observed = all_observed and actual is not None
        observed += actual or 0
        preflight = transport.get("prior_local_preflight_failures", 0)
        if type(preflight) is not int or preflight < 0:
            raise ValueError("continuation_request_accounting_invalid")
        local_failures = max(local_failures, preflight)
        rows.append({"sha256": item["sha256"], "kind": report["kind"], "model_request_attempts": own,
                     "actual_http_requests": actual, "cumulative_model_request_attempts": reservations})
    return {"reports": rows, "model_request_attempts": reservations,
            "actual_http_requests": observed if all_observed else None,
            "reservation_history": reservations + local_failures,
            "local_preflight_failures": local_failures}


def _verify_historical_api_changes(changes):
    if not isinstance(changes, list) or len(changes) > 8:
        raise ValueError("continuation_historical_api_changes_invalid")
    paths = set()
    for change in changes:
        if (not isinstance(change, dict) or set(change) != {"path", "before_sha256", "after_sha256", "reason"}
                or not isinstance(change["path"], str) or change["path"] in paths
                or any(not isinstance(change[key], str) or not re.fullmatch(r"[0-9a-f]{64}", change[key])
                       for key in ("before_sha256", "after_sha256"))
                or change["before_sha256"] == change["after_sha256"]
                or not isinstance(change["reason"], str) or not 1 <= len(change["reason"]) <= 800):
            raise ValueError("continuation_historical_api_changes_invalid")
        paths.add(change["path"])
        verify_api_sources({"schema": "nsgablack.lab_api/v1", "source_scope": "framework",
                            "sources": [{"path": change["path"], "sha256": change["after_sha256"]}]})


def _continuation_cases(chain, historical_api_changes=(), *, acceptance_spec=None):
    root = chain[0]["report"]
    cases = []
    for root_row in root["cases"]:
        item = next(item for item in reversed(chain) if any(row["id"] == root_row["id"] for row in item["report"]["cases"]))
        report = item["report"]
        row = next(row for row in report["cases"] if row["id"] == root_row["id"])
        requests = [record for record in report["requests"] if record["idea"] == row["id"]]
        if not requests:
            raise ValueError("continuation_prior_request_missing")
        for request in requests:
            if content_digest(request["messages"]) != request["messages_sha256"]:
                raise ValueError("continuation_recorded_messages_changed")
        models = {record["model"] for entry in chain for record in entry["report"]["requests"]
                  if record["idea"] == row["id"] and record.get("status") == "received"}
        if len(models) != 1:
            raise ValueError("continuation_prior_model_ambiguous")
        last = requests[-1]
        packet = json.loads(last["messages"][1]["content"])
        if (packet.get("project_id") != root_row["input"]["project_id"]
                or packet.get("project", {}).get("source_digest") != root_row["input"]["project"]["source_digest"]):
            raise ValueError("continuation_original_project_binding_invalid")
        history, appended = _restored_public_history(last)
        for message in history:
            if message.get("role") != "tool":
                continue
            try:
                evidence = json.loads(message["content"])
            except (ValueError, TypeError, KeyError):
                continue
            if isinstance(evidence, dict) and evidence.get("schema") == "nsgablack.lab_api/v1":
                if evidence.get("source_metadata_deduplicated"):
                    if not evidence.get("source_files") and evidence.get("sources"):
                        maps = []
                        for entry in chain:
                            for saved in entry["report"]["requests"]:
                                if saved["idea"] != row["id"]:
                                    continue
                                for old in saved["messages"]:
                                    if old.get("role") != "tool" or old.get("tool_call_id") != message.get("tool_call_id"):
                                        continue
                                    try:
                                        original = json.loads(old["content"])
                                    except (ValueError, TypeError, KeyError):
                                        continue
                                    if isinstance(original, dict) and original.get("source_files"):
                                        maps.append((original["source_files"], entry["sha256"], saved["request"]))
                        if not maps or len({content_digest(item[0]) for item in maps}) != 1:
                            raise ValueError("continuation_api_source_map_missing_or_ambiguous")
                        evidence["source_files"] = deepcopy(maps[0][0])
                        evidence["source_metadata_recovery"] = {"report_sha256": maps[0][1], "request": maps[0][2],
                            "notice": "仅从同一tool_call_id的已绑定历史实际请求恢复原有文件身份映射；未添加新的接口事实。"}
                        message["content"] = json.dumps(evidence, ensure_ascii=False)
                    evidence = deepcopy(evidence)
                    files = {row["file_id"]: row for row in evidence["source_files"]}
                    evidence["sources"] = [{**files[row["file_id"]], **row} if "file_id" in row else row
                                           for row in evidence["sources"]]
                affected = []
                for source_row in evidence.get("sources", ()):
                    matching = next((change for change in historical_api_changes if change["path"] == source_row.get("path")
                                     and change["before_sha256"] == source_row.get("sha256")), None)
                    if matching is not None:
                        affected.append(matching)
                    else:
                        verify_api_sources({"schema": "nsgablack.lab_api/v1", "source_scope": "framework", "sources": [source_row]})
                if affected:
                    message["content"] = json.dumps({"schema": "nsgablack.lab_api/v1", "source_scope": "framework",
                        "status": "historical_source_changed", "historical_only": True, "sources": [],
                        "symbol": evidence.get("symbol"), "query": evidence.get("query"),
                        "historical_sources": evidence["sources"], "declared_source_changes": affected,
                        "prior_tool_content_sha256": source_digest(message["content"]),
                        "notice": "旧API正文已降级为历史引用，不能作为当前接口事实。必须用framework_api重新查询当前源码；未继承旧profile或通过收据。"}, ensure_ascii=False)
                if acceptance_spec is not None:
                    historical = json.loads(message["content"])
                    historical["historical_api_metadata"] = {"status": "previous_tool_version",
                        "extension_requires_requery": "value_contract"}
                    message["content"] = json.dumps(historical, ensure_ascii=False)
        cases.append({"id": row["id"], "project_id": root_row["input"]["project_id"],
            "source_digest": root_row["input"]["project"]["source_digest"], "model_id": next(iter(models)),
            "history": history, "history_sha256": content_digest(history),
            "history_report_sha256": item["sha256"],
            "last_request_number": last["request"], "last_response": appended,
            "prior_validation_attempts": sum(len(old.get("attempts", ())) for entry in chain
                for old in entry["report"]["cases"] if old["id"] == row["id"]), "prior_status": row["status"]})
    return cases


def _verify_development_continuation(value, *, acceptance_spec=None):
    if acceptance_spec is not None and not isinstance(acceptance_spec, HostAcceptanceSpec):
        raise ValueError("host_acceptance_spec_invalid")
    math_for = oracle_math_sha256 if acceptance_spec is None else acceptance_spec.math_identity
    policy = EXECUTION_POLICY if acceptance_spec is None else acceptance_spec.execution_policy
    profile = "original_two_ideas" if acceptance_spec is None else acceptance_spec.name
    if (not isinstance(value, dict) or value.get("schema") != "nsgablack.closed_loop_continuation/v1"
            or value.get("kind") != "same_model_public_conversation_reconstruction"
            or value.get("oracle_math_sha256") != math_for()
            or value.get("acceptance_profile", "original_two_ideas") != profile):
        raise ValueError("continuation_math_or_schema_mismatch")
    chain = _bound_report_chain(value["prior_report_local_path"], value["prior_report_sha256"], acceptance_spec=acceptance_spec)
    _verify_historical_api_changes(value.get("historical_api_changes", []))
    prior, accounting = chain[-1]["report"], _chain_accounting(chain)
    expected_prior = accounting["actual_http_requests"]
    if expected_prior is None:
        expected_prior = accounting["model_request_attempts"]
    if (value["prior_model_configuration"] != prior.get("model_configuration")
            or value["prior_validation_identity"] != prior["validation_identity"]
            or value["prior_model_request_attempts"] != expected_prior
            or value.get("report_chain") != accounting
            or value["policy_change"] != {"previous": prior["execution_policy"], "current": policy}):
        raise ValueError("continuation_metadata_changed")
    if {row["id"] for row in value["cases"]} != {row["id"] for row in chain[0]["report"]["cases"]}:
        raise ValueError("continuation_case_set_changed")
    for row in value.get("cases", ()):
        if content_digest(row["history"]) != row["history_sha256"]:
            raise ValueError("continuation_history_changed")
        _validate_history(row["history"])
        expected = next(old for old in _continuation_cases(chain, value.get("historical_api_changes", []),
                            acceptance_spec=acceptance_spec) if old["id"] == row["id"])
        if row != expected:
            raise ValueError("continuation_original_binding_changed")


def prepare_development_continuation(prior_report, *, expected_sha256, historical_api_changes=None, acceptance_spec=None):
    """Reconstruct only persisted public conversation; never invent a solution.

    Private reasoning was not retained by the original report, so this is not
    described as bit-identical hidden-session continuation. Original policy and
    receipts remain historical, with no authority in the new validation profile.
    """
    if acceptance_spec is not None and not isinstance(acceptance_spec, HostAcceptanceSpec):
        raise ValueError("host_acceptance_spec_invalid")
    math_for = oracle_math_sha256 if acceptance_spec is None else acceptance_spec.math_identity
    policy = EXECUTION_POLICY if acceptance_spec is None else acceptance_spec.execution_policy
    path = Path(prior_report).resolve()
    raw = path.read_bytes()
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64
            or hashlib.sha256(raw).hexdigest() != expected_sha256):
        raise ValueError("continuation_prior_report_digest_invalid")
    chain = _bound_report_chain(path, expected_sha256, acceptance_spec=acceptance_spec)
    prior, accounting = chain[-1]["report"], _chain_accounting(chain)
    changes = [] if historical_api_changes is None else deepcopy(historical_api_changes)
    _verify_historical_api_changes(changes)
    cases = _continuation_cases(chain, changes, acceptance_spec=acceptance_spec)
    prior_used = accounting["actual_http_requests"]
    if prior_used is None:
        prior_used = accounting["model_request_attempts"]
    continuation = {"schema": "nsgablack.closed_loop_continuation/v1",
        "kind": "same_model_public_conversation_reconstruction",
        "prior_report_local_path": str(path), "prior_report_sha256": expected_sha256,
        "prior_validation_identity": prior["validation_identity"],
        "prior_model_configuration": deepcopy(prior.get("model_configuration")),
        "prior_model_request_attempts": prior_used,
        "report_chain": accounting,
        "historical_api_changes": changes,
        "oracle_math_sha256": math_for(), "cases": cases,
        "acceptance_profile": "original_two_ideas" if acceptance_spec is None else acceptance_spec.name,
        "policy_change": {"previous": prior["execution_policy"], "current": policy},
        "reconstruction": "Old system and first packet user are replaced by the current host profile; paired public history is retained. Private reasoning was never retained; no manual source facts, solutions or passed receipt authority are imported."}
    _verify_development_continuation(continuation, acceptance_spec=acceptance_spec)
    return continuation


def _observed_repair(attempts, requests):
    passed = [a for a in attempts if a["result"].get("status") == "passed"
              and a["result"].get("executed") is True
              and a["result"].get("code_sha256") == a["code_sha256"]
              and a["result"].get("executed_source_sha256") == a["code_sha256"]]
    if not passed:
        return False
    latest = passed[-1]
    for attempt in attempts:
        receipt = attempt["result"]
        if (receipt.get("status") != "failed" or receipt.get("executed") is not True
                or attempt["code_sha256"] == latest["code_sha256"]
                or receipt.get("code_sha256") != attempt["code_sha256"]
                or receipt.get("executed_source_sha256") != attempt["code_sha256"]
                or not receipt.get("validation_identity") or not receipt.get("failed_stage")
                or receipt["validation_identity"] != latest["result"].get("validation_identity")):
            continue
        # Bind the failure to a newly returned tool call in this run. A SHA can
        # recur in historical conversations under a different validation profile.
        call_ids = set()
        for origin in requests:
            if origin.get("request") != attempt["after_request"] or origin.get("status") != "received":
                continue
            for call in origin.get("tool_calls") or ():
                function = call.get("function", {})
                if function.get("name") != "check_project_edit" or not isinstance(call.get("id"), str):
                    continue
                try:
                    arguments = json.loads(function["arguments"])
                except (ValueError, TypeError, KeyError):
                    continue
                if (isinstance(arguments, dict) and isinstance(arguments.get("source"), str)
                        and source_digest(arguments["source"]) == attempt["code_sha256"]):
                    call_ids.add(call["id"])
        if not call_ids:
            continue
        # Error must actually have reached a subsequent request, not only a log.
        for request in requests:
            if attempt["after_request"] < request["request"] <= latest["after_request"]:
                for message in request["messages"]:
                    if message.get("role") != "tool" or message.get("tool_call_id") not in call_ids:
                        continue
                    try:
                        data = json.loads(message["content"])
                    except (ValueError, TypeError, KeyError):
                        continue
                    if not isinstance(data, dict) or not isinstance(data.get("validation"), dict):
                        continue
                    validation = data["validation"]
                    if (data.get("code_sha256") == attempt["code_sha256"]
                            and validation.get("code_sha256") == attempt["code_sha256"]
                            and validation.get("executed_source_sha256") == attempt["code_sha256"]
                            and validation.get("validation_identity") == receipt["validation_identity"]
                            and validation.get("failed_stage") == receipt["failed_stage"]
                            and validation.get("executed") is True and validation.get("status") == "failed"):
                        return True
    return False


@dataclass(frozen=True)
class HostAcceptanceSpec:
    """Private host profile; callbacks/fixtures never enter model context."""

    name: str
    ideas: tuple
    target: str
    initialization_contract: str
    execution_policy: str
    identity: object
    math_identity: object
    guard_profile: object
    module_path: object
    edit_call_contracts: object
    max_requests: int = 36


def run_closed_loop(generator, *, complete=None, maximum_requests=24, max_model_calls=12,
                    allow_code_execution=False, executor=execute_candidate, progress=None, case_ids=None,
                    development_continuation=None, tool_protocol="native", acceptance_spec=None):
    if acceptance_spec is not None and not isinstance(acceptance_spec, HostAcceptanceSpec):
        raise ValueError("host_acceptance_spec_invalid")
    spec = acceptance_spec
    ideas = IDEAS if spec is None else spec.ideas
    target = TARGET if spec is None else spec.target
    identity_for = spec_identity if spec is None else spec.identity
    math_for = oracle_math_sha256 if spec is None else spec.math_identity
    guard_for = execution_guard_profile if spec is None else spec.guard_profile
    policy = EXECUTION_POLICY if spec is None else spec.execution_policy
    initialization = INITIALIZATION_CONTRACT if spec is None else spec.initialization_contract
    profile_path = Path(__file__) if spec is None else Path(spec.module_path)
    request_cap = 24 if spec is None else spec.max_requests
    if type(maximum_requests) is not int or not 1 <= maximum_requests <= request_cap:
        raise ValueError("closed_loop_request_budget_invalid")
    if type(max_model_calls) is not int or not 5 <= max_model_calls <= 20:
        raise ValueError("closed_loop_model_budget_invalid")
    if tool_protocol not in {"native", "json"}:
        raise ValueError("closed_loop_tool_protocol_invalid")
    if not allow_code_execution:
        raise ValueError("explicit_closed_loop_execution_required")
    if development_continuation is not None:
        _verify_development_continuation(development_continuation, acceptance_spec=spec)
        if spec is not None and max(development_continuation["prior_model_request_attempts"],
                development_continuation["report_chain"]["reservation_history"]) + maximum_requests > spec.max_requests:
            raise ValueError("host_acceptance_cumulative_budget_exceeded")
    selected = ideas if case_ids is None else tuple(next(x for x in ideas if x["id"] == name) for name in case_ids)
    if not selected or len({row["id"] for row in selected}) != len(selected):
        raise ValueError("closed_loop_case_selection_invalid")
    identity = identity_for()
    frozen_modules = {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (Path(__file__), profile_path)}
    module_sha = frozen_modules[str(profile_path.resolve())]
    def assert_profile_unchanged():
        assert identity_for() == identity
        assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
                   for path, digest in frozen_modules.items())
    report = {"schema": SCHEMA, "kind": "same_model_live_validation", "created_at": datetime.now(timezone.utc).isoformat(),
        "maximum_http_requests": maximum_requests, "model_calls_per_task": max_model_calls, "tool_protocol": tool_protocol,
        "validation_identity": identity, "acceptance_module_sha256": module_sha,
        "oracle_math_sha256": math_for(), "execution_guard_profile": guard_for(),
        "control_loop_module_sha256": frozen_modules[str(Path(__file__).resolve())],
        "acceptance_profile": "original_two_ideas" if spec is None else spec.name,
        "model_configuration": model_configuration_metadata(generator.config) if hasattr(generator, "config") else None,
        "cases": [], "requests": [], "limitations": [
            "Same configured generator and conversation per task; no model substitution or manual source repair.",
            "Hidden fixed behavior and formal Case assertions do not enter initial model input; ordinary failure feedback does.",
            "Dev subprocess and import policy are not an arbitrary-Python security sandbox.",
            "A first-try pass proves generation only; actual failed execution followed by observed correction is counted separately."]}
    report["execution_policy"] = policy
    report["request_count_basis"] = "Budget reservations before provider validation; actual HTTP attempts must be observed by the transport."
    transport = complete or partial(complete_project_turn, protocol=tool_protocol,
                                    feedback_protocol_errors=tool_protocol == "json")
    continuation_rows = {}
    prior_used = 0
    if development_continuation is not None:
        if report["model_configuration"] != development_continuation["prior_model_configuration"]:
            raise ValueError("continuation_model_configuration_changed")
        report["kind"] = "same_model_development_continuation"
        report["continuation"] = {key: deepcopy(value) for key, value in development_continuation.items() if key != "cases"}
        continuation_rows = {row["id"]: row for row in development_continuation["cases"]}
        if any(idea["id"] not in continuation_rows for idea in selected):
            raise ValueError("continuation_case_missing")
        prior_used = development_continuation["prior_model_request_attempts"]
        report["prior_model_request_attempts"] = prior_used
        report["prior_actual_http_requests"] = development_continuation["report_chain"]["actual_http_requests"]
        report["prior_reservation_history"] = development_continuation["report_chain"]["reservation_history"]
    used = 0
    for idea in selected:
        start = used
        instruction = idea["instruction"] + "\n" + initialization + "\n" + policy
        row = {"id": idea["id"], "instruction": instruction, "status": "failed", "attempts": []}
        report["cases"].append(row)
        resumed = continuation_rows.get(idea["id"])
        continuation_injected = False
        def measured(owner, messages, tools):
            nonlocal used, continuation_injected
            assert owner is generator, "model generator substitution is forbidden"
            if resumed is not None:
                _verify_development_continuation(development_continuation, acceptance_spec=spec)
                if not continuation_injected:
                    messages.extend(deepcopy(resumed["history"]))
                    messages.append({"role": "user", "content": json.dumps({
                        "kind": "development_driver_policy_continuation", "prior_report_sha256": development_continuation["prior_report_sha256"],
                        "notice": "继续同一算法任务与同一模型。当前system和工具定义生效，开发驱动与错误诊断有更新；算法意图、数学验收及原Project版本不变。旧验证profile及摘要仅为历史，不是新profile的通过凭据。请按当前工具重新验证并依据实际结果继续；不要改数学规则或仅宣称成功。",
                        "current_execution_policy": policy, "current_validation_identity": identity,
                        "oracle_math_sha256": math_for(), "preserved_history_sha256": resumed["history_sha256"],
                        **({"tool_metadata_update": "framework_api新增从源码字段工厂的显式返回注解派生value_contract；旧响应保留历史，需重新查询扩展元数据。"} if spec is not None else {}),
                        "limitations": "公开会话重建，未保存的私有推理没有恢复；未注入解法或手工接口事实。"}, ensure_ascii=False)})
                    continuation_injected = True
                    row["continuation"] = {key: deepcopy(value) for key, value in resumed.items() if key != "history"}
            # Runtime compaction occurs before invoking this transport hook.
            # Restoring history here must therefore be followed by another
            # ordinary compaction pass before hashing or serializing the wire.
            # The full reconstructed history remains in its SHA-bound prior
            # report; the model-visible projection discloses every eviction.
            background = _evict_resume_background(messages, protected_paths=(target,)) if resumed is not None else None
            if resumed is not None and "initial_background_projection" not in row["continuation"]:
                row["continuation"]["initial_background_projection"] = deepcopy(background)
            before = _public_messages(messages)
            context_target = (48 if tool_protocol == "json" else 80) * 1024
            _compact_restored_context(messages, target_bytes=context_target)
            after = _public_messages(messages)
            compaction = {"restored_messages_sha256": content_digest(before),
                "sent_messages_sha256": content_digest(after),
                "restored_messages_bytes": len(json.dumps(before, ensure_ascii=False).encode()),
                "sent_messages_bytes": len(json.dumps(after, ensure_ascii=False).encode()),
                "changed": before != after, "target_messages_bytes": context_target}
            if resumed is not None and "first_request_projection" not in row["continuation"]:
                row["continuation"]["first_request_projection"] = deepcopy(compaction)
            if used >= maximum_requests:
                raise AssistantProviderError("acceptance_request_limit")
            used += 1
            public = _public_messages(messages)
            record = {"idea": idea["id"], "request": used, "messages": public,
                      "messages_sha256": content_digest(public), "tools": deepcopy(tools), "status": "requested",
                      "context_compaction": compaction,
                      **({"background_projection": background} if background is not None else {})}
            report["requests"].append(record)
            if progress:
                progress(deepcopy(report))
            try:
                turn = transport(owner, messages, tools)
            except Exception as exc:
                record.update(status="failed_or_unknown", error_type=type(exc).__name__)
                raise
            record.update(status="received", model=turn.get("model"), finish_reason=turn.get("finish_reason"),
                          visible_content=turn.get("message", {}).get("content", ""),
                          tool_calls=deepcopy(turn.get("message", {}).get("tool_calls", [])),
                          protocol=turn.get("protocol"), protocol_receipt=deepcopy(turn.get("protocol_receipt")),
                          protocol_error=deepcopy(turn.get("protocol_error")),
                          protocol_wire_content=turn.get("protocol_wire_content"))
            if resumed is not None and turn.get("model") != resumed["model_id"]:
                raise AssistantProviderError("ai_project_model_changed")
            if resumed is not None:
                previous_ids = {call["id"] for message in messages for call in message.get("tool_calls") or ()}
                next_ids = [call.get("id") for call in turn.get("message", {}).get("tool_calls") or ()]
                if len(set(next_ids)) != len(next_ids) or previous_ids.intersection(next_ids):
                    raise AssistantProviderError("ai_project_tool_call_id_collision")
            return turn
        def validate(proposal):
            assert_profile_unchanged()
            attempt = {"number": len(row["attempts"]) + 1, "after_request": used,
                       "code_sha256": source_digest(proposal["source"]), "source": proposal["source"]}
            row["attempts"].append(attempt)
            try:
                result = executor(proposal, idea["id"])
            except Exception as exc:
                result = {"status": "failed", "executed": False, "code_sha256": attempt["code_sha256"],
                          "validation_identity": identity, "failed_stage": "validator", "error_type": type(exc).__name__,
                          "error": "host validator failed before returning a bound receipt"}
            assert result.get("code_sha256") == attempt["code_sha256"]
            assert result.get("validation_identity") == identity
            attempt["result"] = deepcopy(result)
            if progress:
                progress(deepcopy(report))
            return result
        try:
            with tempfile.TemporaryDirectory(prefix="ai-closed-loop-task-") as directory:
                sources, project_id = create_teaching_project(Path(directory))
                runtime = ProjectAssistantRuntime(sources, complete=measured, edit_validator=validate,
                    require_validated_edit=True, validation_identity=identity,
                    edit_call_contracts=({target: {
                        idea["export"] + (".pool" if idea["id"] == IDEAS[0]["id"] else ".request"):
                        "nsgablack.adapters.change_pool.ChangeSelection" if idea["id"] == IDEAS[0]["id"]
                        else "nsgablack.adapters.change.ChangeRequest"}} if spec is None else spec.edit_call_contracts(idea)),
                    tool_protocol=tool_protocol,
                    max_model_calls=max_model_calls, max_tool_calls=60)
                packet = runtime.prepare({"project_id": project_id, "instruction": instruction, "history": []})
                if resumed is not None and (packet["project_id"] != resumed["project_id"]
                        or packet["project"]["source_digest"] != resumed["source_digest"]):
                    raise ValueError("continuation_original_project_changed")
                row["input"] = deepcopy(packet)
                def capture(value):
                    row["runtime_progress"] = deepcopy(value)
                    if progress:
                        progress(deepcopy(report))
                result = runtime.generate(packet, generator, progress=capture)
                row["answer"] = result
                proposal = result.get("edit_proposal") or {}
                digest = source_digest(proposal.get("source", ""))
                last = row["attempts"][-1] if row["attempts"] else {}
                receipt = proposal.get("validation", {})
                if (not result.get("edit_digest") or result.get("edit_digest") != proposal.get("edit_digest")
                        or digest != proposal.get("code_sha256") or digest != last.get("code_sha256")
                        or receipt != last.get("result") or receipt.get("status") != "passed"
                        or receipt.get("executed") is not True or receipt.get("executed_source_sha256") != digest
                        or receipt.get("validation_identity") != identity):
                    raise ValueError("final_passed_execution_binding_invalid")
                task_requests = [record for record in report["requests"] if record["idea"] == idea["id"]]
                if len({record["model"] for record in task_requests if record.get("status") == "received"}) != 1:
                    raise ValueError("same_model_identity_not_preserved")
                row.update(status="passed", final_source_sha256=digest,
                    observed_runtime_repair=_observed_repair(row["attempts"], task_requests),
                    first_execution_pass=sum(a["result"].get("executed") is True for a in row["attempts"]) == 1,
                    first_validation_attempt_pass=len(row["attempts"]) == 1,
                    source_review_repair=any(a["result"].get("failed_stage") == "source_review" for a in row["attempts"]),
                    static_repair=any(trace.get("name") == "check_project_edit" and
                        trace.get("result", {}).get("check", {}).get("status") == "rejected" for trace in result["tool_trace"]))
        except Exception as exc:
            row.update(error=str(exc)[:180] if isinstance(exc, (AssistantProviderError, ValueError)) else "closed_loop_failed",
                       error_type=type(exc).__name__)
        assert_profile_unchanged()
        row["model_request_attempts"] = used - start
        report["summary"] = {"total": len(report["cases"]), "model_request_attempts": used,
            "prior_model_request_attempts": prior_used, "cumulative_model_request_attempts": prior_used + used,
            "reservation_history": report.get("prior_reservation_history", prior_used) + used,
            "passed": sum(x["status"] == "passed" for x in report["cases"]),
            "observed_runtime_repairs": sum(bool(x.get("observed_runtime_repair")) for x in report["cases"]),
            "first_execution_passes": sum(bool(x.get("first_execution_pass")) for x in report["cases"])}
        if progress:
            progress(deepcopy(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="同一模型查接口、写代码、实时测试和自行修复的隔离开发验收")
    parser.add_argument("--model-config", type=Path)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--allow-code-execution", action="store_true")
    parser.add_argument("--maximum-requests", type=int)
    parser.add_argument("--prior-report", type=Path)
    parser.add_argument("--prior-sha256")
    parser.add_argument("--case", dest="case_ids", action="append", choices=[idea["id"] for idea in IDEAS])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--child", choices=[x["id"] for x in IDEAS], help=argparse.SUPPRESS)
    parser.add_argument("--project", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--source", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child:
        if (not args.project or not args.source or args.allow_paid or args.allow_code_execution or args.model_config
                or args.prior_report or args.prior_sha256):
            parser.error("child receives only a temporary Project/source/output")
        _child(args.child, args.project, args.source, args.out)
        return 0
    if not args.model_config or not args.allow_paid or not args.allow_code_execution:
        parser.error("真实验收须显式配置模型、--allow-paid 与 --allow-code-execution")
    if bool(args.prior_report) != bool(args.prior_sha256):
        parser.error("开发续接须同时提供 prior-report 与明确的 prior-sha256")
    continuation = (prepare_development_continuation(args.prior_report, expected_sha256=args.prior_sha256)
                    if args.prior_report else None)
    generator = create_assistant_generator(load_assistant_model_config(args.model_config))
    report = run_closed_loop(generator, maximum_requests=args.maximum_requests or 24,
                             max_model_calls=12, case_ids=args.case_ids,
                             development_continuation=continuation, allow_code_execution=True,
                             progress=lambda value: _write(args.out, value))
    _write(args.out, report)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] == report["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
