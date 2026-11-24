"""Freeze behavioural cases before model calls; no source repairs during grading."""
import hashlib
from copy import deepcopy
import json

import pytest

from nsgablack.catalog.assistant_edit_acceptance import (
    IDEAS, TARGET, execute_proposal, main, review_execution_source, verify_checked_delivery,
    run_edit_acceptance,
    prepare_api_continuation,
)


@pytest.mark.parametrize("symbol", ["UniformInitializer", "blackbase.types.CandidateBatch"])
def test_real_public_api_canonical_module_is_accepted_by_execution_policy(symbol):
    from nsgablack.catalog.lab_api import inspect_framework_api
    api = inspect_framework_api(symbol)
    assert api["status"] == "found"
    module, _, name = api["symbol"].rpartition(".")
    # Query tools and the execution policy must agree about legitimate import
    # paths, including an implementation module under a public namespace.
    review_execution_source(f"from {module} import {name}\n")


def test_rejected_import_identifies_the_actual_module_without_executing_it():
    with pytest.raises(ValueError, match="dev_execution_import_review_failed: pathlib; allowed namespaces:"):
        review_execution_source("from pathlib import Path\n")


PARENTS = '''import numpy as np
from nsgablack.adapters import NSGA2Adapter

class ArchiveDistanceParents:
    stateless = True
    def __init__(self, pool_name="reference_archive"):
        self.pool_name = pool_name
    def checkpoint_identity(self):
        return {"pool_name": self.pool_name, "rule": "rank-crowding-farthest/v1"}
    def select(self, request, *, pool, rng):
        if not pool.has_subpool(self.pool_name):
            raise ValueError("missing archive")
        archive = tuple(pool.subpool_refs(self.pool_name))
        if not archive:
            raise ValueError("empty archive")
        index = int(np.lexsort((np.arange(len(request.population_refs)), -request.crowding, request.rank))[0])
        first = request.population_refs[index]
        x = pool.read((first,)).numeric_matrix[0]
        values = pool.read(archive).numeric_matrix
        distances = np.sum((values - x) ** 2, axis=1)
        second = archive[int(np.argmax(distances))]
        return tuple((first, second)[i % 2] for i in range(request.count))

def build_adapter():
    return NSGA2Adapter(population_size=4, offspring_size=3,
                        parent_selector=ArchiveDistanceParents())
'''

CHANGE = '''import numpy as np
from nsgablack.adapters import NSGA2Adapter, ChangeResult, ChangeBatchResult

def bounded_antithetic(request, *, rng):
    count = 2 if request.max_outputs is None else min(2, request.max_outputs)
    if count == 0:
        return ChangeBatchResult(())
    c = np.mean(request.parents[:2], axis=0)
    h = np.minimum(.3, np.minimum(c + 4., 4. - c))
    delta = h * rng.uniform(-1., 1., size=len(c))
    values = (c + delta, c - delta)
    return ChangeBatchResult(tuple(ChangeResult(value, source_refs=request.source_refs)
                                   for value in values[:count]))

def build_adapter():
    return NSGA2Adapter(population_size=4, offspring_size=3, change=bounded_antithetic)
'''


def proposal(source):
    digest = hashlib.sha256(source.encode()).hexdigest()
    return {"path": TARGET, "source": source, "code_sha256": digest,
            "source_digest": "a" * 64, "check": {"status": "needs_runtime_validation", "code_sha256": digest}}


@pytest.mark.parametrize("index,source", [(0, PARENTS), (1, CHANGE)])
def test_trusted_reference_passes_real_type_behaviour_and_formal_case_run(index, source):
    result = execute_proposal(proposal(source), IDEAS[index]["id"])
    assert result["status"] == "passed", result
    assert result["formal_case"]["committed_steps"] == 2
    assert result["formal_case"]["evaluations"] == 7


def test_parent_reference_mutant_fails_preexisting_distance_expectation():
    source = PARENTS.replace("np.argmax(distances)", "np.argmin(distances)")
    result = execute_proposal(proposal(source), IDEAS[0]["id"])
    assert result["status"] == "failed" and result["formal_case"] is None


def test_change_mutant_fails_output_limit_before_smoke_run():
    source = CHANGE.replace("values[:count]", "values")
    result = execute_proposal(proposal(source), IDEAS[1]["id"])
    assert result["status"] == "failed" and result["formal_case"] is None


@pytest.mark.parametrize("source", ["import os\nos.system('anything')", "import numpy as np\nnp.load('x')",
    "import numpy as np\ngetattr(np, 'load')('x')"])
def test_development_guard_rejects_unneeded_process_file_and_reflection_capabilities(source):
    with pytest.raises(ValueError, match="review_failed"):
        review_execution_source(source)


def test_development_guard_accepts_formal_candidate_initializer_import():
    review_execution_source("from nsgablack.representation import UniformInitializer\n"
                            "initializer = UniformInitializer(-4., 4.)\n")


def test_guard_allows_only_public_exports_local_helper_calls_and_literal_candidate_lookup():
    review_execution_source('''__all__ = ["Selector"]
class Selector:
    def _helper(self, record):
        return getattr(record, "candidate", record)
    def select(self, record):
        return self._helper(record)
''')


@pytest.mark.parametrize("source", [
    'def f():\n    __all__ = ["X"]\n',
    '__all__ = ["__builtins__"]\n',
    'getattr(obj, name, None)', 'getattr(obj, "__dict__", None)',
    'lookup = getattr',
    'class S:\n    def f(self): return self._unknown()\n',
    'class S:\n    def _h(self): pass\n    def f(self): return self._h\n',
    'class S:\n    def _h(self): pass\n    def f(self): return other._h()\n',
    'class S:\n    def f(self): return self.__dict__\n'])
def test_guard_still_refuses_dynamic_or_private_object_access(source):
    with pytest.raises(ValueError, match="review_failed"):
        review_execution_source(source)


def test_rejected_or_unbound_bytes_never_execute():
    altered = proposal(PARENTS)
    altered["source"] += "\n# altered bytes"
    with pytest.raises(ValueError, match="unbound_or_rejected"):
        execute_proposal(altered, IDEAS[0]["id"])
    rejected = proposal(PARENTS)
    rejected["check"]["status"] = "rejected"
    with pytest.raises(ValueError, match="unbound_or_rejected"):
        execute_proposal(rejected, IDEAS[0]["id"])


def test_no_implicit_paid_calls_or_execution_flag():
    with pytest.raises(SystemExit):
        main(["--out", "unused.json"])


def test_delivery_requires_last_successful_check_exact_source_and_api_discovery():
    edit = {**proposal(PARENTS), "edit_digest": "selected", "bindings": {}}
    result = {key: value for key, value in edit.items() if key not in ("source", "bindings")}
    check = {"name": "check_project_edit", "ok": True,
        "arguments": {"path": TARGET, "source": PARENTS}, "result": result}
    answer = {"edit_digest": "selected", "edit_proposal": edit,
        "tool_trace": [{"name": "framework_api", "ok": True}, check]}
    assert verify_checked_delivery(answer, source_digest="a" * 64)["status"] == "matched"
    for mutation in ("stale_last", "changed_source", "no_discovery", "wrong_project"):
        changed = deepcopy(answer)
        if mutation == "stale_last":
            changed["tool_trace"].append({"name": "check_project_edit", "ok": True,
                "result": {"check": {"status": "rejected"}}})
        elif mutation == "changed_source":
            changed["edit_proposal"]["source"] += "\n# altered"
        elif mutation == "no_discovery":
            changed["tool_trace"].pop(0)
        else:
            changed["edit_proposal"]["source_digest"] = "b" * 64
        with pytest.raises(ValueError, match="edit_"):
            verify_checked_delivery(changed, source_digest="a" * 64)


def test_followup_is_explicit_selected_and_accumulates_cap_without_private_reasoning():
    calls = []
    def offline(owner, messages, tools):
        calls.append(1)
        return {"model": "offline", "finish_reason": "stop", "message": {
            "content": '{"explanation":"仅讨论","questions":[],"proposal_digest":null}',
            "reasoning_content": "not-for-report"}}
    report = run_edit_acceptance(object(), complete=offline, already_used=8,
        maximum_requests=16, case_ids=[IDEAS[0]["id"]], project_model_calls=6,
        project_tool_calls=24, source_report_sha256="c" * 64)
    assert len(calls) == 1 and report["summary"]["http_requests"] == 9
    assert report["summary"]["new_http_requests"] == 1
    assert report["kind"] == "known_idea_development_followup"
    assert report["cases"][0]["error"] == "concrete_checked_edit_missing"
    assert "reasoning_content" not in repr(report["request_records"])
    assert report["cases"][0]["behaviour"]["status"] == "not_run"


@pytest.mark.parametrize("options", [{"project_model_calls": 7}, {"project_tool_calls": 25},
    {"case_ids": []}, {"case_ids": ["invented"]}, {"already_used": 17}])
def test_invalid_budget_or_case_never_starts_provider(options):
    with pytest.raises(ValueError, match="invalid_"):
        run_edit_acceptance(object(), **options)


def test_continuation_only_preserves_verified_positive_api_facts_and_report_hash(tmp_path):
    from nsgablack.catalog.lab_api import inspect_framework_api
    found = inspect_framework_api("ChangeResult", member="__init__")
    path = tmp_path / "source.raw.json"
    def save(value):
        path.write_text(json.dumps(value), encoding="utf-8")
        return hashlib.sha256(path.read_bytes()).hexdigest()
    raw = {"cases": [{"id": IDEAS[0]["id"], "instruction": "private question not copied",
        "runtime_progress": {"tool_trace": [
            {"name": "framework_api", "ok": True, "arguments": {"symbol": "ChangeResult", "member": "__init__"}, "result": found},
            {"name": "framework_api", "ok": True, "arguments": {"symbol": "Missing"}, "result": {"status": "not_found"}},
            {"name": "project_read", "ok": True, "arguments": {}, "result": {"text": "not an API fact"}}]}}]}
    digest = save(raw)
    evidence = prepare_api_continuation([(path, digest)], IDEAS[0]["id"])
    assert len(evidence["previous_api_evidence"]) == 1
    assert evidence["previous_api_evidence"][0]["member"]["excerpt"]
    assert evidence["provenance"] == [{"report": path.name, "sha256": digest}]
    assert "private question" not in repr(evidence) and "not an API fact" not in repr(evidence)
    with pytest.raises(ValueError, match="report_changed"):
        prepare_api_continuation([(path, "0" * 64)], IDEAS[0]["id"])
    raw["cases"][0]["runtime_progress"]["tool_trace"][0]["result"]["sources"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="api_source_changed"):
        prepare_api_continuation([(path, save(raw))], IDEAS[0]["id"])
