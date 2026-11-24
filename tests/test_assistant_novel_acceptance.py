"""Private references; never included in model packets or interface tools."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nsgablack.catalog import assistant_novel_acceptance as acceptance
from nsgablack.catalog import assistant_closed_loop_acceptance as shared


REFLECTION = '''import numpy as np
from nsgablack.adapters import NSGA2Adapter, ChangeResult, ChangeBatchResult
from nsgablack.representation import UniformInitializer

def center_reflection_change(request, *, rng):
    if request.max_outputs == 0:
        return ChangeBatchResult(())
    x = request.parents
    if len(x) < 2 or len(request.source_refs) != len(x) or not np.isfinite(x).all():
        raise ValueError("finite referenced parent rows required")
    center = np.mean(x[:-1], axis=0)
    candidates = (np.clip(2*center-x[-1], -4., 4.), np.clip(3*center-2*x[-1], -4., 4.))
    count = 1 if request.max_outputs == 1 else 2
    return ChangeBatchResult(tuple(ChangeResult(row, source_refs=request.source_refs) for row in candidates[:count]))

def build_adapter():
    adapter = NSGA2Adapter(population_size=4, offspring_size=3)
    adapter.set_initializer(UniformInitializer(-4., 4.))
    adapter.set_change(center_reflection_change)
    return adapter
'''


ARCHIVE = '''import numpy as np
from functools import partial
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import UniformInitializer

def archive_maximin(pool, *, count, archive_values, rng=None):
    if type(count) is not int or not 0 <= count <= len(pool):
        raise ValueError("count out of range")
    if count == 0:
        return pool.take(())
    x = pool.values
    f, v = pool.selection_feedback()
    reference = np.asarray(archive_values, dtype=float)
    if reference.size == 0:
        reference = np.empty((0, x.shape[1]))
    if reference.ndim != 2 or reference.shape[1] != x.shape[1] or not np.isfinite(reference).all():
        raise ValueError("invalid archive")
    selected = []
    remaining = list(range(len(pool)))
    for step in range(count):
        if len(reference):
            distances = np.min(np.sum((x[:, None, :] - reference[None, :, :])**2, axis=2), axis=1)
        else:
            distances = np.full(len(pool), np.inf)
        chosen = min(remaining, key=lambda i: (v[i] > 0., 0. if v[i] <= 0. else float(v[i]),
                     -float(distances[i]), float(f[i, 0]), i))
        selected.append(chosen)
        remaining.remove(chosen)
        reference = np.concatenate((reference, x[chosen:chosen+1]), axis=0)
    return pool.take(selected)

def build_adapter(*, archive_values):
    adapter = NSGA2Adapter(population_size=4, offspring_size=3)
    adapter.set_initializer(UniformInitializer(-4., 4.))
    adapter.set_selector(partial(archive_maximin, archive_values=archive_values))
    return adapter
'''


AGE = '''import numpy as np
from dataclasses import dataclass, field
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import PopulationUnitBuilder, UniformInitializer
from nsgablack.units import PopulationUnit, UnitBinding, UnitSchema

@dataclass
class AgePopulationUnit(PopulationUnit):
    age: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    member_fields = ("age",)
    schema = UnitSchema("novel.age_population", version=1,
        required_fields=(*PopulationUnit.schema.required_fields, "age"), candidate_projection=False)

    def on_members_changed(self, change):
        increase = int(change.operation == "selection")
        return {"age": np.asarray([0 if i is None else int(self.age[i]) + increase
                                  for i in change.previous_member_indices], dtype=int)}

    def validate(self):
        super().validate()
        if self.age.ndim != 1 or self.age.dtype.kind not in "iu" or (self.age < 0).any():
            raise ValueError("invalid ages")

class AgePopulationBuilder(PopulationUnitBuilder):
    unit_type = AgePopulationUnit
    compatible_schemas = (PopulationUnit.schema,)

def build_adapter():
    adapter = NSGA2Adapter(population_size=4, offspring_size=3, unit_binding=UnitBinding(AgePopulationBuilder()))
    adapter.set_initializer(UniformInitializer(-4., 4.))
    return adapter
'''


def proposal(source):
    digest = shared.source_digest(source)
    return {"source": source, "path": acceptance.TARGET, "code_sha256": digest,
            "check": {"status": "needs_runtime_validation", "code_sha256": digest}}


@pytest.mark.parametrize("idea,source,checks", [
    (acceptance.IDEAS[0]["id"], REFLECTION, 20),
    (acceptance.IDEAS[1]["id"], ARCHIVE, 30),
    (acceptance.IDEAS[2]["id"], AGE, 12),
])
def test_frozen_reference_passes_real_behavior_and_canonical_l0_case(idea, source, checks):
    result = acceptance.execute_candidate(proposal(source), idea)
    assert result["status"] == "passed", result
    assert result["behavior"]["checks"] == checks
    assert result["formal_case"]["committed_steps"] == 2
    assert result["formal_case"]["evaluations"] == 7 and result["formal_case"]["members"] == 4
    assert result["formal_case"]["component_invocations"] >= 1
    assert result["executed_source_sha256"] == hashlib.sha256(source.encode()).hexdigest()
    assert result["validation_identity"] == acceptance.spec_identity()
    assert len(json.dumps(result, ensure_ascii=False).encode()) < 8192
    if idea == acceptance.IDEAS[2]["id"]:
        assert result["partial_acceptance"]["committed_steps"] == 2
        assert result["failed_step_rollback"]["committed_steps"] == 1
        assert result["failed_step_rollback"]["evaluations"] == 7


def test_reflection_cannot_reverse_the_order_or_silently_drop_expansion():
    source = REFLECTION.replace('candidates[:count]', 'tuple(reversed(candidates[:count]))')
    result = acceptance.execute_candidate(proposal(source), acceptance.IDEAS[0]["id"])
    assert result["status"] == "failed" and result["failed_stage"] == "behavior"


def test_archive_must_recompute_distances_after_every_selection():
    source = ARCHIVE.replace('reference = np.concatenate((reference, x[chosen:chosen+1]), axis=0)', 'pass')
    result = acceptance.execute_candidate(proposal(source), acceptance.IDEAS[1]["id"])
    assert result["status"] == "failed" and result["failed_stage"] == "behavior"


def test_age_must_not_increment_untouched_members_on_replacement():
    source = AGE.replace('int(change.operation == "selection")', '1')
    result = acceptance.execute_candidate(proposal(source), acceptance.IDEAS[2]["id"])
    assert result["status"] == "failed" and result["failed_stage"] == "behavior"


def test_novel_units_policy_is_private_and_does_not_mutate_original_guard():
    old_profile = shared.spec_identity()
    old_namespaces = shared.review_execution_source.__globals__["EXECUTION_ALLOWED_NAMESPACES"]
    acceptance.review_candidate_source(AGE)
    assert "nsgablack.units" not in old_namespaces
    assert shared.review_execution_source.__globals__["EXECUTION_ALLOWED_NAMESPACES"] == old_namespaces
    assert shared.spec_identity() == old_profile
    with pytest.raises(ValueError, match="import_review_failed"):
        acceptance.review_candidate_source("import os")
    with pytest.raises(ValueError, match="imported_object_write"):
        acceptance.review_candidate_source("from nsgablack.units import PopulationUnit\nPopulationUnit.schema = None")


def test_fresh_host_spec_reuses_loop_and_keeps_private_values_out_of_initial_packet():
    calls = 0
    source = "def center_reflection_change(request, *, rng): return None\n"
    def complete(owner, messages, tools):
        nonlocal calls
        calls += 1
        if calls == 1:
            initial = json.loads(messages[1]["content"])
            assert len(messages) == 2 and initial["project_id"]
            assert "novel-reflection-" not in json.dumps(messages)
            return {"model": "same-fake-model", "message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": "fresh-check", "type": "function", "function": {"name": "check_project_edit", "arguments": json.dumps({
                    "path": acceptance.TARGET, "source": source})}}]}}
        output = json.loads(messages[-1]["content"])
        return {"model": "same-fake-model", "message": {"role": "assistant", "content": json.dumps({
            "explanation": "fresh host profile checked", "questions": [], "proposal_digest": None,
            "edit_digest": output["edit_digest"]})}}
    def execute(data, idea):
        return {"status": "passed", "executed": True, "code_sha256": data["code_sha256"],
            "executed_source_sha256": data["code_sha256"], "validation_identity": acceptance.spec_identity()}
    report = acceptance.run_novel_acceptance(object(), complete=complete, executor=execute,
        allow_code_execution=True, case_ids=[acceptance.IDEAS[0]["id"]], maximum_requests=36)
    assert report["summary"]["passed"] == 1, report["cases"][0].get("error")
    assert report["maximum_http_requests"] == 36 and report["model_calls_per_task"] == 14
    assert report["acceptance_profile"] == "three_fresh_components/v1"
    assert report["oracle_math_sha256"] == acceptance.oracle_math_sha256()
    assert report["summary"]["model_request_attempts"] == 2


def test_stdin_validation_uses_exact_source_bytes_and_no_shell_interpolation():
    run = subprocess.run([sys.executable, "-m", "nsgablack.catalog.assistant_novel_acceptance", "--validate", acceptance.IDEAS[0]["id"]],
        input=json.dumps(proposal(REFLECTION)), capture_output=True, text=True, encoding="utf-8", timeout=90)
    result = json.loads(run.stdout)
    assert run.returncode == 0 and result["status"] == "passed", result
    assert result["executed_source_sha256"] == shared.source_digest(REFLECTION)


def test_default_old_mathematical_oracle_is_unchanged():
    assert shared.oracle_math_sha256() == "1cde4d9e753392b98c913df8f908884c617f2831ed6fc6bb80dfadb62aa4ff25"
    with pytest.raises(ValueError, match="request_budget_invalid"):
        shared.run_closed_loop(object(), maximum_requests=36, allow_code_execution=True)
