"""Stage repairs and validate one final candidate/Unit version before evaluation."""
from __future__ import annotations

import hashlib
import inspect
import json
import numpy as np

from blackbase.representation import representation_capabilities
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, UnknownState
from blackbase.runtime import capture_runtime_snapshot, runtime_participants
from ..adapters.proposal_repair import ProposalRepair
from ..representation.repair_contracts import (JointRepairPolicy, JointRepairRejected,
    validate_repair_component, validate_admission_fields)
from ..utils.extension_contracts import normalize_candidate_batch
from ..units.contracts import UnitBinding


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def candidate_revision(batch):
    return _digest({"states": [state.as_dict() for state in batch.semantic_states],
                    "matrix": batch.numeric_matrix.tolist(), "tokens": batch.candidate_tokens})


def _boolean(value):
    if not isinstance(value, (bool, np.bool_)):
        raise TypeError("repair validators must return bool")
    return bool(value)


def repair_problem_batch(control, batch, contexts, provenance):
    pipeline = control.representation_pipeline
    caps = representation_capabilities(pipeline)
    if not caps.supports("repair"):
        return batch
    candidates, _ = control.bind_candidate_batch(batch, provenance, activate=False)
    use_batch = caps.supports("repair_batch")
    if use_batch:
        try:
            inspect.signature(pipeline.repair_batch).bind(candidates, contexts=contexts)
        except (TypeError, ValueError):
            use_batch = False
    repaired = list(pipeline.repair_batch(candidates, contexts=contexts) if use_batch else
                    [control.repair_candidate(value, contexts[i]) for i, value in enumerate(candidates)])
    if len(repaired) != len(batch.semantic_states):
        raise ValueError("Representation repair must preserve candidate count")
    values = [value if isinstance(value, UnknownState) else batch.semantic_states[i].with_values(value)
              for i, value in enumerate(repaired)]
    result = normalize_candidate_batch(values, dimension=control.dimension, owner="problem_repair",
                                       candidate_tokens=batch.candidate_tokens)
    ProposalRepair(len(values), tuple(range(len(values))), batch, result)
    return result


def inspect_joint_repair_contracts(control, participants):
    issues = []
    policy = getattr(control, "joint_repair_policy", None)
    if policy is not None:
        if not isinstance(policy, JointRepairPolicy):
            issues.append(("joint-repair-contract-invalid", "joint_repair_policy must be JointRepairPolicy"))
        try:
            validate_repair_component(getattr(control.representation_pipeline, "problem_repair", None))
        except (TypeError, ValueError) as exc:
            issues.append(("joint-repair-contract-invalid", str(exc)))
    for owner in participants:
        component = getattr(owner, "unit_repair", None)
        if component is None:
            continue
        try:
            if policy is None:
                raise TypeError("UnitRepair requires JointRepairPolicy and a ProblemRepair validator")
            validate_repair_component(component, unit=True)
            if (tuple(owner.step_transaction_children()) or not hasattr(owner, "algorithm_unit")
                    or not isinstance(getattr(owner, "unit_binding", None), UnitBinding)):
                raise TypeError("UnitRepair requires a leaf algorithm_unit and UnitBinding")
            owner.unit_binding.validate(owner.algorithm_unit)
            validate_admission_fields(owner)
        except (TypeError, ValueError) as exc:
            issues.append(("joint-repair-contract-invalid", f"{owner.name}: {exc}"))
    return issues


def _targets(adapter, evidence, context):
    targets = tuple(adapter.proposal_repair_targets(evidence, context))
    expected = set(evidence.after.candidate_tokens)
    seen = set()
    owners = set()
    for owner, local, _ in targets:
        tokens = set(local.after.candidate_tokens)
        if tokens & seen or not tokens <= expected:
            raise ValueError("repair routing duplicates or invents candidate ownership")
        if tokens and id(owner) in owners:
            raise ValueError("one repair owner cannot occupy multiple proposal targets")
        owners.add(id(owner))
        seen.update(tokens)
    if seen != expected:
        raise ValueError("repair routing dropped candidate ownership")
    return targets


def _validate_problem(control, component, batch, contexts):
    revision = candidate_revision(batch)
    results = []
    for i, state in enumerate(batch.semantic_states):
        control.checkpoint_case_runtime()
        value = state.with_values(state.values)
        initial = _digest(value.as_dict())
        results.append(_boolean(component.validate(value, dict(contexts[i]))))
        if _digest(value.as_dict()) != initial:
            raise ValueError("ProblemRepair.validate modified its candidate input")
    if candidate_revision(batch) != revision:
        raise ValueError("ProblemRepair.validate modified its candidate input")
    control.checkpoint_case_runtime()
    return tuple(results)


def _validate_unit(owner, unit, evidence, context):
    original = _digest(owner.unit_binding.dump(unit))
    revision = candidate_revision(evidence.after)
    validation_unit = owner.unit_binding.restore(owner.unit_binding.dump(unit))
    validation_evidence = ProposalRepair(evidence.proposed_count, evidence.proposal_indices,
                                        evidence.before.subset(slice(None)), evidence.after.subset(slice(None)))
    before_revision = candidate_revision(validation_evidence.before)
    result = _boolean(owner.unit_repair.validate(validation_unit, validation_evidence, dict(context)))
    if (_digest(owner.unit_binding.dump(unit)) != original
            or _digest(owner.unit_binding.dump(validation_unit)) != original
            or candidate_revision(evidence.after) != revision
            or candidate_revision(validation_evidence.after) != revision
            or candidate_revision(validation_evidence.before) != before_revision):
        raise ValueError("UnitRepair.validate must not modify the Unit or candidate")
    return result


def _owner_paths(adapter):
    paths = {}
    def visit(owner, path):
        if id(owner) in paths:
            raise ValueError("joint repair requires unique Adapter ownership")
        paths[id(owner)] = path
        for index, child in enumerate(owner.step_transaction_children()):
            visit(child, f"{path}/{index}:{child.name}")
    visit(adapter, adapter.name)
    return paths


def _install_unit(owner, payload):
    owner.algorithm_unit = owner.unit_binding.restore(payload)
    refresh = getattr(owner, "_after_unit_restore", None)
    if callable(refresh):
        refresh()


class RepairBaseline:
    """Local participant state after propose, before any repair/reconciliation."""
    def __init__(self, control, original, proposed_count, context):
        self.paths = _owner_paths(control.adapter)
        evidence = ProposalRepair(proposed_count, tuple(range(len(original.semantic_states))), original, original)
        targets = _targets(control.adapter, evidence, context)
        self.units = {id(owner): owner.unit_binding.dump(owner.algorithm_unit)
                      for owner, local, _ in targets if local.proposal_indices
                      and isinstance(getattr(owner, "unit_binding", None), UnitBinding)
                      and hasattr(owner, "algorithm_unit")}
        self.entries = []
        for owner in runtime_participants((control.adapter,)):
            path = self.paths[id(owner)]
            tokens = {token for leaf, local, _ in targets
                      if self.paths[id(leaf)] == path or self.paths[id(leaf)].startswith(path + "/")
                      for token in local.after.candidate_tokens}
            if tokens:
                self.entries.append((owner, capture_runtime_snapshot(owner), tokens))

    def restore_rejected(self, accepted_tokens):
        # Restore local snapshots once, children first. Ordinary disposition
        # still runs afterwards to clear/filter the original pending slots.
        for owner, snapshot, tokens in reversed(self.entries):
            if not tokens.intersection(accepted_tokens):
                owner.restore_step_state(snapshot)


class PendingUnitAdmission:
    """Attempt-local repair state, settled around disposition and before update.

    The enclosing Adapter transaction still handles exceptions. This object
    handles normal zero/partial admission, which is not an exception rollback.
    No callbacks are replayed to reconstruct a partially admitted Unit.
    """

    def __init__(self, control, evidence, targets, baseline, report):
        self.control, self.evidence, self.report = control, evidence, report
        self.baseline = baseline
        self.rows = [(owner, local, dict(ctx), baseline.units[id(owner)], baseline.paths[id(owner)])
                     for owner, local, ctx in targets if id(owner) in baseline.units]
        self.accepted = []

    def settle(self, disposition):
        if disposition.proposed_count != self.evidence.proposed_count:
            raise ValueError("joint repair admission must address original proposals")
        accepted_indices = set(disposition.accepted_indices)
        accepted_tokens = {token for index, token in zip(self.evidence.proposal_indices,
                                                        self.evidence.after.candidate_tokens)
                           if index in accepted_indices}
        self.baseline.restore_rejected(accepted_tokens)
        audit = []
        for owner, local, ctx, original, path in self.rows:
            self.control.checkpoint_case_runtime()
            selected = tuple(i for i, token in enumerate(local.after.candidate_tokens) if token in accepted_tokens)
            accepted = ProposalRepair(local.proposed_count, tuple(local.proposal_indices[i] for i in selected),
                                      local.before.subset(selected), local.after.subset(selected))
            partial = bool(selected) and len(selected) != len(local.proposal_indices)
            if partial and owner.unit_repair is not None:
                project = getattr(owner.unit_repair, "project_admission", None)
                if not callable(project):
                    raise TypeError(f"{path}: partial UnitRepair admission requires project_admission()")
            if selected:
                self.accepted.append((owner, accepted, ctx, local, original, partial,
                                      BatchDisposition(local.proposed_count, accepted.proposal_indices,
                                                       reason=disposition.reason)))
            audit.append({"owner_path": path, "accepted_indices": list(accepted.proposal_indices),
                          "candidate_tokens": list(accepted.after.candidate_tokens),
                          "unit_revision": _digest(owner.unit_binding.dump(owner.algorithm_unit))})
        self.report["admission"] = audit

    def validate_after_disposition(self):
        for owner, _, _, original, _ in self.rows:
            if owner.algorithm_unit.unit_id != owner.unit_binding.restore(original).unit_id:
                raise ValueError("UnitRepair disposition must preserve Unit identity")
        for owner, evidence, ctx, local, original, partial, disposition in self.accepted:
            self.control.checkpoint_case_runtime()
            if partial and owner.unit_repair is not None:
                # Adapter has already compacted its pending coordinates once.
                # The component projects effects onto that admitted structure.
                from ..representation.structure_builders import encode_unit_value
                fields = tuple(getattr(owner, "admission_unit_fields", ()))
                pending = _digest({name: encode_unit_value(getattr(owner.algorithm_unit, name)) for name in fields})
                projected = owner.unit_repair.project_admission(owner.unit_binding.restore(original),
                    owner.unit_binding.restore(owner.unit_binding.dump(owner.algorithm_unit)),
                    ProposalRepair(local.proposed_count, local.proposal_indices,
                                   local.before.subset(slice(None)), local.after.subset(slice(None))),
                    disposition, dict(ctx))
                owner.unit_binding.validate(projected)
                if projected.unit_id != owner.algorithm_unit.unit_id:
                    raise ValueError("UnitRepair admission must preserve Unit identity")
                if pending != _digest({name: encode_unit_value(getattr(projected, name)) for name in fields}):
                    raise ValueError("UnitRepair projection changed Adapter-owned admitted coordinates")
                _install_unit(owner, owner.unit_binding.dump(projected))
            if owner.unit_repair is not None and not _validate_unit(owner, owner.algorithm_unit, evidence, ctx):
                raise ValueError("UnitRepair admission/disposition invalidated the accepted Unit")
        by_path = {path: owner for owner, _, _, _, path in self.rows}
        for row in self.report["admission"]:
            owner = by_path[row["owner_path"]]
            row["unit_revision"] = _digest(owner.unit_binding.dump(owner.algorithm_unit))
        self.control.checkpoint_case_runtime()


def coordinate_joint_repair(control, original, proposed_count, context, contexts, provenance, baseline):
    """Bounded draft-only rounds; owner reconciliation runs once on a valid pair.

    Failed rounds discard Unit drafts. Existing Adapter pending state is changed
    only after both validators pass, inside the enclosing step transaction.
    """
    adapter, policy = control.adapter, control.joint_repair_policy
    problem_repair = control.representation_pipeline.problem_repair
    indices = tuple(range(len(original.semantic_states)))
    current = original
    report = {"proposed_count": proposed_count, "rounds": 0, "status": "rejected"}
    paths = _owner_paths(adapter)
    global_indices = dict(zip(original.candidate_tokens, indices))
    def failure(owner, local, reason, tokens=None):
        tokens = set(local.after.candidate_tokens if tokens is None else tokens)
        pairs = [(index, token) for index, token in zip(local.proposal_indices, local.after.candidate_tokens)
                 if token in tokens]
        return {"owner_path": paths[id(owner)], "reason": reason,
                "unit_id": getattr(getattr(owner, "algorithm_unit", None), "unit_id", None),
                "proposal_indices": [i for i, _ in pairs],
                "root_proposal_indices": [global_indices[t] for _, t in pairs],
                "candidate_tokens": [t for _, t in pairs]}
    seen_versions = set()
    for round_index in range(1, policy.max_rounds + 1):
        control.checkpoint_case_runtime()
        after_problem = repair_problem_batch(control, current, contexts, provenance)
        evidence = ProposalRepair(proposed_count, indices, original, after_problem)
        targets = _targets(adapter, evidence, context)
        outputs = dict(zip(after_problem.candidate_tokens, after_problem.semantic_states))
        staged = {}
        originals = {}
        for owner, local, ctx in targets:
            control.checkpoint_case_runtime()
            if owner.unit_repair is None or not local.proposal_indices:
                continue
            # Explicit data codec, never deepcopy an Adapter or a Provider graph.
            originals[id(owner)] = owner.unit_binding.dump(owner.algorithm_unit)
            draft = owner.unit_binding.restore(originals[id(owner)])
            unit_id = draft.unit_id
            before_revision = (candidate_revision(local.before), candidate_revision(local.after))
            result = owner.unit_repair.repair(draft, local, dict(ctx))
            if (candidate_revision(local.before), candidate_revision(local.after)) != before_revision:
                raise ValueError("UnitRepair must return a new candidate batch, not mutate input evidence")
            ProposalRepair(local.proposed_count, local.proposal_indices, local.after, result)
            if draft.unit_id != unit_id:
                raise ValueError("UnitRepair must preserve Unit identity")
            owner.unit_binding.validate(draft)
            staged[id(owner)] = draft
            outputs.update(zip(result.candidate_tokens, result.semantic_states))
        final = CandidateBatch.from_candidates([outputs[token] for token in original.candidate_tokens],
                                                candidate_tokens=original.candidate_tokens)
        final_evidence = ProposalRepair(proposed_count, indices, original, final)
        final_targets = _targets(adapter, final_evidence, context)
        if [(id(owner), local.after.candidate_tokens) for owner, local, _ in targets] != [
                (id(owner), local.after.candidate_tokens) for owner, local, _ in final_targets]:
            raise ValueError("UnitRepair changed proposal ownership")
        problem_results = _validate_problem(control, problem_repair, final, contexts)
        problem_ok = all(problem_results)
        invalid_tokens = {token for token, valid in zip(final.candidate_tokens, problem_results) if not valid}
        failures = []
        unit_ok = True
        for owner, local, ctx in final_targets:
            control.checkpoint_case_runtime()
            if invalid_tokens.intersection(local.after.candidate_tokens):
                failures.append(failure(owner, local, "problem_invalid", invalid_tokens))
            if id(owner) in staged:
                valid = _validate_unit(owner, staged[id(owner)], local, ctx)
                if not valid:
                    failures.append(failure(owner, local, "unit_invalid"))
                unit_ok = valid and unit_ok
        report.update(rounds=round_index, problem_valid=problem_ok, unit_valid=unit_ok,
                      candidate_revision=candidate_revision(final), failures=failures)
        control.checkpoint_case_runtime()
        if problem_ok and unit_ok:
            for owner, _, _ in final_targets:
                if id(owner) in staged:
                    # Re-clone so retained component references cannot mutate the adopted Unit.
                    _install_unit(owner, owner.unit_binding.dump(staged[id(owner)]))
            adapter.on_proposal_repair(control, final_evidence, context)
            if candidate_revision(final) != report["candidate_revision"]:
                raise ValueError("owner reconciliation changed the jointly validated candidate")
            reconciled_targets = _targets(adapter, final_evidence, context)
            def routing_identity(values):
                return tuple((id(owner), local.proposal_indices, local.after.candidate_tokens)
                             for owner, local, _ in values)
            if routing_identity(reconciled_targets) != routing_identity(final_targets):
                raise ValueError("owner reconciliation changed proposal repair ownership")
            revisions = {}
            for owner, local, ctx in reconciled_targets:
                control.checkpoint_case_runtime()
                if id(owner) in staged:
                    if owner.algorithm_unit.unit_id != staged[id(owner)].unit_id:
                        raise ValueError("UnitRepair reconciliation must preserve Unit identity")
                    if not _validate_unit(owner, owner.algorithm_unit, local, ctx):
                        report.update(reason="owner_reconciliation_invalid", unit_valid=False,
                                      failures=[failure(owner, local, "owner_reconciliation_invalid")])
                        raise JointRepairRejected(report)
                if hasattr(owner, "algorithm_unit") and local.proposal_indices:
                    revisions[paths[id(owner)]] = _digest(owner.unit_binding.dump(owner.algorithm_unit))
            report.update(status="verified", reason="joint_repair_validated", unit_revisions=revisions)
            control.checkpoint_case_runtime()
            return final, report, PendingUnitAdmission(control, final_evidence, reconciled_targets, baseline, report)
        version = _digest({"candidate": report["candidate_revision"],
                           "units": [owner.unit_binding.dump(staged[id(owner)])
                                     for owner, _, _ in final_targets if id(owner) in staged]})
        if version in seen_versions:
            report["reason"] = "repair_cycle"
            raise JointRepairRejected(report)
        seen_versions.add(version)
        current = final
    report["reason"] = "repair_round_limit"
    raise JointRepairRejected(report)


__all__ = ["coordinate_joint_repair", "inspect_joint_repair_contracts"]
