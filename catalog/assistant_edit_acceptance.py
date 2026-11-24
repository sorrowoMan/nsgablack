"""Development-only model edit acceptance over two independently fixed ideas.

Public assistant tools only inspect source. This CLI separately executes a
selected, statically checked proposal in a temporary teaching Project, after
an additional narrow source review. That review is not a security sandbox or
a mathematical proof. Behaviour expectations are never sent to the model.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .assistant_evaluation import content_digest, model_configuration_metadata
from .assistant_session_acceptance import RequestBudget, create_teaching_project, _write
from .lab_assistant import AssistantProviderError
from .lab_model_provider import complete_project_turn, create_assistant_generator, load_assistant_model_config
from .lab_project_assistant import ProjectAssistantRuntime


SCHEMA = "nsgablack.assistant_edit_acceptance/v1"
EXECUTION_REVIEW_VERSION = "dev_import_review/v6"
EXECUTION_ALLOWED_NAMESPACES = ("numpy", "dataclasses", "functools", "typing", "__future__", "math", "itertools",
                                "nsgablack.adapters", "nsgablack.representation")
EXECUTION_ALLOWED_MODULES = frozenset({"blackbase.types"})
TARGET = "cases/hybrid_search/adapter/proposed_ops.py"
IDEAS = (
    {"id": "archive_distance_parents", "export": "ArchiveDistanceParents",
     "instruction": "我要做一个新的确定性父代规则：第一亲本取当前种群rank最小、同rank拥挤度最大、再并列取槽位最前的成员；第二亲本取reference_archive池中离第一亲本平方欧氏距离最远的解，距离并列时取档案中最前的精确引用。不断按第一、第二的顺序组成请求需要的父代序列，奇数个时最后只留第一亲本。当前种群成员引用唯一，档案允许同值不同身份。档案缺失或为空要明确拒绝。保留GA的交叉公式和生存选择，规则不额外随机抽样。请查真实框架API，实现完整独立Python模块到cases/hybrid_search/adapter/proposed_ops.py：导出ArchiveDistanceParents(pool_name='reference_archive')类及build_adapter()工厂；工厂用NSGA-II，population_size=4、offspring_size=3并绑定这项规则。不要运行或应用代码。请用check_project_edit校验完整source，并在最终交付引用该edit_digest。",
     "review_points": ["使用真实父代选择对象和准确请求数量，保留候选身份与确定性平局规则。",
                       "不修改种群、档案、候选值或GA生存逻辑；空档案明确拒绝。",
                       "提供经工具绑定的完整模块与正式Adapter工厂，不把静态检查称为算法验证。"]},
    {"id": "bounded_antithetic_batch", "export": "bounded_antithetic",
     "instruction": "我想给NSGA-II写一个新的完整change：取两个已选父代的中点c，对每个坐标独立抽u_i~Uniform(-1,1)，令h_i=min(0.3,c_i+4,4-c_i)，一对孩子为c+h*u与c-h*u。假定父代已在[-4,4]内；孩子也必须留在盒内并关于c对称。遵守本次max_outputs：0给空批次、1只给正向孩子，其它正数或None最多给这一对；0时不要消耗随机数。保留两个精确父代来源，不修改父代，不做评估或选择。请先查实际ChangeRequest/ChangeBatchResult/ChangeResult及绑定API，实现完整独立模块到cases/hybrid_search/adapter/proposed_ops.py，导出bounded_antithetic(request,*,rng)和build_adapter()；工厂用NSGA-II，population_size=4、offspring_size=3，仅绑定这个完整change，不叠加旧交叉或mutator。不要运行或应用代码。调用check_project_edit校验完整source后，最终引用edit_digest交付。",
     "review_points": ["真实完整change接口与显式批次结果，数量许可和精确来源正确。",
                       "独立坐标随机、边界和对称性兼容，父代不被原位改写。",
                       "采用原正式NSGA绑定与管线/评估，不私造生命周期；静态检查与行为验收分开。"]},
)


def _code_digest(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _verify_continuation(evidence):
    from .lab_api import verify_api_sources
    if (not isinstance(evidence, dict) or evidence.get("kind") != "source_assisted_development_delivery"
            or not evidence.get("previous_api_evidence") or not evidence.get("provenance")
            or not evidence.get("source_files")):
        raise ValueError("invalid_api_continuation")
    verify_api_sources({"schema": "nsgablack.lab_api/v1", "source_scope": "framework",
                        "sources": evidence["source_files"]})
    for fact in evidence["previous_api_evidence"]:
        if fact.get("status") != "found":
            raise ValueError("invalid_api_continuation_fact")


def prepare_api_continuation(reports, idea_id, *, maximum_bytes=24000):
    """Reuse only previous server tool facts; no answer or private rubric text."""
    from .lab_api import verify_api_sources
    if not 1000 <= maximum_bytes <= 24000:
        raise ValueError("invalid_api_continuation_limit")
    facts, bodies, seen, provenance, source_files = [], [], set(), [], {}
    for path, expected in reports:
        raw = Path(path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected:
            raise ValueError("api_continuation_report_changed")
        report = json.loads(raw)
        provenance.append({"report": Path(path).name, "sha256": digest})
        for case in report.get("cases", ()):
            if case.get("id") != idea_id:
                continue
            trace = case.get("answer", case.get("runtime_progress", {})).get("tool_trace", ())
            for call in trace:
                value = call.get("result", {})
                if (call.get("name") != "framework_api" or not call.get("ok")
                        or call.get("arguments", {}).get("project_path")
                        or value.get("status") != "found"
                        or call.get("arguments", {}).get("member") and value.get("member_status") != "found"):
                    continue
                verify_api_sources(value)
                key = (value["symbol"], call["arguments"].get("member"))
                if key in seen:
                    continue
                seen.add(key)
                for row in value["sources"]:
                    source_files[row["path"]] = {"path": row["path"], "sha256": row["sha256"]}
                fact = {key: deepcopy(value[key]) for key in ("schema", "status", "query", "symbol",
                    "source_scope", "source", "kind", "bases", "unresolved_bases",
                    "dynamic_attributes", "members_complete", "member_names", "constructor_status",
                    "member_status") if key in value}
                fact["source"].pop("sha256", None)  # The shared source_files table owns each verified hash.
                fact["fields"] = [{key: deepcopy(row[key]) for key in ("name", "annotation")
                                   if key in row} for row in value.get("fields", ())]
                member = value.get("member", {})
                if member:
                    fact["member"] = {key: deepcopy(member[key]) for key in
                        ("name", "signature", "parameters", "returns", "owner", "annotation", "kind") if key in member}
                    fact.pop("member_names", None)
                    if member.get("excerpt"):
                        bodies.append((fact, member["excerpt"], member.get("truncated", False)))
                facts.append(fact)
    evidence = {"kind": "source_assisted_development_delivery", "provenance": provenance,
                "source_files": list(source_files.values()), "previous_api_evidence": facts,
                "omitted_member_bodies": 0,
                "compaction": "Class queries retain names and field annotations; explicit member queries retain exact signatures. Bodies use remaining budget, newest query first."}
    def size():
        return len(json.dumps(evidence, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if size() > maximum_bytes:
        raise ValueError("api_continuation_signatures_exceed_limit")
    for fact, excerpt, truncated in reversed(bodies):
        fact["member"].update(excerpt=excerpt, truncated=truncated)
        if size() > maximum_bytes:
            fact["member"].pop("excerpt")
            fact["member"].pop("truncated")
            evidence["omitted_member_bodies"] += 1
    _verify_continuation(evidence)
    return evidence


def verify_checked_delivery(answer, *, source_digest, prior_api_evidence=None):
    """Bind the delivered bytes to the last actual checker result, not prose."""
    proposal = answer.get("edit_proposal")
    trace = answer.get("tool_trace", ())
    checks = [row for row in trace if row.get("name") == "check_project_edit"]
    if prior_api_evidence is not None:
        _verify_continuation(prior_api_evidence)
    if (not isinstance(proposal, dict) or not checks
            or not prior_api_evidence and not any(row.get("name") == "framework_api" and row.get("ok") for row in trace)):
        raise ValueError("edit_api_discovery_or_checked_delivery_missing")
    last = checks[-1]
    result, arguments = last.get("result", {}), last.get("arguments", {})
    digest = _code_digest(proposal.get("source", ""))
    if (not last.get("ok") or result.get("check", {}).get("status") != "needs_runtime_validation"
            or proposal.get("check", {}).get("status") != "needs_runtime_validation"
            or answer.get("edit_digest") != result.get("edit_digest")
            or proposal.get("edit_digest") != result.get("edit_digest")
            or proposal.get("path") != TARGET or arguments.get("path") != TARGET
            or arguments.get("source") != proposal.get("source")
            or arguments.get("bindings", {}) != proposal.get("bindings", {})
            or result.get("source_digest") != source_digest
            or proposal.get("source_digest") != source_digest
            or result.get("code_sha256") != digest or proposal.get("code_sha256") != digest
            or result.get("check", {}).get("code_sha256") != digest):
        raise ValueError("edit_last_check_or_source_binding_mismatch")
    return {"status": "matched", "edit_digest": result["edit_digest"], "code_sha256": digest,
            "source_digest": source_digest, "last_check_status": result["check"]["status"]}


def review_execution_source(source):
    """Conservative dev guard, never presented as an arbitrary-Python sandbox."""
    tree = ast.parse(source)
    allowed = EXECUTION_ALLOWED_NAMESPACES
    blocked = {"open", "eval", "exec", "compile", "__import__", "globals", "locals", "vars",
               "getattr", "setattr", "delattr", "input", "breakpoint", "exit", "quit"}
    blocked_attributes = {"load", "save", "savez", "savez_compressed", "loadtxt", "savetxt",
                          "fromfile", "tofile", "memmap", "ctypeslib", "f2py"}
    allowed_all, local_helper_calls, candidate_getattr_calls = set(), set(), set()
    parent_initializers = set()
    # A dataclass Unit can initialise new fields and then invoke its parent's
    # normal validation hook. This is a scoped call permission, not permission
    # to obtain arbitrary private attributes or reflect on a super object.
    bindings, repeated = {}, set()
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom) and not statement.level:
            for item in statement.names:
                local = item.asname or item.name
                if local in bindings:
                    repeated.add(local)
                bindings[local] = (statement.module or "") + "." + item.name
        elif isinstance(statement, ast.Import):
            for item in statement.names:
                if not item.asname:
                    continue  # Keep this exception limited to explicit aliases.
                if item.asname in bindings:
                    repeated.add(item.asname)
                bindings[item.asname] = item.name
    rebound = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
               and isinstance(node.ctx, (ast.Store, ast.Del))}
    rebound.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
    rebound.update(node.name for node in ast.walk(tree)
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
    # These binders store names as strings rather than Name(Store) nodes.
    # The type-parameter node names also cover Python 3.12+ lexical scopes.
    string_binding_fields = {"ExceptHandler": "name", "MatchAs": "name", "MatchStar": "name",
                             "MatchMapping": "rest", "TypeVar": "name", "ParamSpec": "name",
                             "TypeVarTuple": "name"}
    for node in ast.walk(tree):
        binding_field = string_binding_fields.get(type(node).__name__)
        if binding_field is not None:
            binding_name = getattr(node, binding_field, None)
            if isinstance(binding_name, str):
                rebound.add(binding_name)
    # Imports inside another scope cannot silently replace these declarations.
    top_imports = {id(node) for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and id(node) not in top_imports:
            rebound.update(item.asname or item.name.split(".")[0] for item in node.names)
    def declared_name(node):
        if isinstance(node, ast.Name) and node.id not in rebound | repeated:
            return bindings.get(node.id)
        if isinstance(node, ast.Attribute) and not node.attr.startswith("_"):
            owner = declared_name(node.value)
            return None if owner is None else owner + "." + node.attr
        return None
    for statement in tree.body:
        if not isinstance(statement, ast.ClassDef) or len(statement.bases) != 1:
            continue
        base = declared_name(statement.bases[0])
        if (base is None or not base.startswith("nsgablack.units.")
                or any(part.startswith("_") for part in base.split("."))):
            continue
        decorators = [item.func if isinstance(item, ast.Call) and not item.args else item
                      for item in statement.decorator_list]
        if len(decorators) != 1 or declared_name(decorators[0]) != "dataclasses.dataclass":
            continue
        if "super" in rebound or "super" in bindings:
            continue
        for method in statement.body:
            if (not isinstance(method, ast.FunctionDef) or method.name != "__post_init__"
                    or method.decorator_list
                    or [arg.arg for arg in (*method.args.posonlyargs, *method.args.args)] != ["self"]):
                continue
            pending = list(method.body)
            while pending:
                node = pending.pop()
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    continue
                if (isinstance(node, ast.Call) and not node.args and not node.keywords
                        and isinstance(node.func, ast.Attribute) and node.func.attr == "__post_init__"
                        and isinstance(node.func.value, ast.Call)
                        and isinstance(node.func.value.func, ast.Name) and node.func.value.func.id == "super"
                        and not node.func.value.args and not node.func.value.keywords):
                    parent_initializers.add(id(node.func))
                pending.extend(ast.iter_child_nodes(node))
    for statement in tree.body:
        if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == "__all__"
                and isinstance(statement.value, (ast.List, ast.Tuple))
                and all(isinstance(item, ast.Constant) and isinstance(item.value, str)
                        and item.value.isidentifier() and not item.value.startswith("_")
                        for item in statement.value.elts)):
            allowed_all.add(id(statement.targets[0]))
        if isinstance(statement, ast.ClassDef):
            methods = {node.name for node in statement.body if isinstance(node, ast.FunctionDef)
                       and node.name.startswith("_") and not node.name.startswith("__")}
            for method in statement.body:
                if (not isinstance(method, ast.FunctionDef) or not method.args.args
                        or method.args.args[0].arg != "self"):
                    continue
                for call in ast.walk(method):
                    if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                            and isinstance(call.func.value, ast.Name) and call.func.value.id == "self"
                            and call.func.attr in methods):
                        local_helper_calls.add(id(call.func))
    for call in ast.walk(tree):
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "getattr"
                and len(call.args) == 3 and not call.keywords and isinstance(call.args[1], ast.Constant)
                and call.args[1].value == "candidate"):
            candidate_getattr_calls.add(id(call.func))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [item.name for item in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if (isinstance(node, ast.ImportFrom) and node.level
                    or any(name not in EXECUTION_ALLOWED_MODULES and not any(
                               name == prefix or name.startswith(prefix + ".") for prefix in allowed)
                           for name in names) or any(item.name == "*" for item in node.names)):
                refused = ", ".join(names)
                raise ValueError("dev_execution_import_review_failed: " + refused
                                 + "; allowed namespaces: " + ", ".join(allowed)
                                 + "; allowed exact modules: " + ", ".join(sorted(EXECUTION_ALLOWED_MODULES))
                                 + "; relative and star imports are not allowed")
        if (isinstance(node, ast.Name)
                and ((node.id in blocked and id(node) not in candidate_getattr_calls)
                     or node.id.startswith("__") and id(node) not in allowed_all)):
            raise ValueError("dev_execution_name_review_failed: " + node.id)
        if (isinstance(node, ast.Attribute)
                and ((node.attr.startswith("_") and id(node) not in local_helper_calls | parent_initializers)
                     or node.attr in blocked_attributes)):
            raise ValueError("dev_execution_attribute_review_failed: " + node.attr)
    return tree


def _import_proposal(path):
    spec = importlib.util.spec_from_file_location("acceptance_proposed_ops", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _parent_behaviour(module):
    import numpy as np
    from blackbase.types import CandidateBatch
    from nsgablack.adapters.parent_selection import ParentSelectionRequest, resolve_parent_selection
    from nsgablack.core.state.solution_pool import SolutionPool
    from nsgablack.core.state.snapshot_store import InMemorySnapshotStore

    pool = SolutionPool(InMemorySnapshotStore(), run_id="holdout-parent-behaviour")
    def put(rows, prefix):
        return pool.put(CandidateBatch.from_candidates(rows,
            candidate_tokens=tuple(f"{prefix}:{i}" for i in range(len(rows)))))
    members = put([[0., 0.], [2., 2.], [1., 1.]], "member")
    external = put([[-2., -1.], [4., 3.], [-2., -1.]], "archive")
    pool.create_subpool("reference_archive", external)
    original = pool.read((*members, *external)).numeric_matrix.copy()
    selector = module.ArchiveDistanceParents(pool_name="reference_archive")
    identity = selector.checkpoint_identity()
    assert isinstance(identity, dict) and identity and selector.stateless is True
    checks = 0
    for count in (1, 2, 5, 6):
        request = ParentSelectionRequest(members, [1, 0, 0], [.3, .4, .9], count, {})
        rng = np.random.default_rng(998)
        state = content_digest(rng.bit_generator.state)
        got = selector.select(request, pool=pool, rng=rng)
        refs, slots = resolve_parent_selection(request, got)
        expected = tuple((members[2], external[0])[i % 2] for i in range(count))
        assert refs == expected, "rank/crowding, archive distance, order or count differs"
        assert slots == tuple(2 if i % 2 == 0 else None for i in range(count))
        assert content_digest(rng.bit_generator.state) == state, "deterministic selector consumed RNG"
        checks += 1
    request = ParentSelectionRequest(members, [0, 0, 1], [.5, .5, 9.], 2, {})
    refs, _ = resolve_parent_selection(request, selector.select(request, pool=pool, rng=np.random.default_rng(4)))
    assert refs == (members[0], external[1]), "member tie did not retain first slot"
    checks += 1
    for name in ("missing", "empty"):
        if name == "empty":
            pool.create_subpool(name)
        rejected = False
        try:
            module.ArchiveDistanceParents(pool_name=name).select(request, pool=pool, rng=np.random.default_rng(4))
        except (ValueError, RuntimeError):
            rejected = True
        assert rejected, "missing or empty archive was silently accepted"
        checks += 1
    np.testing.assert_array_equal(pool.read((*members, *external)).numeric_matrix, original)
    assert pool.subpool_refs("reference_archive") == external
    return {"checks": checks + 1, "scope": "Unique current-member refs; equal-valued archive identities retained."}


def _change_behaviour(module):
    import numpy as np
    from nsgablack.adapters.change import ChangeRequest
    from nsgablack.adapters.change_batch import ChangeBatchResult
    from nsgablack.core.state.solution_pool import SolutionRef
    refs = (SolutionRef("p", "r", 0, "parent-a"), SolutionRef("p", "r", 1, "parent-b"))
    checks = 0
    for parents in (np.array([[-3.9, 1.], [3.7, -1.2]]),
                    np.array([[3.95, -3.8], [3.99, -3.96]]),
                    np.array([[-4., 4.], [-4., 4.]])):
        for limit in (0, 1, 2, 3, None):
            before = parents.copy()
            request = ChangeRequest(parents, source_refs=refs, max_outputs=limit)
            rng = np.random.default_rng(431)
            got = module.bounded_antithetic(request, rng=rng)
            assert isinstance(got, ChangeBatchResult), "explicit ChangeBatchResult required"
            wanted = 2 if limit is None else min(limit, 2)
            assert len(got.results) == wanted, "max_outputs was not respected"
            c = parents.mean(axis=0)
            if wanted:
                u = np.random.default_rng(431).uniform(-1., 1., size=parents.shape[1])
                h = np.minimum(.3, np.minimum(c + 4., 4. - c))
                expected = (c + h * u, c - h * u)
                for index, item in enumerate(got.results):
                    np.testing.assert_allclose(item.candidate, expected[index], rtol=1e-12, atol=1e-12)
                    assert tuple(item.source_refs) == refs, "both exact sources must be explicit"
                    assert np.all(np.asarray(item.candidate) >= -4.) and np.all(np.asarray(item.candidate) <= 4.)
            else:
                assert content_digest(rng.bit_generator.state) == content_digest(np.random.default_rng(431).bit_generator.state)
            np.testing.assert_array_equal(parents, before)
            np.testing.assert_array_equal(request.parents, before)
            checks += 1
    return {"checks": checks, "scope": "Independent coordinates, zero/one/two outputs, boundary symmetry and immutable parents."}


def _formal_case_smoke(module, project):
    import numpy as np
    from blackbase.project import build_case, load_case_builder
    from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
    from blackbase.types import CandidateBatch
    from nsgablack.adapters import NSGA2Adapter
    from nsgablack.plugins.base import Plugin

    class ArchiveSeed(Plugin):
        def __init__(self):
            super().__init__("acceptance_reference_seed")
        def on_solver_init(self, solver):
            refs = solver.store_solutions(CandidateBatch.from_candidates(
                [[-3., 0.], [3., 0.], [0., 0.]], candidate_tokens=("ref-a", "ref-b", "ref-c")), source="reference-seed")
            solver.solution_pool.create_subpool("reference_archive", refs)

    adapter = module.build_adapter()
    assert isinstance(adapter, NSGA2Adapter)
    assert adapter.cfg.population_size == 4 and adapter.cfg.offspring_size == 3
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1), owner_id="assistant-edit-acceptance", scope="optimization")
    try:
        grant = ResourceContext.from_mapping(lease.resource_context(namespace="assistant.edit.acceptance"))
        solver = build_case(load_case_builder(project, "hybrid_search"), resource_context=grant,
            component_overrides={"adapter": adapter})
        solver.add_plugin(ArchiveSeed())
        solver.run(max_steps=2)
        assert solver.run_progress_steps == 2 and solver.evaluation_count == 7
        assert len(adapter.get_population_solution_refs(solver)) == 4
        assert np.isfinite(adapter.get_population_snapshot()[1]).all()
        return {"committed_steps": 2, "evaluations": 7, "path": "canonical Case builder + actual Solver.run"}
    finally:
        allocator.release(lease)


def _child(idea, project, source, output):
    result = {"status": "failed", "behaviour": None, "formal_case": None}
    stage = "proposal_import"
    try:
        module = _import_proposal(source)
        stage = "behaviour"
        result["behaviour"] = (_parent_behaviour(module) if idea == IDEAS[0]["id"] else _change_behaviour(module))
        stage = "formal_case"
        result["formal_case"] = _formal_case_smoke(module, project)
        result["status"] = "passed"
    except Exception as exc:
        result["failed_stage"] = stage
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:800]
    _write(Path(output), result)


def execute_proposal(proposal, idea, *, timeout_seconds=45):
    """Only operator-invoked dev acceptance executes code, never public tools."""
    source = proposal["source"]
    digest = _code_digest(source)
    expected = proposal.get("code_sha256", proposal.get("check", {}).get("code_sha256"))
    if expected != digest or proposal.get("path") != TARGET or proposal.get("check", {}).get("status") != "needs_runtime_validation":
        raise ValueError("unbound_or_rejected_edit_proposal")
    review_execution_source(source)
    with tempfile.TemporaryDirectory(prefix="assistant-edit-behaviour-") as directory:
        sources, project_id = create_teaching_project(Path(directory))
        project = sources.resolve_project(project_id)
        path = project / TARGET
        path.write_text(source, encoding="utf-8")
        output = Path(directory) / "behaviour.json"
        env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC") if key in os.environ}
        env.update(PYTHONPATH=str(Path(__file__).resolve().parents[2]), PYTHONIOENCODING="utf-8",
                   TEMP=directory, TMP=directory, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        command = [sys.executable, "-m", "nsgablack.catalog.assistant_edit_acceptance", "--child", idea,
                   "--project", str(project), "--source", str(path), "--out", str(output)]
        try:
            process = subprocess.run(command, cwd=project, env=env, capture_output=True,
                                     timeout=timeout_seconds, text=True, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return {"status": "failed", "error": "bounded_subprocess_timeout", "code_sha256": digest}
        if process.returncode or not output.is_file():
            return {"status": "failed", "error": "behaviour_process_failed", "code_sha256": digest,
                    "exit_code": process.returncode, "stderr_tail": process.stderr[-2000:]}
        result = json.loads(output.read_text(encoding="utf-8"))
        return {**result, "code_sha256": digest, "execution_review_version": EXECUTION_REVIEW_VERSION,
                "execution_scope": "dev-only temporary teaching Project; original source untouched"}


def run_edit_acceptance(generator, *, complete=None, maximum_requests=16, progress=None,
                        executor=execute_proposal, allow_code_execution=False, already_used=0,
                        case_ids=None, project_model_calls=4, project_tool_calls=12,
                        source_report_sha256=None, api_continuation=None):
    if type(maximum_requests) is not int or not 1 <= maximum_requests <= 16:
        raise ValueError("invalid_edit_acceptance_request_limit")
    if (type(project_model_calls) is not int or not 1 <= project_model_calls <= 6
            or type(project_tool_calls) is not int or not 1 <= project_tool_calls <= 24):
        raise ValueError("invalid_edit_acceptance_runtime_limits")
    selected = tuple(IDEAS if case_ids is None else
        (next((idea for idea in IDEAS if idea["id"] == identity), None) for identity in case_ids))
    if not selected or any(idea is None for idea in selected) or len({idea["id"] for idea in selected}) != len(selected):
        raise ValueError("invalid_edit_acceptance_case_selection")
    if source_report_sha256 is not None and (not isinstance(source_report_sha256, str)
            or len(source_report_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_report_sha256)):
        raise ValueError("invalid_edit_acceptance_source_report")
    budget = RequestBudget(maximum_requests, already_used=already_used)
    if api_continuation is not None:
        _verify_continuation(api_continuation)
        if not source_report_sha256 or len(selected) != 1:
            raise ValueError("api_continuation_requires_explicit_followup")
    transport = complete or complete_project_turn
    requests, rows = [], []
    current = {"idea": None, "continuation_injected": False}
    def measured(owner, messages, tools):
        if api_continuation is not None:
            _verify_continuation(api_continuation)
            if not current["continuation_injected"]:
                messages.append({"role": "user", "content": json.dumps(api_continuation,
                    ensure_ascii=False, separators=(",", ":"))})
                current["continuation_injected"] = True
        budget.reserve()
        record = {"idea": current["idea"], "request": budget.used,
            "messages_sha256": content_digest(messages),
            "request_messages": [{key: deepcopy(value) for key, value in message.items()
                                  if key != "reasoning_content"} for message in messages],
            "private_reasoning_omitted": True,
            "request_tools": deepcopy(tools), "status": "requested"}
        requests.append(record)
        turn = transport(owner, messages, tools)
        message = turn.get("message", {})
        record.update(status="received", model=turn.get("model"), finish_reason=turn.get("finish_reason"),
            visible_content=message.get("content", ""), tool_calls=deepcopy(message.get("tool_calls", [])))
        return turn
    report = {"schema": SCHEMA, "kind": ("source_assisted_development_delivery" if api_continuation else
                                         "known_idea_development_followup" if source_report_sha256
                                         else "new_idea_development_acceptance"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execution_review_version": EXECUTION_REVIEW_VERSION,
        "source_report_sha256": source_report_sha256,
        "api_continuation": deepcopy(api_continuation),
        "prior_http_requests": already_used,
        "runtime_limits": {"model_calls_per_idea": project_model_calls, "tool_calls_per_idea": project_tool_calls},
        "model_configuration": model_configuration_metadata(generator.config) if hasattr(generator, "config") else None,
        "maximum_http_requests": maximum_requests,
        "behaviour_spec_sha256": content_digest(inspect.getsource(_parent_behaviour) + inspect.getsource(_change_behaviour)),
        "cases": rows, "request_records": requests,
        "limitations": ["两个新想法的开发验收，不等于普遍算法正确性或模型已内化框架。",
                        "静态源码检查不执行代码，不构成数学证明或任意Python沙箱。",
                        "行为执行仅在独立开发子进程/教学Project临时副本；不改变公共AI权限或原始工程。",
                        "问题与验收预先冻结；行为断言与参考实现不进入模型输入；失败保留，不自动重试。"]}
    for idea in selected:
        current["idea"] = idea["id"]
        row = {"id": idea["id"], "instruction": idea["instruction"], "review_points": idea["review_points"],
               "protocol": "failed", "static_check": "not_delivered", "behaviour": {"status": "not_run"},
               "semantic_review": "pending"}
        rows.append(row)
        start = budget.used
        try:
            with tempfile.TemporaryDirectory(prefix="assistant-edit-idea-") as directory:
                sources, identity = create_teaching_project(Path(directory))
                runtime = ProjectAssistantRuntime(sources, complete=measured,
                    max_model_calls=project_model_calls, max_tool_calls=project_tool_calls)
                packet = runtime.prepare({"project_id": identity, "instruction": idea["instruction"], "history": []})
                row["input"] = deepcopy(packet)
                def capture(value):
                    row["runtime_progress"] = deepcopy(value)
                    if progress:
                        progress(deepcopy(report))
                result = runtime.generate(packet, generator, progress=capture)
                row.update(protocol="passed", answer=result, response_sha256=content_digest(result))
                proposal = result.get("edit_proposal")
                if not isinstance(proposal, dict):
                    row["error"] = "concrete_checked_edit_missing"
                else:
                    row["static_check"] = proposal.get("check", {}).get("status", "missing")
                    row["proposed_source_sha256"] = _code_digest(proposal["source"])
                    row["delivery_binding"] = verify_checked_delivery(result,
                        source_digest=packet["project"]["source_digest"], prior_api_evidence=api_continuation)
                    if allow_code_execution:
                        row["behaviour"] = executor(proposal, idea["id"])
                    else:
                        row["behaviour"] = {"status": "not_run", "reason": "explicit_dev_execution_required"}
        except AssistantProviderError as exc:
            row["error"] = str(exc) if str(exc).startswith(("ai_", "acceptance_")) else "provider_or_protocol_failure"
        except Exception as exc:
            row["error"] = "edit_acceptance_preparation_or_execution_failed"
            row["error_type"] = type(exc).__name__
        row["http_requests"] = budget.used - start
        report["summary"] = {"total": len(rows), "http_requests": budget.used,
            "new_http_requests": budget.used - already_used,
            "protocol_passed": sum(r["protocol"] == "passed" for r in rows),
            "checked_module_delivered": sum(r["static_check"] == "needs_runtime_validation" for r in rows),
            "behaviour_passed": sum(r["behaviour"]["status"] == "passed" for r in rows),
            "semantic_pending": len(rows)}
        if progress:
            progress(deepcopy(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="显式开发验收：模型真实API发现、模块静态检查与独立行为执行")
    parser.add_argument("--model-config", type=Path)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--allow-code-execution", action="store_true")
    parser.add_argument("--maximum-requests", type=int, default=16)
    parser.add_argument("--already-used", type=int, default=0)
    parser.add_argument("--case", dest="case_ids", action="append", choices=[idea["id"] for idea in IDEAS])
    parser.add_argument("--project-model-calls", type=int, default=4)
    parser.add_argument("--project-tool-calls", type=int, default=12)
    parser.add_argument("--source-report-sha256")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--child", choices=[idea["id"] for idea in IDEAS], help=argparse.SUPPRESS)
    parser.add_argument("--project", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--source", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child:
        if args.allow_paid or args.allow_code_execution or args.model_config or not args.project or not args.source:
            parser.error("子进程只接收独立教学工程和选定源码")
        _child(args.child, args.project, args.source, args.out)
        return 0
    if not args.model_config or not args.allow_paid:
        parser.error("真实模型验收须显式 --model-config 与 --allow-paid")
    generator = create_assistant_generator(load_assistant_model_config(args.model_config))
    report = run_edit_acceptance(generator, maximum_requests=args.maximum_requests,
        allow_code_execution=args.allow_code_execution,
        already_used=args.already_used, case_ids=args.case_ids,
        project_model_calls=args.project_model_calls, project_tool_calls=args.project_tool_calls,
        source_report_sha256=args.source_report_sha256,
        progress=lambda value: _write(args.out, value))
    _write(args.out, report)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["behaviour_passed"] == report["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
