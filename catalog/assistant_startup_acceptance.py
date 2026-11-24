"""Fresh component task for native startup guidance, with a frozen oracle.

No reference implementation is provided to the tested model. Formal execution
reuses the existing canonical teaching Case and L0 validation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace

from . import assistant_novel_acceptance as baseline
from . import assistant_closed_loop_acceptance as shared

IDEA = "deadband_blend_change"
TASK = {"id": IDEA, "export": IDEA, "instruction":
    "我想在NSGA-II里试一个带死区的双亲对称混合：对两个父代a、b的每个坐标，"
    "若两者差值绝对值严格大于1，第一个子代从a向b走四分之一，第二个从b向a走四分之一；"
    "差值不超过1的坐标分别保持各自父代值。两个子代分别裁剪到[-4,4]。"
    "这是替换完整变化的实验，其余搜索流程照旧，不叠加默认交叉或变异。"
    "导出deadband_blend_change(request,*,rng)，接收恰好两个有限非空一维数值父代及两个精确源引用。"
    "结果使用正式批次类型，顺序为靠a子代、靠b子代，二者都保留有序完整父引用（含重复）；"
    "不改变父代或RNG。max_outputs=0立即返回空批次，不要求父代有效；1只返回第一个，"
    "2及更大或None返回这两个。正输出时非法父代或缺引用须拒绝。"
    "另导出build_adapter()，装配正式NSGA-II，种群4、后代3、均匀初值[-4,4]。"
    "先直接说明会改哪个部件、是否需要新Unit或Problem，再查真实接口、实现、测试、修复。"
    "只修改cases/hybrid_search/adapter/novel_ops.py。"}


def behavior(module):
    import numpy as np
    from nsgablack.adapters import ChangeBatchResult, ChangeRequest
    fixtures = (
        ([[0., 0., 0.], [1., -1., 2.]], [[0., 0., .5], [1., -1., 1.5]]),
        ([[3., -3.], [-1., 1.]], [[2., -2.], [0., 0.]]),
        ([[10., -10.], [2., -2.]], [[4., -4.], [4., -4.]]),
    )
    checks = 0
    for number, (parents, expected) in enumerate(fixtures):
        pool, refs = shared._fixture_pool(parents, run_id=f"startup-deadband-{number}")
        for limit in (0, 1, 2, 5, None):
            rng = np.random.default_rng(163)
            before = shared.content_digest(rng.bit_generator.state)
            request = ChangeRequest(parents, source_refs=refs, max_outputs=limit)
            result = module.deadband_blend_change(request, rng=rng)
            assert isinstance(result, ChangeBatchResult)
            count = 0 if limit == 0 else 1 if limit == 1 else 2
            assert len(result.results) == count, "bounded output count differs"
            for index, item in enumerate(result.results):
                np.testing.assert_allclose(item.candidate, expected[index], rtol=1e-12, atol=1e-12)
                assert item.source_refs == refs, "exact ordered parent provenance differs"
            np.testing.assert_array_equal(request.parents, parents)
            np.testing.assert_array_equal(pool.read(refs).numeric_matrix, parents)
            assert shared.content_digest(rng.bit_generator.state) == before
            checks += 1
    _, refs = shared._fixture_pool([[0., 0.]], run_id="startup-repeated-source")
    result = module.deadband_blend_change(ChangeRequest([[0., 0.], [0., 0.]], source_refs=refs*2), rng=np.random.default_rng(3))
    assert all(item.source_refs == refs*2 for item in result.results)
    checks += 1
    assert not module.deadband_blend_change(ChangeRequest([[0., 0.]], max_outputs=0), rng=np.random.default_rng(1)).results
    checks += 1
    for rows, sources in (([[1., 2.]], refs), ([[1., 2.]]*3, refs*3),
                          ([[1., 2.]]*2, ()), ([[1., np.inf]]*2, refs*2)):
        rejected = False
        try:
            module.deadband_blend_change(ChangeRequest(rows, source_refs=sources), rng=np.random.default_rng(1))
        except (ValueError, TypeError):
            rejected = True
        assert rejected, "invalid positive-output parent input accepted"
        checks += 1
    return {"checks": checks, "scope": "Strict deadband boundary, symmetry, clipping, output limits, exact refs, no mutation/RNG."}


def spec_identity():
    return "startup-deadband-v1:" + shared.source_digest(json.dumps({
        "task": TASK, "behavior": inspect.getsource(behavior),
        "formal_case": inspect.getsource(baseline._formal_case),
        "guard": baseline.execution_guard_profile()}, sort_keys=True))


def execute_candidate(proposal):
    return shared.execute_candidate(proposal, IDEA, timeout_seconds=70,
        host_execution=shared.HostExecutionSpec(baseline.TARGET, spec_identity,
            baseline.review_candidate_source, baseline.POLICY, __name__))


def _child(idea, project, source, out):
    result = {"status": "failed", "executed": False, "failed_stage": "identity", "validation_identity": spec_identity()}
    try:
        if idea != IDEA:
            raise ValueError("startup_task_unknown")
        raw = Path(source).read_bytes()
        result["executed_source_sha256"] = result["code_sha256"] = hashlib.sha256(raw).hexdigest()
        result["failed_stage"] = "import"
        spec = importlib.util.spec_from_file_location("startup_proposal", source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        result["executed"] = True
        spec.loader.exec_module(module)
        result["failed_stage"] = "behavior"
        result["behavior"] = behavior(module)
        result["failed_stage"] = "formal_case"
        # Alias only the validation lookup; the real bound callable remains the
        # model's deadband component, observed in the native Case execution.
        proxy = SimpleNamespace(build_adapter=module.build_adapter, center_reflection_change=module.deadband_blend_change)
        result["formal_case"] = baseline._formal_case(proxy, project, baseline.IDEAS[0]["id"])
        result["formal_case"]["validated_component"] = IDEA
        result.update(status="passed", failed_stage=None)
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=shared._safe_error(exc, project)[:600],
                      traceback=shared._safe_error(traceback.format_exc(limit=5), project)[-3000:])
    shared._write(Path(out), result)


def main(argv=None):
    parser = argparse.ArgumentParser(description="新会话任务固定验收；不调用模型")
    parser.add_argument("--child", choices=[IDEA], required=True)
    for name in ("project", "source", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    _child(args.child, args.project, args.source, args.out)


if __name__ == "__main__":
    main()
