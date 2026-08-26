"""
Composable solver built on SolverBase.

This solver delegates the optimization logic to AlgorithmAdapter instances.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from blackbase.resources import ResourceContext
from blackbase.contracts import BatchDisposition
from blackbase.evaluation import EvaluationDispositionEnvelope
from blackbase.types import CandidateBatch
from blackbase.context import StateStoreConfig, make_snapshot_key
from blackbase.project import attach_failure_evidence

import numpy as np

from ..adapters import (
    AdapterCommitReport,
    AlgorithmAdapter,
    CompositeAdapter,
    PopulationPartition,
)
from .blank_solver import SolverBase
from .evaluation_feedback import OptimizationFeedbackBatch
from blackbase.context.context_keys import (
    KEY_ADAPTER_COMMIT_REPORT_REF,
    KEY_METADATA,
    KEY_SNAPSHOT_KEY,
    KEY_STEP,
)
from .state.incumbent import (
    CandidateProvenance,
    DEFAULT_INCUMBENT_POLICY_ID,
    IncumbentState,
    ScalarizationError,
)
from .state.step_outcome import StepOutcome
from .runtime_governance import commit_population_snapshot
from ..utils.extension_contracts import normalize_candidate_batch, stack_population


def _rollback_step_failure(
    primary_error: BaseException,
    callbacks: Sequence[tuple[str, Callable[[], None]]],
) -> None:
    """Attempt every rollback action without replacing the primary failure."""

    failures: list[tuple[str, BaseException]] = []
    for name, callback in callbacks:
        try:
            callback()
        except BaseException as exc:
            failures.append((str(name), exc))
    if not failures:
        return
    evidence = tuple(
        {
            "participant": name,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        for name, exc in failures
    )
    try:
        setattr(primary_error, "step_rollback_errors", evidence)
    except Exception:
        pass
    try:
        attach_failure_evidence(
            primary_error,
            "nsgablack_step_rollback",
            evidence,
        )
    except Exception:
        pass
    add_note = getattr(primary_error, "add_note", None)
    if callable(add_note):
        add_note(f"secondary step rollback failures: {evidence!r}")


class ComposableSolver(SolverBase):
    """Solver wrapper that executes adapter-driven optimization loops."""

    def __init__(
        self,
        problem,
        adapter: Optional[AlgorithmAdapter] = None,
        evaluation_acceptance_policy: Any = None,
        bias_module=None,
        representation_pipeline=None,
        ignore_constraint_violation_when_bias: bool = False,
        plugin_strict: bool = False,
        snapshot_strict: bool = False,
        resource_context: Optional[Mapping[str, Any] | ResourceContext] = None,
        storage_config: Optional[StateStoreConfig] = None,
        context_store_backend: str = "memory",
        context_store_ttl_seconds: Optional[float] = None,
        context_store_redis_url: str = "redis://localhost:6379/0",
        context_store_key_prefix: str = "nsgablack:context",
        context_store_serializer: str = "safe",
        context_store_hmac_env_var: str = "NSGABLACK_CONTEXT_HMAC_KEY",
        context_store_unsafe_allow_legacy_pickle: bool = False,
        context_store_max_payload_bytes: int = 262_144,
        snapshot_store_backend: str = "memory",
        snapshot_store_ttl_seconds: Optional[float] = None,
        snapshot_store_redis_url: str = "redis://localhost:6379/0",
        snapshot_store_key_prefix: str = "nsgablack:snapshot",
        snapshot_store_dir: Optional[str] = None,
        snapshot_store_serializer: str = "safe",
        snapshot_store_hmac_env_var: str = "NSGABLACK_SNAPSHOT_HMAC_KEY",
        snapshot_store_unsafe_allow_unsigned: bool = False,
        snapshot_store_max_payload_bytes: int = 8_388_608,
        context_inline_candidate_max_bytes: int = 4_096,
        snapshot_schema: str = "nsgablack.population_snapshot/v2",
        enable_convergence_monitor: bool = False,
        convergence_config: Optional[object] = None,
        enable_adaptive_parameters: bool = False,
        adaptive_config: Optional[object] = None,
        enable_companion_orchestrator: bool = False,
        companion_config: Optional[object] = None,
    ) -> None:
        super().__init__(
            problem=problem,
            bias_module=bias_module,
            representation_pipeline=representation_pipeline,
            ignore_constraint_violation_when_bias=ignore_constraint_violation_when_bias,
            plugin_strict=bool(plugin_strict),
            snapshot_strict=bool(snapshot_strict),
            resource_context=resource_context,
            storage_config=storage_config,
            context_store_backend=context_store_backend,
            context_store_ttl_seconds=context_store_ttl_seconds,
            context_store_redis_url=context_store_redis_url,
            context_store_key_prefix=context_store_key_prefix,
            context_store_serializer=context_store_serializer,
            context_store_hmac_env_var=context_store_hmac_env_var,
            context_store_unsafe_allow_legacy_pickle=context_store_unsafe_allow_legacy_pickle,
            context_store_max_payload_bytes=context_store_max_payload_bytes,
            snapshot_store_backend=snapshot_store_backend,
            snapshot_store_ttl_seconds=snapshot_store_ttl_seconds,
            snapshot_store_redis_url=snapshot_store_redis_url,
            snapshot_store_key_prefix=snapshot_store_key_prefix,
            snapshot_store_dir=snapshot_store_dir,
            snapshot_store_serializer=snapshot_store_serializer,
            snapshot_store_hmac_env_var=snapshot_store_hmac_env_var,
            snapshot_store_unsafe_allow_unsigned=snapshot_store_unsafe_allow_unsigned,
            snapshot_store_max_payload_bytes=snapshot_store_max_payload_bytes,
            context_inline_candidate_max_bytes=context_inline_candidate_max_bytes,
            snapshot_schema=snapshot_schema,
            enable_convergence_monitor=bool(enable_convergence_monitor),
            convergence_config=convergence_config,
            enable_adaptive_parameters=bool(enable_adaptive_parameters),
            adaptive_config=adaptive_config,
            enable_companion_orchestrator=bool(enable_companion_orchestrator),
            companion_config=companion_config,
        )
        self.adapter: Optional[AlgorithmAdapter] = adapter
        self.evaluation_acceptance_policy = None
        self.set_evaluation_acceptance_policy(evaluation_acceptance_policy)
        self.last_step_summary: Dict[str, Any] = {}
        self._last_adapter_commit_report: Dict[str, Any] = {}
        self._objective_scalarizer = None
        self.incumbent_scalarizer_id = DEFAULT_INCUMBENT_POLICY_ID
        self.incumbent_scalarizer_context: Dict[str, Any] = {}
        self.scalarizer_failure_policy = "raise"
        self.scalarizer_fallback_count = 0
        self.result_quality_degraded = False
        self.scalarizer_audit_complete = True
        self._candidate_population_partitions: dict[
            str,
            tuple[
                PopulationPartition,
                CandidateBatch,
                tuple[Any, ...],
            ],
        ] = {}
        self.population_authority_mode = "step_batch"

    @property
    def objective_scalarizer(self):
        """Stable pointwise scalarizer used only for run-wide incumbent ranking."""

        return self._objective_scalarizer

    @objective_scalarizer.setter
    def objective_scalarizer(self, scalarizer) -> None:
        with self._incumbent_lock:
            incumbent = self._incumbent_commit.state
            if incumbent is not None:
                if scalarizer is self._objective_scalarizer:
                    return
                raise ScalarizationError(
                    "cannot replace the incumbent scalarizer during an active run",
                    policy_id=self.incumbent_scalarizer_id,
                )
            self._objective_scalarizer = scalarizer
            if scalarizer is None:
                self.incumbent_scalarizer_id = DEFAULT_INCUMBENT_POLICY_ID
                return
            module = str(getattr(scalarizer, "__module__", "unknown"))
            name = str(
                getattr(
                    scalarizer,
                    "__qualname__",
                    getattr(scalarizer, "__name__", type(scalarizer).__name__),
                )
            )
            self.incumbent_scalarizer_id = f"pointwise:{module}.{name}"

    def set_incumbent_scalarizer(
        self,
        scalarizer,
        *,
        policy_id: str,
        context: Optional[Mapping[str, Any]] = None,
        failure_policy: str = "raise",
    ) -> "ComposableSolver":
        """Configure a stable row-wise scoring policy for run-wide incumbents."""

        normalized_policy = str(failure_policy or "raise").strip().lower()
        if normalized_policy not in {"raise", "fallback_sum"}:
            raise ValueError(
                "scalarizer failure_policy must be 'raise' or 'fallback_sum'"
            )
        normalized_id = str(policy_id or "").strip()
        if not normalized_id:
            raise ValueError("incumbent scalarizer policy_id must not be empty")
        normalized_context = dict(context or {})
        with self._incumbent_lock:
            incumbent = self._incumbent_commit.state
            if incumbent is not None:
                unchanged = (
                    scalarizer is self._objective_scalarizer
                    and normalized_id == self.incumbent_scalarizer_id
                    and self._policy_context_signature(normalized_context)
                    == self._policy_context_signature(
                        self.incumbent_scalarizer_context
                    )
                    and normalized_policy == self.scalarizer_failure_policy
                )
                if unchanged:
                    return self
                raise ScalarizationError(
                    "cannot change incumbent selection policy during an active run",
                    policy_id=normalized_id,
                )
            self.objective_scalarizer = scalarizer
            self.incumbent_scalarizer_id = normalized_id
            self.incumbent_scalarizer_context = normalized_context
            self.scalarizer_failure_policy = normalized_policy
        return self

    @classmethod
    def _policy_context_signature(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(
                (str(key), cls._policy_context_signature(item))
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            )
        if isinstance(value, np.ndarray):
            return cls._policy_context_signature(value.tolist())
        if isinstance(value, (list, tuple)):
            return tuple(cls._policy_context_signature(item) for item in value)
        if isinstance(value, np.generic):
            return value.item()
        return value

    def _validate_incumbent_commit(self, state: IncumbentState) -> None:
        super()._validate_incumbent_commit(state)
        expected_policy_id = str(
            getattr(self, "incumbent_scalarizer_id", DEFAULT_INCUMBENT_POLICY_ID)
        )
        if state.policy_id != expected_policy_id:
            raise ScalarizationError(
                "incumbent commit policy does not match the configured scalarizer",
                phase="incumbent_commit",
                policy_id=expected_policy_id,
            )
        expected_context = dict(
            getattr(self, "incumbent_scalarizer_context", {}) or {}
        )
        if self._policy_context_signature(
            state.policy_context
        ) != self._policy_context_signature(expected_context):
            raise ScalarizationError(
                "incumbent commit policy context does not match the configured scalarizer",
                phase="incumbent_commit",
                policy_id=expected_policy_id,
            )

    def set_adapter(self, adapter: AlgorithmAdapter) -> None:
        self.adapter = adapter

    def set_adapters(self, adapters: Sequence[AlgorithmAdapter]) -> None:
        self.adapter = CompositeAdapter(list(adapters))

    def set_evaluation_acceptance_policy(self, policy: Any) -> None:
        """Install a post-evaluation admission policy.

        The policy must return a shared ``BatchDisposition`` so Adapter-owned
        proposal bookkeeping is reconciled before the accepted subset reaches
        ``update``.
        """

        if policy is not None and not callable(getattr(policy, "select", None)):
            raise TypeError(
                "evaluation_acceptance_policy must provide select(candidates, feedback, context)"
            )
        self.evaluation_acceptance_policy = policy

    def setup(self) -> None:
        if self.adapter is not None:
            self.adapter.setup(self)

    def prepare_fresh_run(self) -> None:
        super().prepare_fresh_run()
        self._last_adapter_commit_report = {}
        self._candidate_population_partitions = {}
        self.population_authority_mode = "step_batch"

    def teardown(self) -> None:
        if self.adapter is not None:
            self.adapter.teardown(self)

    def _notify_proposal_disposition(
        self,
        *,
        proposed_count: int,
        accepted_count: int,
        context: Dict[str, Any],
        reason: str,
    ) -> None:
        proposed = int(proposed_count)
        accepted = int(accepted_count)
        if accepted == proposed:
            return
        disposition = BatchDisposition.prefix(
            proposed_count=proposed,
            accepted_count=accepted,
            reason=reason,
            metadata={"control": type(self).__name__},
        )
        if self.adapter is None:
            raise RuntimeError("proposal disposition requires an attached adapter")
        self.adapter.on_proposal_disposition(
            self,
            disposition,
            context,
        )

    @staticmethod
    def _copy_optional_array(value: Any) -> np.ndarray | None:
        return None if value is None else np.array(value, copy=True)

    def _capture_authority_projection(self) -> dict[str, Any]:
        """Capture only population authority, excluding evaluation-event state."""

        return {
            "population": self._copy_optional_array(self.population),
            "objectives": self._copy_optional_array(self.objectives),
            "violations": self._copy_optional_array(self.constraint_violations),
            "candidate_batch": self.get_candidate_population_batch(),
            "candidate_provenance": self.get_candidate_population_provenance(),
            "active_provenance": tuple(self._active_candidate_provenance),
            "partitions": dict(self._candidate_population_partitions),
            "authority_mode": str(self.population_authority_mode),
        }

    def _restore_authority_projection(self, projection: Mapping[str, Any]) -> None:
        """Restore authority after a rejected or failed acceptance decision."""

        self.population = self._copy_optional_array(projection.get("population"))
        self.objectives = self._copy_optional_array(projection.get("objectives"))
        self.constraint_violations = self._copy_optional_array(
            projection.get("violations")
        )
        self._candidate_population_batch = projection.get("candidate_batch")
        self._candidate_population_provenance = tuple(
            projection.get("candidate_provenance", ()) or ()
        )
        self._active_candidate_provenance = list(
            projection.get("active_provenance", ()) or ()
        )
        self._candidate_population_partitions = dict(
            projection.get("partitions", {}) or {}
        )
        self.population_authority_mode = str(
            projection.get("authority_mode", "step_batch") or "step_batch"
        )
        self._active_candidate_population_ref = None
        if self.population is not None and self._active_candidate_provenance:
            self.activate_candidate_provenance(
                self.population,
                self._active_candidate_provenance,
            )

    def step(self) -> StepOutcome:
        if self.adapter is None:
            return self._step_transaction_body()
        previous_projection = self._capture_authority_projection()
        previous_incumbent = self._capture_incumbent_transaction_state()
        previous_snapshot_handle = self._latest_snapshot_handle
        previous_snapshot_generation = self._snapshot_generation
        previous_event_id = self._last_evaluation_event_id
        adapter_transaction = self.adapter.begin_step_transaction()
        self.begin_snapshot_step_transaction()
        try:
            outcome = self._step_transaction_body()
            outcome = self._finalize_evaluation_disposition(
                outcome,
                previous_authority_key=(
                    None
                    if previous_snapshot_handle is None
                    else str(previous_snapshot_handle.key)
                ),
            )
            if outcome.committed:
                self.commit_snapshot_step_transaction()
                outcome = self._settle_evaluation_disposition_best_effort(outcome)
            else:
                self.rollback_snapshot_step_transaction()
        except BaseException as exc:
            self._record_failed_evaluation_disposition(
                exc,
                previous_event_id=previous_event_id,
                previous_authority_key=(
                    None
                    if previous_snapshot_handle is None
                    else str(previous_snapshot_handle.key)
                ),
            )
            _rollback_step_failure(
                exc,
                (
                    ("snapshot", self.rollback_snapshot_step_transaction),
                    ("adapter", adapter_transaction.rollback),
                    (
                        "solver.authority",
                        lambda: self._restore_authority_projection(previous_projection),
                    ),
                    (
                        "solver.incumbent",
                        lambda: self._restore_incumbent_transaction_state(
                            previous_incumbent
                        ),
                    ),
                    (
                        "solver.snapshot_handle",
                        lambda: setattr(
                            self,
                            "_latest_snapshot_handle",
                            previous_snapshot_handle,
                        ),
                    ),
                    (
                        "solver.snapshot_generation",
                        lambda: setattr(
                            self,
                            "_snapshot_generation",
                            previous_snapshot_generation,
                        ),
                    ),
                ),
            )
            raise
        report = adapter_transaction.commit()
        return self._attach_adapter_commit_report(outcome, report)

    def _finalize_evaluation_disposition(
        self,
        outcome: StepOutcome,
        *,
        previous_authority_key: str | None,
    ) -> StepOutcome:
        """Persist the decision edge for the Event produced by this attempt."""

        event_evidence = dict(outcome.metadata.get("evaluation_event", {}) or {})
        event_id = str(event_evidence.get("event_id", "") or "")
        if not event_id:
            return outcome
        status = "committed" if outcome.committed else "rejected"
        authority_key = (
            self.pending_snapshot_step_key()
            if outcome.committed
            else previous_authority_key
        )
        disposition_payload = {
            "evaluation_acceptance": dict(
                outcome.metadata.get("evaluation_acceptance", {}) or {}
            ),
            "proposal_disposition": dict(
                outcome.metadata.get("proposal_disposition", {}) or {}
            ),
            "step_status": outcome.status,
            "reason": outcome.reason,
        }
        envelope = EvaluationDispositionEnvelope(
            event_id=event_id,
            status=status,
            disposition_codec="nsgablack.evaluation_disposition/v1",
            disposition_payload=disposition_payload,
            event_snapshot_key=str(
                event_evidence.get("snapshot_key", "") or ""
            ),
            authority_snapshot_key=str(authority_key or ""),
            identity=dict(self._last_evaluation_event_identity),
            metadata={
                "authority_unchanged": not outcome.committed,
                "authority_mode": str(self.population_authority_mode),
            },
        )
        disposition_snapshot_key: str | None = None
        if outcome.committed:
            attached = self.attach_evaluation_disposition_to_pending_snapshot(
                envelope
            )
            if not attached:
                raise RuntimeError(
                    "committed evaluation disposition has no staged authority Snapshot"
                )
            self.prepare_evaluation_disposition(envelope)
        else:
            intended_key = self._evaluation_evidence_snapshot_key(
                "disposition",
                envelope.event_id,
            )
            self.prepare_evaluation_disposition(
                envelope,
                disposition_snapshot_key=intended_key,
            )
            disposition_snapshot_key = self.write_evaluation_disposition_snapshot(
                envelope,
                force_key=intended_key,
            )
        evidence = envelope.as_dict()
        if disposition_snapshot_key is not None:
            evidence["disposition_snapshot_key"] = disposition_snapshot_key
        finalized = outcome.with_metadata(evaluation_disposition=evidence)
        if not outcome.committed and disposition_snapshot_key is not None:
            finalized = self._settle_evaluation_disposition_best_effort(finalized)
        return finalized

    def _settle_evaluation_disposition_best_effort(
        self,
        outcome: StepOutcome,
    ) -> StepOutcome:
        evidence = dict(outcome.metadata.get("evaluation_disposition", {}) or {})
        if not evidence:
            return outcome
        event_id = str(evidence.get("event_id", "") or "")
        if not event_id:
            return outcome
        try:
            record = self.settle_evaluation_disposition(event_id)
            evidence["journal_record"] = record.as_dict()
        except BaseException as exc:
            current = self.evaluation_evidence_journal.get(event_id)
            evidence["journal_settlement"] = {
                "status": "deferred",
                "record_status": None if current is None else current.status,
                "record_revision": None if current is None else current.revision,
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        return outcome.with_metadata(evaluation_disposition=evidence)

    def _record_failed_evaluation_disposition(
        self,
        error: BaseException,
        *,
        previous_event_id: str | None,
        previous_authority_key: str | None,
    ) -> None:
        """Best-effort failure edge without ever replacing the primary error."""

        event_id = str(self._last_evaluation_event_id or "")
        if not event_id or event_id == str(previous_event_id or ""):
            return
        try:
            envelope = EvaluationDispositionEnvelope(
                event_id=event_id,
                status="failed",
                disposition_codec="nsgablack.evaluation_disposition/v1",
                disposition_payload={
                    "step_status": "failed",
                    "error_type": type(error).__name__,
                    "message": str(error),
                },
                event_snapshot_key=str(
                    self._last_evaluation_event_snapshot_key or ""
                ),
                authority_snapshot_key=str(previous_authority_key or ""),
                identity=dict(self._last_evaluation_event_identity),
                metadata={
                    "authority_unchanged": True,
                    "authority_commit_uncertain": bool(
                        self.pending_snapshot_step_key()
                    ),
                },
            )
            intended_key = self._evaluation_evidence_snapshot_key(
                "disposition",
                envelope.event_id,
            )
            self.prepare_evaluation_disposition(
                envelope,
                disposition_snapshot_key=intended_key,
            )
            disposition_key = self.write_evaluation_disposition_snapshot(
                envelope,
                force_key=intended_key,
            )
            evidence = envelope.as_dict()
            if disposition_key is not None:
                evidence["disposition_snapshot_key"] = disposition_key
                record = self.settle_evaluation_disposition(event_id)
                evidence["journal_record"] = record.as_dict()
            context = dict(
                getattr(error, "_nsgablack_error_context", {}) or {}
            )
            context["evaluation_disposition"] = evidence
            setattr(error, "_nsgablack_error_context", context)
            attach_failure_evidence(error, "nsgablack", context)
        except BaseException as evidence_error:
            context = dict(
                getattr(error, "_nsgablack_error_context", {}) or {}
            )
            context["evaluation_disposition_write_failure"] = {
                "error_type": type(evidence_error).__name__,
                "message": str(evidence_error),
            }
            try:
                setattr(error, "_nsgablack_error_context", context)
                attach_failure_evidence(error, "nsgablack", context)
            except Exception:
                pass
            add_note = getattr(error, "add_note", None)
            if callable(add_note):
                add_note(
                    "Evaluation disposition evidence also failed: "
                    f"{type(evidence_error).__name__}: {evidence_error}"
                )

    def _attach_adapter_commit_report(
        self,
        outcome: StepOutcome,
        report: AdapterCommitReport,
    ) -> StepOutcome:
        report_payload = report.as_dict()
        metadata = dict(outcome.metadata)
        metadata["adapter_post_commit_cleanup"] = report_payload
        try:
            snapshot_key = make_snapshot_key(
                prefix=(
                    f"{self._active_run_id or 'unscoped'}"
                    "/adapter-commit-report"
                ),
                generation=int(self.generation),
                step=int(self.run_progress_attempts),
            )
            handle = self.snapshot_store.write(
                {"adapter_commit_report": report_payload},
                key=snapshot_key,
                meta={
                    "run_id": str(self._active_run_id or ""),
                    "generation": int(self.generation),
                    "attempts_completed": int(self.run_progress_attempts),
                    "semantic_commit": bool(outcome.committed),
                },
                schema="nsgablack.adapter_commit_report/v2",
                ttl_seconds=self.snapshot_store_ttl_seconds,
            )
            metadata["adapter_commit_report_snapshot_key"] = str(handle.key)
            self.context_store.set(
                KEY_ADAPTER_COMMIT_REPORT_REF,
                str(handle.key),
                ttl_seconds=self.context_store_ttl_seconds,
            )
        except BaseException as persistence_error:
            metadata["adapter_commit_report_persistence_error"] = {
                "error_type": type(persistence_error).__name__,
                "message": str(persistence_error),
            }
        self._last_adapter_commit_report = dict(metadata["adapter_post_commit_cleanup"])
        if "adapter_commit_report_snapshot_key" in metadata:
            self._last_adapter_commit_report["snapshot_key"] = metadata[
                "adapter_commit_report_snapshot_key"
            ]
        if "adapter_commit_report_persistence_error" in metadata:
            self._last_adapter_commit_report["persistence_error"] = metadata[
                "adapter_commit_report_persistence_error"
            ]
        return StepOutcome(
            status=outcome.status,
            evaluations=outcome.evaluations,
            proposals=outcome.proposals,
            stop_requested=outcome.stop_requested,
            reason=outcome.reason,
            metadata=metadata,
        )

    def _step_transaction_body(self) -> StepOutcome:
        if self.adapter is None:
            return StepOutcome(
                status="terminal",
                stop_requested=True,
                reason="adapter_unavailable",
            )
        if bool(getattr(self, "stop_requested", False)):
            return StepOutcome(
                status="cancelled",
                stop_requested=True,
                reason=str(getattr(self, "stop_reason", None) or "stop_requested"),
            )

        authority_resolver = getattr(
            self.adapter,
            "resolve_population_state_mode",
            None,
        )
        resolved_authority = (
            str(authority_resolver()).strip().lower()
            if callable(authority_resolver)
            else "unresolved"
        )
        if resolved_authority in {"single", "partitioned"}:
            self.population_authority_mode = resolved_authority
        elif resolved_authority == "none":
            self.population_authority_mode = "step_batch"
        elif resolved_authority != "unresolved":
            raise ValueError(
                "Adapter returned invalid resolved population authority: "
                f"{resolved_authority!r}"
            )

        previous_projection = self._capture_authority_projection()
        previous_population_batch = previous_projection["candidate_batch"]
        previous_population_provenance = previous_projection["candidate_provenance"]
        propose_context = self.build_context()
        propose_context[KEY_STEP] = self.generation

        proposed = self.adapter.coerce_candidates(self.adapter.propose(self, propose_context))
        candidate_provenance = self.prepare_candidate_provenance(proposed)
        candidate_batch = normalize_candidate_batch(
            proposed,
            dimension=self.dimension,
            owner=getattr(self.adapter, "name", "adapter"),
            candidate_tokens=[item.candidate_token for item in candidate_provenance],
        )
        candidates, candidate_provenance = self.bind_candidate_batch(
            candidate_batch,
            candidate_provenance,
            activate=False,
        )
        requested_count = len(candidates)
        if requested_count == 0:
            empty_outcome_getter = getattr(
                self.adapter,
                "get_empty_proposal_outcome",
                None,
            )
            empty_outcome = (
                empty_outcome_getter(self, propose_context)
                if callable(empty_outcome_getter)
                else None
            )
            if empty_outcome is not None:
                if not isinstance(empty_outcome, StepOutcome):
                    raise TypeError(
                        "Adapter.get_empty_proposal_outcome() must return "
                        "StepOutcome or None"
                    )
                if empty_outcome.committed:
                    raise ValueError(
                        "An empty Adapter proposal cannot commit a logical step"
                    )
                return empty_outcome
        approved_count = self.evaluation_batch_allowance(
            requested_count,
            context=propose_context,
        )
        if approved_count <= 0:
            self._restore_authority_projection(previous_projection)
            if requested_count > 0:
                self._notify_proposal_disposition(
                    proposed_count=requested_count,
                    accepted_count=0,
                    context=propose_context,
                    reason="evaluation_budget_exhausted",
                )
                self.last_step_summary = {
                    "num_proposed": int(requested_count),
                    "num_candidates": 0,
                    "budget_truncated": True,
                }
                self.request_stop()
            return StepOutcome(
                status="rejected" if requested_count > 0 else "idle",
                proposals=requested_count,
                stop_requested=bool(requested_count > 0),
                reason=(
                    "evaluation_budget_exhausted"
                    if requested_count > 0
                    else "adapter_proposed_no_candidates"
                ),
            )
        if approved_count < requested_count:
            candidates = candidates[:approved_count]
            candidate_provenance = candidate_provenance[:approved_count]
        # If a representation pipeline is attached, enforce a repair pass so
        # all adapter-produced candidates go through the main pipeline.
        if len(candidates) > 0 and self.representation_pipeline is not None:
            repair = getattr(self.representation_pipeline, "repair", None)
            if repair is not None:
                if hasattr(self.representation_pipeline, "repair_batch"):
                    repaired = self.representation_pipeline.repair_batch(
                        candidates,
                        context=propose_context,
                    )
                else:
                    repaired = [
                        self.repair_candidate(cand, propose_context)
                        for cand in candidates
                    ]
                candidate_batch = normalize_candidate_batch(
                    repaired,
                    dimension=self.dimension,
                    owner=f"{getattr(self.adapter, 'name', 'adapter')}.repair",
                    candidate_tokens=[
                        item.candidate_token for item in candidate_provenance
                    ],
                )
                candidates, candidate_provenance = self.bind_candidate_batch(
                    candidate_batch,
                    candidate_provenance,
                    activate=False,
                )
        candidate_count = len(candidates)
        if candidate_count != approved_count:
            raise ValueError(
                "Representation repair must preserve candidate count: "
                f"expected={approved_count}, actual={candidate_count}"
            )

        self.bind_candidate_provenance(candidates, candidate_provenance)
        self.population = stack_population(candidates, name="ComposableSolver.population")
        self.activate_candidate_provenance(self.population, candidate_provenance)
        (
            self.population,
            self.objectives,
            self.constraint_violations,
            reservation_truncated,
        ) = self._evaluate_population_with_budget_retry(self.population)
        evaluated_count = int(self.population.shape[0])
        self._active_candidate_provenance = candidate_provenance[:evaluated_count]
        self.activate_candidate_provenance(
            self.population,
            self._active_candidate_provenance,
        )
        evaluated_batch = CandidateBatch(
            semantic_states=tuple(candidate_batch.semantic_states[:evaluated_count]),
            numeric_matrix=np.asarray(self.population, dtype=float),
            candidate_tokens=tuple(
                item.candidate_token
                for item in self._active_candidate_provenance
            ),
        )
        budget_disposition = BatchDisposition.prefix(
            proposed_count=requested_count,
            accepted_count=evaluated_count,
            reason=(
                "evaluation_budget_race"
                if reservation_truncated
                else "evaluation_budget_allowance"
            ),
            metadata={"control": type(self).__name__},
        )
        if evaluated_count == 0:
            self._restore_authority_projection(previous_projection)
            self.adapter.on_proposal_disposition(
                self,
                budget_disposition,
                propose_context,
            )
            self.last_step_summary = {
                "num_proposed": int(requested_count),
                "num_candidates": 0,
                "budget_truncated": True,
            }
            self.request_stop()
            return StepOutcome(
                status="rejected",
                proposals=requested_count,
                stop_requested=True,
                reason="evaluation_budget_race",
            )

        feedback_batch = self.get_last_feedback_batch()
        if (
            feedback_batch is None
            or feedback_batch.candidate_count != evaluated_count
        ):
            feedback_batch = OptimizationFeedbackBatch.from_arrays(
                self.objectives,
                self.constraint_violations,
                metadata={"evaluation_path": "legacy_solver"},
            )
        else:
            feedback_batch = feedback_batch.with_arrays(
                self.objectives,
                self.constraint_violations,
            )

        full_evaluated_batch = evaluated_batch
        full_feedback_batch = feedback_batch
        full_evaluated_provenance = tuple(self._active_candidate_provenance)
        full_population = np.array(self.population, dtype=float, copy=True)
        full_objectives = np.array(self.objectives, dtype=float, copy=True)
        full_violations = np.array(
            self.constraint_violations,
            dtype=float,
            copy=True,
        ).reshape(-1)

        try:
            self.record_evaluation_event(
                full_evaluated_batch,
                full_feedback_batch,
                full_evaluated_provenance,
            )
            previous_mode = str(previous_projection["authority_mode"])
            previous_complete = (
                bool(previous_projection["partitions"])
                if previous_mode == "partitioned"
                else (
                    previous_projection["population"] is not None
                    and previous_projection["objectives"] is not None
                    and previous_projection["violations"] is not None
                )
            )
            event_snapshot_key = self.write_evaluation_event_snapshot(
                authority_population=(
                    None
                    if previous_mode == "partitioned"
                    else previous_projection["population"]
                ),
                authority_objectives=(
                    None
                    if previous_mode == "partitioned"
                    else previous_projection["objectives"]
                ),
                authority_violations=(
                    None
                    if previous_mode == "partitioned"
                    else previous_projection["violations"]
                ),
                authority_complete=previous_complete,
            )
            acceptance_context = self.build_context()
            if event_snapshot_key is not None:
                acceptance_context[KEY_SNAPSHOT_KEY] = event_snapshot_key
            acceptance_context[KEY_STEP] = self.generation
            evaluation_scores = self._score_incumbent_candidates(
                full_objectives,
                full_violations,
            )
            evaluation_selection = self._select_best_from_scores(
                full_violations,
                evaluation_scores,
            )
            evaluation_summary = self._summarize_step(
                full_objectives,
                full_violations,
                selection=evaluation_selection,
            )
            event_best_index = int(evaluation_selection[0])
            context_metadata = dict(
                acceptance_context.get(KEY_METADATA, {}) or {}
            )
            context_metadata["evaluation_event"] = {
                **evaluation_summary,
                "evaluation_count": int(self.evaluation_count),
                "candidate_token": full_evaluated_batch.candidate_tokens[
                    event_best_index
                ],
                "snapshot_key": event_snapshot_key,
                "event_id": self._last_evaluation_event_id,
            }
            acceptance_context[KEY_METADATA] = context_metadata

            acceptance_disposition = BatchDisposition.prefix(
                proposed_count=evaluated_count,
                accepted_count=evaluated_count,
                reason="evaluation_acceptance_not_configured",
            )
            if self.evaluation_acceptance_policy is not None:
                selected = self.evaluation_acceptance_policy.select(
                    full_evaluated_batch,
                    full_feedback_batch,
                    acceptance_context,
                )
                if not isinstance(selected, BatchDisposition):
                    raise TypeError(
                        "evaluation acceptance policy must return BatchDisposition"
                    )
                if selected.proposed_count != evaluated_count:
                    raise ValueError(
                        "evaluation acceptance disposition must reference the evaluated batch: "
                        f"expected={evaluated_count}, actual={selected.proposed_count}"
                    )
                acceptance_disposition = selected

            final_disposition = budget_disposition.compose(
                acceptance_disposition,
                reason=(
                    acceptance_disposition.reason
                    if acceptance_disposition.changed
                    else budget_disposition.reason
                ),
                metadata={"control": type(self).__name__},
            )
            # Every proposal attempt receives exactly one final disposition.
            # Identity dispositions are still significant to transparent and
            # composite wrappers because they may need to reconcile an earlier
            # local allocation without publishing an intermediate callback.
            self.adapter.on_proposal_disposition(
                self,
                final_disposition,
                acceptance_context,
            )
        except BaseException:
            self._restore_authority_projection(previous_projection)
            raise

        accepted_indices = np.asarray(
            acceptance_disposition.accepted_indices,
            dtype=int,
        )
        accepted_update_batch = full_evaluated_batch.subset(accepted_indices)
        accepted_feedback_batch = full_feedback_batch.subset(accepted_indices)
        accepted_provenance = tuple(
            full_evaluated_provenance[int(index)]
            for index in accepted_indices
        )

        accepted_count = int(acceptance_disposition.accepted_count)
        acceptance_audit = acceptance_disposition.as_dict()
        proposal_disposition_audit = final_disposition.as_dict()
        if accepted_count == 0:
            self._restore_authority_projection(previous_projection)
            self.last_step_summary = {
                "num_proposed": int(requested_count),
                "num_evaluated": int(evaluated_count),
                "num_candidates": 0,
                "budget_truncated": bool(
                    approved_count < requested_count or reservation_truncated
                ),
                "evaluation_acceptance": acceptance_audit,
                "proposal_disposition": proposal_disposition_audit,
            }
            return StepOutcome(
                status="rejected",
                proposals=requested_count,
                evaluations=evaluated_count,
                reason=acceptance_disposition.reason,
                metadata={
                    "evaluation_acceptance": acceptance_audit,
                    "proposal_disposition": proposal_disposition_audit,
                    "evaluation_event": {
                        "event_id": self._last_evaluation_event_id,
                        "snapshot_key": event_snapshot_key,
                    },
                },
            )

        self.population = np.asarray(
            full_population[accepted_indices],
            dtype=float,
        )
        self.objectives = np.asarray(
            full_objectives[accepted_indices],
            dtype=float,
        )
        self.constraint_violations = np.asarray(
            full_violations[accepted_indices],
            dtype=float,
        )
        self._active_candidate_provenance = list(accepted_provenance)
        self.activate_candidate_provenance(
            self.population,
            self._active_candidate_provenance,
        )

        incumbent_selection = self._select_best_from_scores(
            self.constraint_violations,
            evaluation_scores[accepted_indices],
        )
        self.last_step_summary = self._summarize_step(
            self.objectives,
            self.constraint_violations,
            selection=incumbent_selection,
        )
        self.last_step_summary.update(
            {
                "num_proposed": int(requested_count),
                "num_evaluated": int(evaluated_count),
                "evaluation_acceptance": acceptance_audit,
                "proposal_disposition": proposal_disposition_audit,
                "budget_truncated": bool(
                    approved_count < requested_count
                    or reservation_truncated
                ),
            }
        )

        update_context = self.build_context()
        update_context[KEY_STEP] = self.generation
        self.adapter.update(
            self,
            self.population,
            accepted_feedback_batch,
            update_context,
        )
        snapshot_getter = getattr(self.adapter, "get_population_snapshot", None)
        authoritative = snapshot_getter() if callable(snapshot_getter) else None
        partition_getter = getattr(self.adapter, "get_population_partitions", None)
        partitions = (
            tuple(partition_getter() or ())
            if callable(partition_getter)
            else ()
        )
        if authoritative is not None:
            (
                authoritative_population,
                authoritative_objectives,
                authoritative_violations,
            ) = authoritative
            token_getter = getattr(
                self.adapter,
                "get_population_candidate_tokens",
                None,
            )
            authoritative_tokens = (
                token_getter() if callable(token_getter) else None
            )
            authoritative_array = np.asarray(
                authoritative_population,
                dtype=float,
            )
            if authoritative_tokens is None and (
                authoritative_array.shape == accepted_update_batch.numeric_matrix.shape
                and np.array_equal(
                    authoritative_array,
                    accepted_update_batch.numeric_matrix,
                    equal_nan=True,
                )
            ):
                authoritative_tokens = accepted_update_batch.candidate_tokens
            if (
                authoritative_tokens is None
                and previous_population_batch is not None
                and authoritative_array.shape
                == previous_population_batch.numeric_matrix.shape
                and np.array_equal(
                    authoritative_array,
                    previous_population_batch.numeric_matrix,
                    equal_nan=True,
                )
            ):
                authoritative_tokens = previous_population_batch.candidate_tokens
            committed_batch = self.commit_candidate_population(
                authoritative_array,
                authoritative_tokens,
                sources=(
                    (accepted_update_batch, accepted_provenance),
                    (previous_population_batch, previous_population_provenance),
                ),
            )
            token_setter = getattr(
                self.adapter,
                "set_population_candidate_tokens",
                None,
            )
            if callable(token_setter):
                token_setter(committed_batch.candidate_tokens)
            self._candidate_population_partitions = {}
            self.population_authority_mode = "single"
            commit_population_snapshot(
                self,
                authoritative_population,
                authoritative_objectives,
                authoritative_violations,
                strict=True,
            )
        elif partitions:
            self._commit_candidate_population_partitions(
                partitions,
                evaluated_batch=accepted_update_batch,
                evaluated_provenance=accepted_provenance,
                previous_population_batch=previous_population_batch,
                previous_population_provenance=tuple(
                    previous_population_provenance
                ),
            )
            self._candidate_population_batch = None
            self._candidate_population_provenance = ()
            self._active_candidate_provenance = []
            self._active_candidate_population_ref = None
            self.population_authority_mode = "partitioned"
            self.population = None
            self.objectives = None
            self.constraint_violations = None
            self.write_partitioned_population_snapshot()

        else:
            self._candidate_population_partitions = {}
            self.population_authority_mode = "step_batch"
            self.commit_candidate_population(
                accepted_update_batch.numeric_matrix,
                accepted_update_batch.candidate_tokens,
                sources=((accepted_update_batch, accepted_provenance),),
            )
            self.write_population_snapshot(
                self.population,
                self.objectives,
                self.constraint_violations,
            )

        self._update_best(
            accepted_update_batch.numeric_matrix,
            accepted_feedback_batch.objectives,
            accepted_feedback_batch.violations,
            selection=incumbent_selection,
            provenance=accepted_provenance,
        )

        return StepOutcome(
            status="committed",
            evaluations=evaluated_count,
            proposals=requested_count,
            stop_requested=bool(getattr(self, "stop_requested", False)),
            reason=str(getattr(self, "stop_reason", None) or ""),
            metadata={
                "authority_mode": self.population_authority_mode,
                "budget_truncated": bool(
                    approved_count < requested_count or reservation_truncated
                ),
                "accepted_evaluations": accepted_count,
                "evaluation_acceptance": acceptance_audit,
                "proposal_disposition": proposal_disposition_audit,
                "evaluation_event": {
                    "event_id": self._last_evaluation_event_id,
                    "snapshot_key": event_snapshot_key,
                },
            },
        )

    def _commit_candidate_population_partitions(
        self,
        partitions: Sequence[PopulationPartition],
        *,
        evaluated_batch: CandidateBatch,
        evaluated_provenance: Sequence[Any],
        previous_population_batch: CandidateBatch | None,
        previous_population_provenance: Sequence[Any],
    ) -> None:
        previous_states = dict(self._candidate_population_partitions)
        sources: list[tuple[CandidateBatch | None, Sequence[Any]]] = [
            (evaluated_batch, tuple(evaluated_provenance)),
            (
                previous_population_batch,
                tuple(previous_population_provenance),
            ),
        ]
        sources.extend(
            (batch, provenance)
            for _partition, batch, provenance in previous_states.values()
        )
        committed: dict[
            str,
            tuple[PopulationPartition, CandidateBatch, tuple[Any, ...]],
        ] = {}
        for partition in tuple(partitions or ()):
            if partition.partition_id in committed:
                raise ValueError(
                    "Adapter exported duplicate population partition ID: "
                    f"{partition.partition_id}"
                )
            batch, provenance = self._materialize_candidate_population(
                partition.population,
                partition.candidate_tokens,
                sources=tuple(sources),
            )
            normalized_partition = PopulationPartition(
                partition_id=partition.partition_id,
                population=partition.population,
                objectives=partition.objectives,
                violations=partition.violations,
                candidate_tokens=batch.candidate_tokens,
                owner=partition.owner,
                metadata=partition.metadata,
            )
            committed[partition.partition_id] = (
                normalized_partition,
                batch,
                provenance,
            )
        self._candidate_population_partitions = committed

    def get_candidate_population_partitions(
        self,
    ) -> Mapping[str, CandidateBatch]:
        return {
            partition_id: value[1]
            for partition_id, value in self._candidate_population_partitions.items()
        }

    def export_candidate_population_partitions_checkpoint_state(
        self,
    ) -> dict[str, Any] | None:
        if not self._candidate_population_partitions:
            return None
        return {
            "schema": "nsgablack.candidate_population_partitions/v1",
            "authority_mode": "partitioned",
            "partitions": [
                {
                    "partition": partition.as_dict(),
                    "batch": batch.as_dict(),
                    "provenance": [item.as_dict() for item in provenance],
                }
                for partition, batch, provenance in self._candidate_population_partitions.values()
            ],
        }

    def restore_candidate_population_partitions_checkpoint_state(
        self,
        payload: Mapping[str, Any] | None,
    ) -> None:
        if not isinstance(payload, Mapping):
            self._candidate_population_partitions = {}
            return
        schema = str(payload.get("schema", ""))
        if schema != "nsgablack.candidate_population_partitions/v1":
            raise ValueError(
                f"unsupported candidate population partition schema: {schema}"
            )
        restored: dict[
            str,
            tuple[PopulationPartition, CandidateBatch, tuple[Any, ...]],
        ] = {}
        from .state.incumbent import CandidateProvenance

        for item in tuple(payload.get("partitions", ()) or ()):
            partition = PopulationPartition.from_dict(item.get("partition", {}))
            batch = CandidateBatch.from_dict(item.get("batch", {}))
            provenance = tuple(
                CandidateProvenance.from_dict(value)
                for value in tuple(item.get("provenance", ()) or ())
            )
            if partition.partition_id in restored:
                raise ValueError(
                    "candidate population checkpoint contains duplicate partition IDs"
                )
            if batch.numeric_matrix.shape != partition.population.shape or not np.array_equal(
                batch.numeric_matrix,
                partition.population,
                equal_nan=True,
            ):
                raise ValueError(
                    "candidate population partition semantic/numeric state mismatch"
                )
            if tuple(batch.candidate_tokens) != tuple(partition.candidate_tokens):
                raise ValueError(
                    "candidate population partition token state mismatch"
                )
            if len(provenance) != len(batch.semantic_states):
                raise ValueError(
                    "candidate population partition provenance is misaligned"
                )
            for token, record in zip(batch.candidate_tokens, provenance):
                if token != record.candidate_token:
                    raise ValueError(
                        "candidate population partition token disagrees with lineage"
                    )
            restored[partition.partition_id] = (
                partition,
                batch,
                provenance,
            )
        self._candidate_population_partitions = restored
        self.population_authority_mode = (
            "partitioned" if restored else "single"
        )

    def _normalize_violation_values(
        self,
        violations: Optional[np.ndarray],
        *,
        rows: int,
    ) -> np.ndarray:
        if violations is None:
            return np.zeros((rows,), dtype=float)
        values = np.asarray(violations, dtype=float).reshape(-1)
        if values.shape[0] != rows:
            raise ValueError(
                "constraint violations must align with objective rows: "
                f"expected={rows}, actual={values.shape[0]}"
            )
        return values

    def _candidate_objective_score(
        self,
        objectives: np.ndarray,
        violations: np.ndarray,
        idx: int,
    ) -> float:
        scalarizer = self.objective_scalarizer
        objective_row = np.asarray(objectives[idx], dtype=float).reshape(-1)
        violation = float(violations[idx])
        if callable(scalarizer):
            try:
                score = float(
                    scalarizer(
                        objective_row.copy(),
                        violation,
                        dict(self.incumbent_scalarizer_context),
                    )
                )
                if not np.isfinite(score):
                    raise ValueError("scalarizer returned a non-finite score")
            except Exception as exc:
                policy = str(self.scalarizer_failure_policy or "raise").strip().lower()
                if policy != "fallback_sum":
                    raise ScalarizationError(
                        "incumbent scalarization failed",
                        candidate_index=int(idx),
                        objective_row=objective_row,
                        violation=violation,
                        policy_id=self.incumbent_scalarizer_id,
                    ) from exc
                self.scalarizer_fallback_count += 1
                self.result_quality_degraded = True
                score = float(np.sum(objective_row))
        else:
            score = float(np.sum(objective_row))
        return score if np.isfinite(score) else float("inf")

    @staticmethod
    def _order_key_from_score(violation: float, score: float) -> Tuple[int, float, float]:
        normalized_violation = float(violation)
        if not np.isfinite(normalized_violation):
            normalized_violation = float("inf")
        feasible = normalized_violation <= 0.0
        return (
            0 if feasible else 1,
            0.0 if feasible else normalized_violation,
            float(score),
        )

    def _candidate_order_key(
        self,
        objectives: np.ndarray,
        violations: np.ndarray,
        idx: int,
    ) -> Tuple[int, float, float]:
        return self._order_key_from_score(
            float(violations[idx]),
            self._candidate_objective_score(objectives, violations, idx),
        )

    def select_best_with_score(
        self,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> Tuple[int, float]:
        objective_values = np.asarray(objectives, dtype=float)
        if objective_values.ndim == 1:
            objective_values = objective_values.reshape(-1, 1)
        if objective_values.ndim != 2 or objective_values.shape[0] == 0:
            return 0, float("inf")
        violation_values = self._normalize_violation_values(
            violations,
            rows=objective_values.shape[0],
        )
        scores = self._score_incumbent_candidates(
            objective_values,
            violation_values,
        )
        return self._select_best_from_scores(violation_values, scores)

    def _score_incumbent_candidates(
        self,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> np.ndarray:
        """Score each evaluated row once so all later projections can reuse it."""

        objective_values = np.asarray(objectives, dtype=float)
        if objective_values.ndim == 1:
            objective_values = objective_values.reshape(-1, 1)
        if objective_values.ndim != 2:
            raise ValueError("incumbent objectives must be two-dimensional")
        violation_values = self._normalize_violation_values(
            violations,
            rows=objective_values.shape[0],
        )
        return np.asarray(
            [
                self._candidate_objective_score(
                    objective_values,
                    violation_values,
                    idx,
                )
                for idx in range(objective_values.shape[0])
            ],
            dtype=float,
        )

    def _select_best_from_scores(
        self,
        violations: np.ndarray,
        scores: np.ndarray,
    ) -> Tuple[int, float]:
        """Select feasibility-first best without executing the scalarizer again."""

        score_values = np.asarray(scores, dtype=float).reshape(-1)
        if score_values.size == 0:
            return 0, float("inf")
        violation_values = self._normalize_violation_values(
            violations,
            rows=score_values.size,
        )
        keys = [
            self._order_key_from_score(
                float(violation_values[idx]),
                float(score_values[idx]),
            )
            for idx in range(score_values.size)
        ]
        best_idx = min(range(len(keys)), key=keys.__getitem__)
        return int(best_idx), float(keys[best_idx][2])

    def select_best(self, objectives: np.ndarray, violations: np.ndarray) -> int:
        best_idx, _ = self.select_best_with_score(objectives, violations)
        return best_idx

    def _update_best(
        self,
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
        *,
        selection: Optional[Tuple[int, float]] = None,
        provenance: Optional[Sequence[Any]] = None,
    ) -> None:
        if population is None or len(population) == 0:
            return
        population_values = np.asarray(population, dtype=float)
        objective_values = np.asarray(objectives, dtype=float)
        if objective_values.ndim == 1:
            objective_values = objective_values.reshape(-1, 1)
        if population_values.ndim != 2 or objective_values.ndim != 2:
            raise ValueError("incumbent candidates and objectives must be two-dimensional")
        if population_values.shape[0] != objective_values.shape[0]:
            raise ValueError("incumbent candidates and objectives must have matching rows")
        violation_values = self._normalize_violation_values(
            violations,
            rows=objective_values.shape[0],
        )

        best_idx, best_score = (
            self.select_best_with_score(objective_values, violation_values)
            if selection is None
            else (int(selection[0]), float(selection[1]))
        )
        best_violation = float(violation_values[best_idx])
        if not np.isfinite(best_score) or not np.isfinite(best_violation):
            return
        incumbent = self.get_incumbent()
        if incumbent is not None:
            if incumbent.policy_id != self.incumbent_scalarizer_id:
                raise ScalarizationError(
                    "incumbent scalarizer policy changed during an active run",
                    policy_id=self.incumbent_scalarizer_id,
                )
            if self._policy_context_signature(
                incumbent.policy_context
            ) != self._policy_context_signature(self.incumbent_scalarizer_context):
                raise ScalarizationError(
                    "incumbent scalarizer context changed during an active run",
                    policy_id=self.incumbent_scalarizer_id,
                )
            incumbent_key = self._order_key_from_score(
                incumbent.constraint_violation,
                incumbent.score,
            )
            candidate_key = self._order_key_from_score(best_violation, best_score)
            if incumbent_key <= candidate_key:
                return

        candidate = np.asarray(population_values[best_idx], dtype=float).reshape(-1)
        if provenance is not None:
            provenance_rows = tuple(provenance)
            if len(provenance_rows) != population_values.shape[0]:
                raise ValueError(
                    "incumbent provenance must align with candidate rows"
                )
            record = provenance_rows[best_idx]
            if not isinstance(record, CandidateProvenance):
                raise TypeError(
                    "incumbent provenance rows must be CandidateProvenance"
                )
            provenance_payload = {
                "candidate_token": record.candidate_token,
                "source": record.source_kind,
                "source_run_id": record.source_run_id,
                "warm_start_id": record.warm_start_id,
                "proposal_id": record.proposal_id,
                "parent_token": record.parent_token,
                "transform_stage": record.transform_stage,
                "metadata": dict(record.metadata),
            }
        else:
            provenance_payload = self.incumbent_source_for(
                candidate,
                candidate_index=best_idx,
                population=population_values,
            )
        evaluation_id = (
            f"{self._active_run_id or 'unscoped'}:generation:{int(self.generation)}:"
            f"evaluation:{int(self.evaluation_count)}:candidate:{int(best_idx)}"
        )
        self.set_incumbent(
            IncumbentState(
                candidate=candidate,
                objectives=objective_values[best_idx],
                constraint_violation=best_violation,
                score=best_score,
                policy_id=self.incumbent_scalarizer_id,
                policy_context=self.incumbent_scalarizer_context,
                evaluation_id=evaluation_id,
                candidate_token=provenance_payload.get("candidate_token"),
                source=provenance_payload["source"],
                source_run_id=provenance_payload.get("source_run_id"),
                warm_start_id=provenance_payload.get("warm_start_id"),
                proposal_id=provenance_payload.get("proposal_id"),
                metadata=provenance_payload.get("metadata", {}),
            )
        )

    def _summarize_step(
        self,
        objectives: np.ndarray,
        violations: np.ndarray,
        *,
        selection: Optional[Tuple[int, float]] = None,
    ) -> Dict[str, Any]:
        if objectives is None or len(objectives) == 0:
            return {}
        objective_values = np.asarray(objectives, dtype=float)
        if objective_values.ndim == 1:
            objective_values = objective_values.reshape(-1, 1)
        violation_values = self._normalize_violation_values(
            violations,
            rows=objective_values.shape[0],
        )
        best_idx, best_score = (
            self.select_best_with_score(objective_values, violation_values)
            if selection is None
            else (int(selection[0]), float(selection[1]))
        )
        return {
            "best_objective": best_score,
            "best_constraint_violation": float(violation_values[best_idx]),
            "best_index": int(best_idx),
            "num_candidates": int(len(objective_values)),
        }
