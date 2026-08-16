from __future__ import annotations

import numpy as np


class _Add:
    def __init__(self, value: float) -> None:
        self.value = float(value)

    def mutate(self, x, context=None):
        _ = context
        return np.asarray(x, dtype=float) + self.value


class _Scale:
    def __init__(self, factor: float) -> None:
        self.factor = float(factor)

    def mutate(self, x, context=None):
        _ = context
        return np.asarray(x, dtype=float) * self.factor


def test_pipeline_kernel_serial_slot_chain() -> None:
    from nsgablack.representation import build_pipeline_kernel

    spec = {
        "slots": (
            {"slot": "mutate", "mode": "serial", "operators": ("add_one", "times_two")},
        )
    }
    kernel = build_pipeline_kernel(
        spec,
        operator_registry={
            "add_one": _Add(1.0),
            "times_two": _Scale(2.0),
        },
    )

    out = kernel.run_slot("mutate", np.array([1.0, 2.0]), {})
    assert np.allclose(out, [4.0, 6.0])


def test_pipeline_kernel_router_slot_by_context() -> None:
    from nsgablack.representation import build_pipeline_kernel

    spec = {
        "slots": (
            {
                "slot": "mutate",
                "mode": "router",
                "selector_key": "phase",
                "routes": {"explore": "add_ten", "exploit": "add_one"},
                "strict": True,
            },
        )
    }
    kernel = build_pipeline_kernel(
        spec,
        operator_registry={
            "add_one": _Add(1.0),
            "add_ten": _Add(10.0),
        },
    )

    y_explore = kernel.run_slot("mutate", np.array([0.0, 0.0]), {"phase": "explore"})
    y_exploit = kernel.run_slot("mutate", np.array([0.0, 0.0]), {"phase": "exploit"})
    assert np.allclose(y_explore, [10.0, 10.0])
    assert np.allclose(y_exploit, [1.0, 1.0])


def test_pipeline_kernel_parallel_slot_merge_mean() -> None:
    from nsgablack.representation import build_pipeline_kernel

    spec = {
        "slots": (
            {
                "slot": "mutate",
                "mode": "parallel",
                "merge": "mean",
                "operators": ("add_two", "times_two"),
            },
        )
    }
    kernel = build_pipeline_kernel(
        spec,
        operator_registry={
            "add_two": _Add(2.0),
            "times_two": _Scale(2.0),
        },
    )

    out = kernel.run_slot("mutate", np.array([2.0, 4.0]), {})
    # branch1: [4, 6], branch2: [4, 8], mean -> [4, 7]
    assert np.allclose(out, [4.0, 7.0])


def test_pipeline_kernel_missing_operator_raises() -> None:
    from nsgablack.representation import build_pipeline_kernel

    spec = {"slots": ({"slot": "mutate", "operators": ("missing_operator",)},)}
    try:
        _ = build_pipeline_kernel(spec, operator_registry={})
    except KeyError as exc:
        assert "missing_operator" in str(exc)
        return
    raise AssertionError("expected missing operator KeyError")


def test_pipeline_kernel_slot_method_override_runs_custom_method() -> None:
    from nsgablack.representation import build_pipeline_kernel

    class PredictPlus:
        def predict(self, x, context=None):
            _ = context
            return np.asarray(x, dtype=float) + 5.0

    spec = {
        "slots": (
            {
                "slot": "head",
                "method": "predict",
                "mode": "serial",
                "operators": ("predict_plus",),
            },
        )
    }
    kernel = build_pipeline_kernel(spec, operator_registry={"predict_plus": PredictPlus()})
    out = kernel.run_slot("head", np.array([1.0, 2.0]), {})
    assert np.allclose(out, [6.0, 7.0])


def test_nsgablack_pipeline_policy_is_the_shared_blackbase_contract() -> None:
    from blackbase.kernel import OrchestrationPolicy as SharedOrchestrationPolicy
    from nsgablack.representation import OrchestrationPolicy, build_pipeline_kernel

    kernel = build_pipeline_kernel(
        {
            "slots": ({
                "slot": "mutate",
                "mode": "parallel",
                "merge": "mean",
                "operators": ("add", "scale"),
            },)
        },
        operator_registry={"add": _Add(1.0), "scale": _Scale(2.0)},
    )

    assert OrchestrationPolicy is SharedOrchestrationPolicy
    assert isinstance(kernel.slot_policies["mutate"], SharedOrchestrationPolicy)


def test_nsgablack_dynamic_slot_uses_shared_declarative_stages() -> None:
    from nsgablack.representation import build_pipeline_kernel

    kernel = build_pipeline_kernel(
        {
            "slots": ({
                "slot": "mutate",
                "mode": "dynamic",
                "stages": ((0, "early"), (3, "late")),
            },)
        },
        operator_registry={"early": _Add(1.0), "late": _Add(4.0)},
    )

    assert np.allclose(kernel.run_slot("mutate", np.array([0.0]), {"generation": 1}), [1.0])
    assert np.allclose(kernel.run_slot("mutate", np.array([0.0]), {"generation": 5}), [4.0])
