from __future__ import annotations

import numpy as np


def test_pipeline_orchestrator_serial_mutate_chain():
    from nsgablack.representation import OrchestrationPolicy, PipelineOrchestrator

    class AddOne:
        def mutate(self, x, context=None):
            _ = context
            return np.asarray(x, dtype=float) + 1.0

    class TimesTwo:
        def mutate(self, x, context=None):
            _ = context
            return np.asarray(x, dtype=float) * 2.0

    orch = PipelineOrchestrator(
        mutate_policy=OrchestrationPolicy(mode="serial", operators=[AddOne(), TimesTwo()])
    )
    out = orch.mutate(np.array([1.0, 2.0]), context={})
    assert np.allclose(out, [4.0, 6.0])


def test_pipeline_orchestrator_switch_by_context_index():
    from nsgablack.representation import OrchestrationPolicy, PipelineOrchestrator

    class AddOne:
        def mutate(self, x, context=None):
            _ = context
            return np.asarray(x, dtype=float) + 1.0

    class AddThree:
        def mutate(self, x, context=None):
            _ = context
            return np.asarray(x, dtype=float) + 3.0

    orch = PipelineOrchestrator(
        mutate_policy=OrchestrationPolicy(mode="switch", operators=[AddOne(), AddThree()], index_key="vns_k")
    )

    out0 = orch.mutate(np.array([0.0, 0.0]), context={"vns_k": 0})
    out1 = orch.mutate(np.array([0.0, 0.0]), context={"vns_k": 1})
    out_big = orch.mutate(np.array([0.0, 0.0]), context={"vns_k": 99})

    assert np.allclose(out0, [1.0, 1.0])
    assert np.allclose(out1, [3.0, 3.0])
    assert np.allclose(out_big, [3.0, 3.0])


def test_pipeline_orchestrator_router_by_context_key():
    from nsgablack.representation import OrchestrationPolicy, PipelineOrchestrator

    class Explore:
        def mutate(self, x, context=None):
            _ = context
            return np.asarray(x, dtype=float) + 10.0

    class Exploit:
        def mutate(self, x, context=None):
            _ = context
            return np.asarray(x, dtype=float) + 1.0

    orch = PipelineOrchestrator(
        mutate_policy=OrchestrationPolicy(
            mode="router",
            routes={"explore": Explore(), "exploit": Exploit()},
            selector_key="phase",
            strict=True,
        )
    )

    y_explore = orch.mutate(np.array([0.0, 0.0]), context={"phase": "explore"})
    y_exploit = orch.mutate(np.array([0.0, 0.0]), context={"phase": "exploit"})

    assert np.allclose(y_explore, [10.0, 10.0])
    assert np.allclose(y_exploit, [1.0, 1.0])


def test_pipeline_orchestrator_dynamic_repair_by_generation():
    from nsgablack.representation import OrchestrationPolicy, PipelineOrchestrator

    class ClipLow:
        def repair(self, x, context=None):
            _ = context
            arr = np.asarray(x, dtype=float)
            return np.clip(arr, -1.0, 1.0)

    class ClipHigh:
        def repair(self, x, context=None):
            _ = context
            arr = np.asarray(x, dtype=float)
            return np.clip(arr, -0.2, 0.2)

    orch = PipelineOrchestrator(
        repair_policy=OrchestrationPolicy(
            mode="dynamic",
            stages=[(0, ClipLow()), (5, ClipHigh())],
        )
    )

    x = np.array([0.8, -0.8], dtype=float)
    out_early = orch.repair(x, context={"generation": 2})
    out_late = orch.repair(x, context={"generation": 9})

    assert np.allclose(out_early, [0.8, -0.8])
    assert np.allclose(out_late, [0.2, -0.2])
