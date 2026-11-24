"""Three fresh, host-frozen component tasks using the existing same-model loop.

Private numerical fixtures and reference implementations are never model input.
This module is an isolated development validator, not a general Python sandbox.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import traceback
from types import FunctionType

from . import assistant_closed_loop_acceptance as shared
from .assistant_evaluation import content_digest
from .assistant_session_acceptance import _write


TARGET = "cases/hybrid_search/adapter/novel_ops.py"
INITIALIZATION_CONTRACT = shared.INITIALIZATION_CONTRACT
POLICY = shared.EXECUTION_POLICY + " 本轮额外允许nsgablack.units及其子模块，以定义纯数据Unit与builder；不允许读取验收器。"
IDEAS = (
    {"id": "center_reflection_expansion", "export": "center_reflection_change", "instruction":
     "实现一个中心反射/外扩完整change数学部件，不冒充完整Nelder-Mead优化器。导出center_reflection_change(request,*,rng)："
     "输入N>=2个父代，最后一行为w，其余N-1行算术均值为c；依次产生r=clip(2*c-w,-4,4)、e=clip(3*c-2*w,-4,4)。"
     "max_outputs=0直接返回空ChangeBatchResult，不读池、不消耗RNG；=1只交付r；>=2或None交付r,e两项，顺序固定。"
     "正输出要求所有父代有逐行精确source_refs，N至少2，数值有限；两个结果的source_refs均原样保留全部父代引用的顺序和重复次数。"
     "结果候选为一维向量，不修改父代、池或调用评估/选择；不使用随机数。数学行为会以N=2/3/4、裁剪和输出边界验证。"
     "另导出build_adapter()，构造NSGA2Adapter(population_size=4,offspring_size=3)，显式绑定UniformInitializer(-4,4)及此完整change；"
     "保留默认父代选择，NSGA2正式change的父代固定2，因此正式Case验证同一公式N=2，不要发明parent_count参数或额外取父代。"
     "完整独立模块写入cases/hybrid_search/adapter/novel_ops.py。查真实接口后check_project_edit，按真实错误自行修复并交付真实通过的edit_digest；不改Problem或验收。"},
    {"id": "archive_maximin_survivor", "export": "archive_maximin", "instruction":
     "实现冻结参考档案快照的确定性greedy maximin生存选择部件，不是父代选择。导出archive_maximin(pool,*,count,archive_values,rng=None)，"
     "archive_values为Host从真实参考Pool精确refs读取后冻结的tuple-of-tuples；这是本任务明确的静态参考集，不是动态跨池读授权。"
     "每次选一个仍未选择的offered位置：可行(selection违反量<=0)优先；不可行之间先按违反量升序；同一优先层最大化该候选到"
     "参考档案与所有已选候选的最小平方欧氏距离，再按第一selection目标升序、原offered位置升序破平局。每选一行就把它的向量加入距离参考集。"
     "若档案和已选均为空，所有最小距离视为正无穷，按目标/位置破平局。档案可为空；非空必须有限二维、维数等于候选。"
     "候选及反馈为有限数值。count为非bool的Python int，允许0到len(pool)；0立即返回空派生Pool，不读数值或RNG；越界/错误类型明确拒绝。"
     "返回原offered root的pool.take(位置)，不按ref或数值去重，同一ref占多个offered位置仍是不同槽位；不得重评、改写输入或消耗RNG。"
     "另导出build_adapter(*,archive_values)，用functools.partial将冻结tuple快照绑定到此普通Pool函数，交给NSGA2Adapter(population_size=4,offspring_size=3)的survivor，"
     "显式UniformInitializer(-4,4)，其余父代与变化保持默认；不得捕获活Pool、ndarray或RNG。完整独立模块到cases/hybrid_search/adapter/novel_ops.py。"
     "查真实接口后check_project_edit，按真实错误自行修复并交付通过的edit_digest；不改Problem或验收。"},
    {"id": "age_population_unit", "export": "AgePopulationUnit", "instruction":
     "新增带成员年龄的PopulationUnit组件，搜索仍由标准NSGA2负责。导出dataclass AgePopulationUnit(PopulationUnit)，age为非负整数一维数组，"
     "member_fields=('age',)，schema名novel.age_population、版本1、required_fields包含PopulationUnit所有字段和age、candidate_projection=False。"
     "on_members_changed(change)只读旧Unit并返回age更新：initialize和所有新增成员age=0；selection中幸存的旧槽位age+1；"
     "replacement中未换旧槽位age不增、新成员0；clear为空。严格按previous_member_indices识别旧槽位，不按数值或token猜身份；重复槽位分别保留。"
     "不要原位写旧age或Unit，不调用选择/评估/服务；返回数据由正式成员操作统一验证发布。导出AgePopulationBuilder(PopulationUnitBuilder)，"
     "unit_type为该新Unit，compatible_schemas=(PopulationUnit.schema,)，复用继承的正式dump/restore codec，不重写codec或缓存活对象。"
     "另导出build_adapter()，NSGA2Adapter(population_size=4,offspring_size=3,unit_binding=UnitBinding(AgePopulationBuilder()))，显式UniformInitializer(-4,4)，"
     "默认父代/变化/生存选择保持标准。会检查真实环境选择、重复来源、replacement、直接hook只读、部分接纳、步骤失败回滚和JSON checkpoint恢复；"
     "部分接纳后的incoming是最终交给update的紧凑行，不是原提案索引。新Unit应按需构建，恢复走codec不重放hook。"
     "完整独立模块到cases/hybrid_search/adapter/novel_ops.py。查真实接口后check_project_edit，依据真实错误修复并交付通过的edit_digest；不改Problem或验收。"},
)


def _reviewer():
    # Rebind the existing frozen guard's namespace data in private function
    # globals. Do not mutate the original policy/module or transform model code.
    guard = shared.review_execution_source
    guard_globals = {**guard.__globals__, "EXECUTION_ALLOWED_NAMESPACES":
                     (*guard.__globals__["EXECUTION_ALLOWED_NAMESPACES"], "nsgablack.units")}
    extended = FunctionType(guard.__code__, guard_globals, guard.__name__)
    integrity = shared.review_candidate_source
    return FunctionType(integrity.__code__, {**integrity.__globals__, "review_execution_source": extended}, integrity.__name__)


def review_candidate_source(source):
    return _reviewer()(source)


def _reflection_behavior(module):
    import numpy as np
    from nsgablack.adapters import ChangeBatchResult, ChangeRequest
    fn = module.center_reflection_change
    fixtures = (
        [[1., -2.], [-1., 3.]],
        [[1., 1.], [3., -1.], [-2., 2.]],
        [[-3., 1., .5], [1., -2., 3.], [2., 3., -1.], [3.9, -3.9, -3.9]],
    )
    checks = 0
    for number, rows in enumerate(fixtures):
        pool, refs = shared._fixture_pool(rows, run_id=f"novel-reflection-{number}")
        parents = np.asarray(rows)
        center = np.mean(parents[:-1], axis=0)
        expected = (np.clip(2 * center - parents[-1], -4., 4.), np.clip(3 * center - 2 * parents[-1], -4., 4.))
        for maximum in (0, 1, 2, 5, None):
            rng = np.random.default_rng(817)
            before = content_digest(rng.bit_generator.state)
            request = ChangeRequest(parents, source_refs=refs, max_outputs=maximum)
            result = fn(request, rng=rng)
            assert isinstance(result, ChangeBatchResult), "explicit ChangeBatchResult required"
            count = 0 if maximum == 0 else 1 if maximum == 1 else 2
            assert len(result.results) == count, "output count/order contract differs"
            for i, item in enumerate(result.results):
                np.testing.assert_allclose(item.candidate, expected[i], rtol=1e-12, atol=1e-12)
                assert np.asarray(item.candidate).ndim == 1 and item.source_refs == refs, "shape or exact ordered parent sources differ"
            assert content_digest(rng.bit_generator.state) == before, "deterministic change consumed RNG"
            np.testing.assert_array_equal(request.parents, parents)
            np.testing.assert_array_equal(pool.read(refs).numeric_matrix, parents)
            checks += 1
    pool, refs = shared._fixture_pool([[1., 2.], [3., 4.]], run_id="novel-repeated-parent")
    result = fn(ChangeRequest([[1., 2.]] * 3, source_refs=(refs[0], refs[0], refs[0]), max_outputs=2), rng=np.random.default_rng(2))
    assert all(item.source_refs == (refs[0], refs[0], refs[0]) for item in result.results)
    checks += 1
    assert not fn(ChangeRequest([[0., 0.]], max_outputs=0), rng=np.random.default_rng(1)).results
    checks += 1
    for parents, sources in (([[1., 2.]], refs[:1]), ([[1., 2.], [2., 3.]], ()),
                             ([[1., np.inf], [2., 3.]], refs)):
        rejected = False
        try:
            fn(ChangeRequest(parents, source_refs=sources), rng=np.random.default_rng(1))
        except (ValueError, TypeError):
            rejected = True
        assert rejected, "invalid positive-output parent input accepted"
        checks += 1
    return {"checks": checks, "scope": "N=2/3/4 component, clipping, bounded batch, exact repeated sources and no mutation/RNG."}


def _maximin_expected(values, objectives, violations, archive, count):
    import numpy as np
    chosen, remaining = [], list(range(len(values)))
    reference = [np.asarray(row) for row in archive]
    while len(chosen) < count:
        def key(i):
            distance = min((float(np.sum((values[i] - row) ** 2)) for row in reference), default=float("inf"))
            return violations[i] > 0, 0. if violations[i] <= 0 else float(violations[i]), -distance, float(objectives[i, 0]), i
        selected = min(remaining, key=key)
        chosen.append(selected)
        remaining.remove(selected)
        reference.append(values[selected])
    return tuple(chosen)


def _archive_behavior(module):
    import numpy as np
    from types import SimpleNamespace
    from nsgablack.adapters.selection_pool import offered_pool, pool_selection_indices
    rows = [[0., 0.], [3., 0.], [-3., 0.], [0., 2.], [0., -2.], [0., 0.], [4., 4.]]
    store, refs = shared._fixture_pool(rows, run_id="novel-greedy")
    archive_refs = refs[5:]
    store.create_subpool("reference_archive", archive_refs)
    archive = tuple(tuple(float(v) for v in row) for row in store.read(archive_refs).numeric_matrix)
    offered_refs = (*refs[:5], refs[0], refs[5], refs[6])
    x = store.read(offered_refs).numeric_matrix
    f = np.asarray([[6., 0.], [2., -100.], [1., 100.], [3., -100.],
                    [0., 100.], [-1., 200.], [-2., 300.], [-9., 400.]])
    v = np.asarray([0., 0., 0., 0., 0., 0., .3, .1])
    before = store.read(refs).numeric_matrix.copy()
    checks = 0
    for reference in (archive, (), ((1., 1.),)):
        with offered_pool(SimpleNamespace(solution_pool=store), offered_refs, objectives=f, violations=v) as pool:
            for count in (0, 1, 2, 4, len(pool)):
                rng = np.random.default_rng(711)
                rng_before = content_digest(rng.bit_generator.state)
                got = module.archive_maximin(pool, count=count, archive_values=reference, rng=rng)
                assert pool_selection_indices(pool, got) == _maximin_expected(x, f, v, reference, count), "greedy recurrence, feasibility or stable occurrence ordering differs"
                assert content_digest(rng.bit_generator.state) == rng_before
                np.testing.assert_array_equal(pool.values, x)
                np.testing.assert_array_equal(pool.objectives, f)
                checks += 1
            for invalid in (-1, len(pool) + 1, True, 1.5):
                rejected = False
                try:
                    module.archive_maximin(pool, count=invalid, archive_values=reference)
                except (ValueError, TypeError, IndexError):
                    rejected = True
                assert rejected, "invalid count accepted"
                checks += 1
    with offered_pool(SimpleNamespace(solution_pool=store), (), objectives=np.empty((0, 1)), violations=np.empty(0)) as pool:
        assert pool_selection_indices(pool, module.archive_maximin(pool, count=0, archive_values=())) == ()
        checks += 1
    with offered_pool(SimpleNamespace(solution_pool=store), offered_refs, objectives=f, violations=v) as pool:
        for bad in (((1.,),), ((np.inf, 0.),)):
            rejected = False
            try:
                module.archive_maximin(pool, count=1, archive_values=bad)
            except (ValueError, TypeError):
                rejected = True
            assert rejected, "invalid archive shape or nonfinite value accepted"
            checks += 1
    np.testing.assert_array_equal(store.read(refs).numeric_matrix, before)
    assert store.subpool_refs("reference_archive") == archive_refs
    return {"checks": checks, "scope": "Frozen exact-ref archive snapshot; greedy sequential coverage, feasibility, empty archive and repeated offered coordinates."}


def _age_behavior(module):
    import numpy as np
    from nsgablack.units import PopulationUnit, PopulationChange, UnitBinding
    from nsgablack.representation import PopulationUnitBuilder
    binding = UnitBinding(module.AgePopulationBuilder())
    adapter = module.build_adapter()
    assert adapter.algorithm_unit is None, "factory eagerly built Unit"
    unit = adapter.ensure_unit()
    assert type(unit) is module.AgePopulationUnit and type(binding.builder) is module.AgePopulationBuilder
    assert unit.member_fields == ("age",) and unit.schema.name == "novel.age_population" and unit.schema.version == 1
    assert PopulationUnit.schema in binding.builder.compatible_schemas
    assert binding.builder.dump.__func__ is PopulationUnitBuilder.dump and binding.builder.restore.__func__ is PopulationUnitBuilder.restore, "reuse the formal inherited codec"
    assert unit.age.shape == (0,) and unit.age.dtype.kind in "iu"
    checks = 1
    unit.initialize_population([[1., 0.], [2., 0.], [3., 0.]], [[1.], [2.], [3.]], [0.] * 3, candidate_tokens=("a", "b", "c"))
    np.testing.assert_array_equal(unit.age, [0, 0, 0]); checks += 1
    unit.age = np.asarray([6, 2, 9], dtype=int)
    before = binding.dump(unit)
    change = PopulationChange("selection", 3, 1, (2, None, 0), (None, 0, None))
    updates = unit.on_members_changed(change)
    np.testing.assert_array_equal(updates["age"], [10, 0, 7])
    assert np.asarray(updates["age"]).dtype.kind in "iu", "member ages must remain integers"
    assert binding.dump(unit) == before, "member hook mutated its old Unit"
    checks += 1
    unit.apply_selection([2, 3, 0, 0], [[1., 0.]], [[1.]], [0.], candidate_tokens=("new-a",))
    np.testing.assert_array_equal(unit.age, [10, 0, 7, 7])
    assert unit.age.dtype.kind in "iu" and (unit.age >= 0).all()
    assert unit.candidate_tokens == ("c", "new-a", "a", "a"); checks += 1
    unit.replace_evaluated_rows([1, 1, 2], [[4., 0.], [5., 0.], [6., 0.]], [[4.], [5.], [6.]], [0.] * 3,
                                candidate_tokens=("x", "y", "z"))
    np.testing.assert_array_equal(unit.age, [10, 0, 0, 7]); checks += 1
    assert unit.age.dtype.kind in "iu" and (unit.age >= 0).all()
    unit.attach_feedback(np.asarray(unit.objectives) + 1., np.zeros(4))
    np.testing.assert_array_equal(unit.age, [10, 0, 0, 7]); checks += 1
    saved = json.loads(json.dumps(binding.dump(unit)))
    calls = []
    previous = sys.getprofile()
    sys.setprofile(lambda frame, event, arg: calls.append(event) if event == "call" and frame.f_code is module.AgePopulationUnit.on_members_changed.__code__ else None)
    try:
        restored = binding.restore(saved)
    finally:
        sys.setprofile(previous)
    assert not calls and type(restored) is module.AgePopulationUnit
    assert binding.dump(restored) == saved; checks += 1
    restored.age[0] = 123
    assert unit.age[0] == 10; checks += 1
    # Use a fresh Adapter, then exercise its real RuntimeParticipant transaction.
    transaction = adapter.begin_step_transaction()
    baseline = binding.dump(adapter.algorithm_unit)
    adapter.algorithm_unit.apply_selection([0], [[8., 0.]], [[8.]], [0.], candidate_tokens=("incoming",))
    transaction.rollback()
    assert binding.dump(adapter.algorithm_unit) == baseline; checks += 1
    checkpoint = json.loads(json.dumps(adapter.get_state()))
    clone = module.build_adapter()
    clone.set_state(checkpoint)
    np.testing.assert_array_equal(clone.algorithm_unit.age, adapter.algorithm_unit.age)
    assert clone.algorithm_unit.candidate_tokens == adapter.algorithm_unit.candidate_tokens; checks += 1
    clone.algorithm_unit.clear_population()
    assert clone.algorithm_unit.age.shape == (0,) and clone.algorithm_unit.population is None; checks += 1
    clone.algorithm_unit.initialize_population(adapter.population, adapter.objectives, adapter.violations,
        candidate_tokens=adapter.get_population_candidate_tokens())
    np.testing.assert_array_equal(clone.algorithm_unit.age, [0, 0, 0, 0]); checks += 1
    return {"checks": checks, "scope": "Exact member provenance, readonly hook, replacement, inherited JSON codec and real participant rollback."}


def _factory(module, idea):
    if idea == IDEAS[1]["id"]:
        store, refs = shared._fixture_pool([[-3., -2.], [1., 2.], [3., -1.]], run_id="novel-formal-archive")
        store.create_subpool("reference_archive", refs)
        snapshot = tuple(tuple(float(v) for v in row) for row in store.read(refs).numeric_matrix)
        return module.build_adapter(archive_values=snapshot), snapshot
    return module.build_adapter(), None


def _formal_case(module, project, idea, *, variant="normal"):
    import numpy as np
    from functools import wraps, partial
    from blackbase.project import build_case, load_case_builder
    from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
    from blackbase.contracts import BatchDisposition
    from nsgablack.adapters import NSGA2Adapter
    from nsgablack.plugins.base import Plugin
    from nsgablack.representation import UniformInitializer
    adapter, reference = _factory(module, idea)
    assert isinstance(adapter, NSGA2Adapter) and adapter.cfg.population_size == 4 and adapter.cfg.offspring_size == 3
    initializer = adapter.get_bound_initializer()
    assert isinstance(initializer, UniformInitializer)
    assert initializer.checkpoint_identity()["low"] == -4. and initializer.checkpoint_identity()["high"] == 4.
    target = getattr(module, next(row["export"] for row in IDEAS if row["id"] == idea))
    if idea == IDEAS[0]["id"]:
        assert adapter.get_bound_change().function is target
        code = target.__code__
    elif idea == IDEAS[1]["id"]:
        bound = adapter.get_bound_selector().function
        assert isinstance(bound, partial) and bound.func is target and bound.keywords["archive_values"] == reference
        assert isinstance(bound.keywords["archive_values"], tuple)
        code = target.__code__
    else:
        assert adapter.unit_binding.builder.unit_type is target and adapter.algorithm_unit is None
        code = target.on_members_changed.__code__
    observed = []
    class Observe(Plugin):
        def __init__(self): super().__init__("novel-unit-observe")
        def on_generation_committed(self, solver, context):
            observed.append((tuple(adapter.get_population_candidate_tokens()),
                None if idea != IDEAS[2]["id"] else np.array(adapter.algorithm_unit.age, copy=True)))
    if variant != "normal":
        def selection(pool, *, count, rng=None):
            return pool.take(tuple(range(count)) if len(pool) == 4 else (4, 0, 5, 1))
        adapter.set_selector(selection)
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1), owner_id="novel-acceptance", scope="optimization")
    try:
        grant = ResourceContext.from_mapping(lease.resource_context(namespace="assistant.novel"))
        solver = build_case(load_case_builder(project, "hybrid_search"), resource_context=grant, component_overrides={"adapter": adapter})
        if variant != "normal":
            class Partial:
                policy_id = "novel-partial/v1"
                def select(self, candidates, feedback, context):
                    n = len(candidates.numeric_matrix)
                    return BatchDisposition(n, tuple(range(n)) if n == 4 else (0, 2), reason="novel_partial")
            solver.set_evaluation_acceptance_policy(Partial())
        solver.add_plugin(Observe())
        problem_calls = []
        evaluate = solver.problem.evaluate
        @wraps(evaluate)
        def counted(*args, **kwargs):
            problem_calls.append(solver.run_progress_steps)
            return evaluate(*args, **kwargs)
        solver.problem.evaluate = counted
        if variant == "rollback":
            original_update, updates = adapter.update, []
            def fail_after_update(*args, **kwargs):
                original_update(*args, **kwargs)
                updates.append(1)
                if len(updates) == 2:
                    raise RuntimeError("novel deliberate post-update failure")
            adapter.update = fail_after_update
        calls = []
        previous = sys.getprofile()
        sys.setprofile(lambda frame, event, arg: calls.append(event) if event == "call" and frame.f_code is code else None)
        failure = None
        try:
            solver.run(max_steps=2)
        except RuntimeError as exc:
            failure = exc
        finally:
            sys.setprofile(previous)
        assert calls, "declared component was not invoked by the real Case"
        assert problem_calls == [0] * 4 + [1] * 3 and solver.evaluation_count == 7
        refs = adapter.get_population_solution_refs(solver)
        assert len(refs) == 4
        values = solver.read_solutions(refs).numeric_matrix
        raw_f, raw_v = solver.solution_pool.read_raw_feedback(refs)
        optimum = np.asarray(solver.problem.optimum)
        np.testing.assert_allclose(raw_f[:, 0], np.sum((values - optimum) ** 2, axis=1))
        np.testing.assert_array_equal(raw_v, np.zeros(4))
        if variant == "rollback":
            assert failure is not None and "deliberate post-update" in str(failure)
            assert solver.run_progress_steps == 1 and len(observed) == 1
            assert tuple(adapter.get_population_candidate_tokens()) == observed[0][0]
            np.testing.assert_array_equal(adapter.algorithm_unit.age, [0, 0, 0, 0])
        else:
            assert failure is None and solver.run_progress_steps == 2
            if variant == "partial":
                np.testing.assert_array_equal(adapter.algorithm_unit.age, [0, 1, 0, 1])
                assert tuple(adapter.get_population_candidate_tokens())[1::2] == observed[0][0][:2]
                saved = json.loads(json.dumps(adapter.get_state()))
                clone = module.build_adapter()
                clone.set_selector(selection)
                clone.set_state(saved)
                np.testing.assert_array_equal(clone.algorithm_unit.age, [0, 1, 0, 1])
                assert clone.get_population_candidate_tokens() == adapter.get_population_candidate_tokens()
        return {"committed_steps": solver.run_progress_steps, "evaluations": 7, "members": 4,
                "component_invocations": len(calls), "variant": variant, "evaluation_batches": [4, 3],
                "entry": "canonical Case builder + L0 grant + Solver.run", "raw_feedback_matches_problem": True}
    finally:
        allocator.release(lease)


def oracle_math_sha256():
    return content_digest({"ideas": IDEAS, "initialization": INITIALIZATION_CONTRACT,
        "behavior": "".join(inspect.getsource(fn) for fn in (_reflection_behavior, _maximin_expected,
            _archive_behavior, _age_behavior, _factory, _formal_case))})


def execution_guard_profile():
    return {**shared.execution_guard_profile(), "additional_namespaces": ["nsgablack.units"],
            "review_binding_sha256": shared.source_digest(inspect.getsource(_reviewer)), "policy": POLICY}


def spec_identity():
    return "novel:" + content_digest({"oracle_math_sha256": oracle_math_sha256(), "guard": execution_guard_profile()})


def _contracts(idea):
    parameter, symbol = ((".request", "nsgablack.adapters.change.ChangeRequest") if idea["id"] == IDEAS[0]["id"] else
        (".pool", "nsgablack.adapters.change_pool.ChangeSelection") if idea["id"] == IDEAS[1]["id"] else
        (".on_members_changed.change", "nsgablack.units.population_operations.PopulationChange"))
    return {TARGET: {idea["export"] + parameter: symbol}}


def execute_candidate(proposal, idea, *, timeout_seconds=70):
    if idea not in {row["id"] for row in IDEAS}:
        raise ValueError("novel_case_unknown")
    return shared.execute_candidate(proposal, idea, timeout_seconds=timeout_seconds,
        host_execution=shared.HostExecutionSpec(TARGET, spec_identity, review_candidate_source, POLICY,
                                               "nsgablack.catalog.assistant_novel_acceptance"))


def run_novel_acceptance(generator, *, maximum_requests=36, max_model_calls=14, **kwargs):
    return shared.run_closed_loop(generator, maximum_requests=maximum_requests, max_model_calls=max_model_calls,
        executor=kwargs.pop("executor", execute_candidate), acceptance_spec=shared.HostAcceptanceSpec(
            "three_fresh_components/v1", IDEAS, TARGET, INITIALIZATION_CONTRACT, POLICY, spec_identity,
            oracle_math_sha256, execution_guard_profile, __file__, _contracts, 36), **kwargs)


def _child(idea, project, source, out):
    result = {"status": "failed", "executed": False, "failed_stage": "identity", "validation_identity": spec_identity()}
    try:
        raw = Path(source).read_bytes()
        result["executed_source_sha256"] = result["code_sha256"] = hashlib.sha256(raw).hexdigest()
        result["failed_stage"] = "import"
        specification = importlib.util.spec_from_file_location("novel_proposal", source)
        module = importlib.util.module_from_spec(specification)
        sys.modules[specification.name] = module
        result["executed"] = True
        specification.loader.exec_module(module)
        result["failed_stage"] = "behavior"
        behavior = {_idea["id"]: fn for _idea, fn in zip(IDEAS, (_reflection_behavior, _archive_behavior, _age_behavior))}
        result["behavior"] = behavior[idea](module)
        result["failed_stage"] = "formal_case"
        result["formal_case"] = _formal_case(module, project, idea)
        if idea == IDEAS[2]["id"]:
            result["partial_acceptance"] = _formal_case(module, project, idea, variant="partial")
            result["failed_step_rollback"] = _formal_case(module, project, idea, variant="rollback")
        result.update(status="passed", failed_stage=None)
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=shared._safe_error(exc, project)[:600],
                      traceback=shared._safe_error(traceback.format_exc(limit=7), project)[-3200:])
        frames = [frame for frame in traceback.extract_tb(exc.__traceback__) if Path(frame.filename).resolve() == Path(source).resolve()]
        lines = Path(source).read_text(encoding="utf-8").splitlines()
        result["candidate_error_context"] = [{"line": frame.lineno, "function": frame.name,
            "excerpt": "\n".join(f"{i + 1}: {lines[i]}" for i in range(max(0, frame.lineno - 2), min(len(lines), frame.lineno + 1)))[:600]}
            for frame in frames[-2:]]
    # Bound generic diagnostics without truncating source identities/status.
    while len(json.dumps(result, ensure_ascii=False).encode()) > 7600:
        if result.get("traceback"):
            result["traceback"] = result["traceback"][len(result["traceback"]) // 3:]
        elif result.get("candidate_error_context"):
            result["candidate_error_context"].pop(0)
        else:
            break
    _write(Path(out), result)


def main(argv=None):
    parser = argparse.ArgumentParser(description="冻结新组件数学验收；不调用任何模型")
    parser.add_argument("--validate", choices=[row["id"] for row in IDEAS])
    parser.add_argument("--child", choices=[row["id"] for row in IDEAS])
    parser.add_argument("--project", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.validate and not any((args.child, args.project, args.source, args.out)):
        result = execute_candidate(json.load(sys.stdin), args.validate)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "passed" else 1
    if args.child and args.project and args.source and args.out and not args.validate:
        _child(args.child, args.project, args.source, args.out)
        return 0
    parser.error("使用--validate CASE从stdin读取proposal，或内部--child和完整临时路径")


if __name__ == "__main__":
    raise SystemExit(main())
