"""Read verified runtime Events into a portable model dataset, never a journal.

The original Snapshot identity remains a receipt naming its original scope.
Portable values are not inserted into another store under an invented scope.
"""
from copy import deepcopy
import numpy as np
from blackbase.context import SnapshotIdentity
from blackbase.context.snapshot_store import snapshot_content_digest
from blackbase.types import CandidateBatch
from ...core.evaluation_feedback import OptimizationFeedbackBatch
from ...core.solver_helpers.snapshot_helpers import validate_evaluation_event_snapshot


def require_unintercepted_problem(control):
    """Conservative supported scope until dispatch carries per-row truth receipts.

    individual_fallback only names batch routing: it can still invoke an
    individual Provider. Refuse all registered Providers and evaluation-deciding
    Plugins, rather than certify that routing label as true observation origin.
    """
    providers = tuple(control.evaluation_mediator.list_providers())
    deciding = [plugin.name for plugin in control.plugin_manager.list_plugins(enabled_only=True)
                if "evaluation" in tuple(getattr(getattr(plugin, "participation", None), "decides", ()))]
    if providers or deciding:
        raise ValueError("BO direct Problem policy does not support EvaluationProvider or evaluation-deciding Plugin interception")


def unpack_evidence(value, owner):
    if value.get("schema") != "nsgablack.bo_dataset_evidence/v1":
        raise ValueError("unsupported BO dataset evidence schema")
    identity = SnapshotIdentity.from_dict(value["event_ref"])
    digest = snapshot_content_digest(identity.schema, value["snapshot_data"], digest_codec=identity.digest_codec)
    if digest != identity.content_digest:
        raise ValueError("BO portable Event content digest mismatch")
    if value.get("source_policy") != "unintercepted_problem/v1":
        raise ValueError("BO portable dataset lacks the direct Problem source policy receipt")
    event, _ = validate_evaluation_event_snapshot(value["snapshot_data"],
        snapshot_schema=identity.schema, expected_event_id=value["event_id"],
        expected_run_id=value["run_id"], expected_snapshot_key=identity.key)
    if not event.semantic_complete:
        raise ValueError("BO requires complete evaluation evidence")
    candidates = CandidateBatch.from_dict(event.candidate_payload)
    feedback = OptimizationFeedbackBatch.from_dict(event.feedback_payload)
    if feedback.candidate_count != len(candidates.semantic_states):
        raise ValueError("BO Event candidates/feedback counts differ")
    selected = [i for i, state in enumerate(candidates.semantic_states)
                if tuple(state.metadata.get("bo_owner", ())) == tuple(owner)]
    if not selected:
        return []
    # raw describes the Bias view, not truth. Only direct Problem evaluation is
    # admitted in this first version; ambiguous/approximate Providers decline.
    if feedback.metadata.get("evaluation_path") != "individual_fallback":
        raise ValueError("BO true observation policy requires direct Problem evaluation")
    raw = feedback.raw_objectives
    if raw.shape[1] != 1:
        raise ValueError("synchronous BO currently requires one raw objective")
    rows = []
    for i in selected:
        if not np.isfinite(raw[i]).all() or not np.isfinite(candidates.numeric_matrix[i]).all():
            raise ValueError("BO observations must be finite")
        state = candidates.semantic_states[i]
        rows.append({"identity": [value["run_id"], event.event_id, i],
            "candidate_token": candidates.candidate_tokens[i],
            "event_ref": identity.as_dict(), "x": candidates.numeric_matrix[i].tolist(),
            "y": float(raw[i, 0]), "violation": float(feedback.raw_violations[i]),
            "seed_index": state.metadata.get("bo_seed_index")})
    return rows


def collect_evidence(control, owner, known=()):
    """Read-only collection. Deferred Events are retried, never cursor-skipped."""
    known = set(known)
    collected = []
    run_id = control.run_session.run_id
    records = control.evaluation_evidence_journal.list_records(run_id=run_id)
    if not records:
        return collected
    require_unintercepted_problem(control)
    for record in records:
        if (record.run_id, record.event_id) in known:
            continue
        inspection = control.inspect_event(record, control.snapshot_store)
        if inspection.state == "deferred":
            continue
        if inspection.state != "verified":
            raise ValueError(f"BO cannot consume invalid Event: {inspection.reason}")
        source = control.snapshot_store.read_verified(inspection.event_ref)
        value = {"schema": "nsgablack.bo_dataset_evidence/v1", "run_id": record.run_id,
                 "event_id": record.event_id, "event_ref": inspection.event_ref.as_dict(),
                 "source_policy": "unintercepted_problem/v1",
                 "snapshot_data": deepcopy(dict(source.data))}
        if unpack_evidence(value, owner):
            collected.append(value)
    return collected
