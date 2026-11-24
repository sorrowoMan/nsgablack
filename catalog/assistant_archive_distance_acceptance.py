"""Versioned additive archive oracle. The original novel oracle stays intact.

Private assertion inputs are never sent to the tested Codex. This module reuses
the existing reviewed-source executor and canonical Case, not a new runtime.
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

from . import assistant_novel_acceptance as baseline
from . import assistant_closed_loop_acceptance as shared

PROFILE = "archive-distance-v2"
IDEA = "archive_maximin_survivor"


def nearest_reference_behavior(module):
    """Known opposite rankings, independent of the implementation's recurrence."""
    import numpy as np
    from types import SimpleNamespace
    from nsgablack.adapters.selection_pool import offered_pool, pool_selection_indices

    checks = 0
    for values in ((0., 4.), (4., 0.)):
        # To references 0 and 10: nearest distances squared are 0 and 16,
        # farthest distances squared are 100 and 36. Correct winner is 4.
        store, refs = shared._fixture_pool([[x, 0.] for x in values], run_id="nearest-reference-v2")
        before = store.read(refs).numeric_matrix.copy()
        for archive in (((0., 0.), (10., 0.)), ((10., 0.), (0., 0.))):
            for count in (1, 2):
                with offered_pool(SimpleNamespace(solution_pool=store), refs,
                                  objectives=np.zeros((2, 1)), violations=np.zeros(2)) as pool:
                    selected = module.archive_maximin(pool, count=count, archive_values=archive)
                    actual = pool_selection_indices(pool, selected)
                    expected = (values.index(4.), values.index(0.))[:count]
                    assert actual == expected, (
                        "nearest-reference distance ranking differs: "
                        f"expected offered positions {expected}, got {actual}")
                    assert tuple(selected.refs) == tuple(refs[i] for i in expected)
                    np.testing.assert_array_equal(pool.values, before)
                checks += 1
        np.testing.assert_array_equal(store.read(refs).numeric_matrix, before)
    return {"checks": checks, "scope": "Opposite nearest/farthest rankings; both candidate and archive orders; exact refs."}


def oracle_math_sha256():
    return shared.source_digest(json.dumps({
        "profile": PROFILE, "baseline_math": baseline.oracle_math_sha256(),
        "additional_behavior": inspect.getsource(nearest_reference_behavior),
    }, sort_keys=True))


def spec_identity():
    return PROFILE + ":" + shared.source_digest(json.dumps({
        "math": oracle_math_sha256(), "baseline_identity": baseline.spec_identity(),
    }, sort_keys=True))


def execute_candidate(proposal, idea=IDEA, *, timeout_seconds=70):
    if idea != IDEA:
        raise ValueError("archive_distance_profile_requires_archive_task")
    return shared.execute_candidate(proposal, idea, timeout_seconds=timeout_seconds,
        host_execution=shared.HostExecutionSpec(baseline.TARGET, spec_identity,
            baseline.review_candidate_source, baseline.POLICY, __name__))


def _child(idea, project, source, out):
    result = {"status": "failed", "executed": False, "failed_stage": "identity",
              "validation_identity": spec_identity()}
    try:
        if idea != IDEA:
            raise ValueError("archive_distance_profile_requires_archive_task")
        raw = Path(source).read_bytes()
        result["executed_source_sha256"] = result["code_sha256"] = hashlib.sha256(raw).hexdigest()
        result["failed_stage"] = "import"
        spec = importlib.util.spec_from_file_location("archive_distance_proposal", source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        result["executed"] = True
        spec.loader.exec_module(module)
        result["failed_stage"] = "behavior"
        extra = nearest_reference_behavior(module)
        old = baseline._archive_behavior(module)
        result["behavior"] = {"checks": old["checks"] + extra["checks"],
                              "baseline_checks": old["checks"], "additional_checks": extra["checks"],
                              "scope": extra["scope"] + "; all original archive checks retained."}
        result["failed_stage"] = "formal_case"
        result["formal_case"] = baseline._formal_case(module, project, idea)
        result.update(status="passed", failed_stage=None)
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=shared._safe_error(exc, project)[:600],
                      traceback=shared._safe_error(traceback.format_exc(limit=5), project)[-3000:])
    shared._write(Path(out), result)


def main(argv=None):
    parser = argparse.ArgumentParser(description="增补最近参考距离验收；不调用模型")
    parser.add_argument("--child", choices=[IDEA], required=True)
    for name in ("project", "source", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    _child(args.child, args.project, args.source, args.out)


if __name__ == "__main__":
    main()
