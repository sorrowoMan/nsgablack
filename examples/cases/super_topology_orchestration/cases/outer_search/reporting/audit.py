"""Derive topology claims from recorded runtime facts; missing facts fail closed."""

from __future__ import annotations

import hashlib
import math


def _child_identity(parent, child):
    return bool(
        parent["case_run_id"]
        and child["case_run_id"] != parent["case_run_id"]
        and child["case_run_id"]
        and child["parent_case_run_id"] == parent["case_run_id"]
        and child["root_run_id"] == parent["root_run_id"]
        and child["project_run_id"] == parent["project_run_id"]
        and child["depth"] == parent["depth"] + 1
    )


def _bounded_grant(parent, child):
    return (
        all(
            math.isfinite(float(child[key])) and 0 <= child[key] <= parent[key]
            for key in ("workers", "threads", "gpus", "memory_mb")
        )
        and child["workers"] > 0 and child["threads"] > 0
        and child["backend"] == parent["backend"]
        and set(child["device_tokens"]).issubset(parent["device_tokens"])
    )


def _resource_child(parent, child):
    return bool(
        parent["namespace"] and parent["lease_id"]
        and child["namespace"].startswith(parent["namespace"] + ".")
        and child["lease_id"] == parent["lease_id"] == child["parent_lease_id"]
        and child["fencing_token"] == parent["fencing_token"]
        and child["grant_id"]
    )


def _settled(usage):
    budget = usage["evaluations"]
    return bool(
        budget["handle_id"]
        and budget["settlement_status"] == "settled"
        and budget["outstanding_reserved"] == 0
        and all(
            math.isfinite(float(budget[key])) and budget[key] >= 0
            for key in ("limit", "charged_to_parent", "returned_to_parent", "committed")
        )
        and budget["charged_to_parent"] == budget["committed"]
        and budget["limit"] == budget["charged_to_parent"] + budget["returned_to_parent"]
    )


def _child_cancellation(parent, child):
    digest = hashlib.sha256(
        f"{parent['lineage_digest']}:{parent['control_id']}:{child['control_id']}".encode()
    ).hexdigest()
    return bool(
        parent["control_id"] and child["control_id"]
        and parent["control_id"] != child["control_id"]
        and child["parent_control_id"] == parent["control_id"]
        and child["root_control_id"] == parent["root_control_id"]
        and child["lineage_depth"] == parent["lineage_depth"] + 1
        and child["lineage_digest"] == digest
        and all(child[key] == parent[key] for key in ("backend", "namespace", "path"))
        and math.isfinite(float(child["deadline_at"])) and child["deadline_at"] > 0
        and (parent["deadline_at"] == 0 or child["deadline_at"] <= parent["deadline_at"])
    )


def evaluate_invariants(audit):
    """Recomputable checks, deliberately independent of the saved invariants field."""
    calls = audit.get("nested_calls", ())

    def every(predicate):
        return bool(calls) and len(calls) == audit["candidate_trainer_calls"] and all(
            predicate(record, record["inner"]) for record in calls
        )

    checks = {
        "project_dag_dependencies": lambda: all(
            set(audit["dag"][key]) == {"baseline_solver", "baseline_trainer"}
            for key in ("dependencies", "inferred_artifact_dependencies")
        ),
        "artifact_authority_inputs": lambda: all(
            audit["baseline_publications"][name]["verified"] is True
            and audit["baseline_publications"][name]["receipt"]["receipt_digest"]
            and audit["baseline_publications"][name]["receipt"]["ref"] == audit["baseline_inputs"][name]
            for name in ("solver_baseline", "trainer_baseline")
        ),
        "solver_to_trainer": lambda: every(lambda record, inner:
            record["trainer_status"] == "succeeded"
            and _child_identity(audit["outer_identity"], record["trainer_identity"])
            and record["trainer_control_plane"] == "nsgablack.ComposableSolver"
            and record["trainer_committed_steps"] > 0
            and bool(record["trainer_publication_digest"])
        ),
        "trainer_to_solver": lambda: every(lambda record, inner:
            inner["inner_status"] == "succeeded"
            and inner["trainer_identity"] == record["trainer_identity"]
            and _child_identity(record["trainer_identity"], inner["inner_identity"])
        ),
        "resource_lineage": lambda: audit["outer_resource_binding_current"] is True and every(
            lambda record, inner:
            record["trainer_resource_binding_current"] is True
            and inner["inner_resource_binding_current"] is True
            and _bounded_grant(audit["outer_resource_grant"], record["trainer_resource_grant"])
            and _bounded_grant(record["trainer_resource_grant"], inner["inner_resource_grant"])
            and _resource_child(audit["outer_resource_lineage"], record["trainer_resource_lineage"])
            and _resource_child(record["trainer_resource_lineage"], inner["inner_resource_lineage"])
        ),
        "budget_settlement": lambda: every(lambda record, inner:
            _settled(record["trainer_budget_usage"]) and _settled(inner["inner_budget_usage"])
            and record["trainer_evaluation_count"] > 0
            and record["trainer_budget_usage"]["evaluations"]["committed"] == (
                record["trainer_evaluation_count"]
                + inner["inner_budget_usage"]["evaluations"]["charged_to_parent"]
            )
        ),
        "cancellation_deadline_lineage": lambda: every(lambda record, inner:
            _child_cancellation(audit["outer_cancellation"], record["trainer_cancellation"])
            and _child_cancellation(record["trainer_cancellation"], inner["inner_cancellation"])
        ),
    }
    results = {}
    for name, check in checks.items():
        try:
            results[name] = bool(check())
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            results[name] = False
    return results
