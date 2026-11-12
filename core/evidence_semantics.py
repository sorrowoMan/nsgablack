"""Read-only optimization semantics for the shared evidence coordinator.

The inspector receives stores, not a Solver. It cannot evaluate candidates,
invoke acceptance, update an Adapter, or advance run progress.
"""
from __future__ import annotations
from blackbase.context import AuthorityStore
import time
from enum import Enum
from typing import Any, Mapping
from blackbase.context import AuthorityIdentity
from blackbase.evaluation import EvaluationDispositionEnvelope, EvaluationDispositionVerificationReceipt, EvaluationEvidenceInspection, EvaluationEvidenceRecord, EvaluationEventEnvelope, evaluation_disposition_digest
from .solver_helpers import EVALUATION_EVENT_SNAPSHOT_SCHEMA_V1, LAST_EVALUATION_DISPOSITION_KEY, evaluation_event_envelope_from_snapshot, validate_evaluation_event_snapshot, validate_population_snapshot_v2
from blackbase.context import SnapshotIdentity, SnapshotRecord, SnapshotStore


class EvidenceReason(Enum):
    """Stable wire reason and recovery classification are one declaration."""
    VERIFIED = ("verified", "verified")
    SNAPSHOT_STORE_MISMATCH = ("snapshot_store_mismatch", "invalid")
    EVENT_SNAPSHOT_UNREADABLE = ("event_snapshot_unreadable", "deferred")
    EVENT_PREDECESSOR_UNREADABLE = ("event_predecessor_unreadable", "deferred")
    EVENT_SNAPSHOT_INVALID = ("event_snapshot_invalid", "invalid")
    MISSING_DISPOSITION_INTENT = ("missing_disposition_intent", "invalid")
    INVALID_DISPOSITION_INTENT = ("invalid_disposition_intent", "invalid")
    DISPOSITION_EVENT_ID_MISMATCH = ("disposition_event_id_mismatch", "invalid")
    EVENT_SNAPSHOT_KEY_MISSING = ("event_snapshot_key_missing", "invalid")
    EVENT_SNAPSHOT_KEY_MISMATCH = ("event_snapshot_key_mismatch", "invalid")
    EVENT_AUTHORITY_EDGE_MISMATCH = ("event_authority_edge_mismatch", "invalid")
    EVENT_AUTHORITY_PREDECESSOR_MISMATCH = ("event_authority_predecessor_mismatch", "invalid")
    DISPOSITION_PREDECESSOR_MISMATCH = ("disposition_predecessor_mismatch", "invalid")
    DESTINATION_SNAPSHOT_KEY_MISSING = ("destination_snapshot_key_missing", "invalid")
    DESTINATION_SNAPSHOT_UNREADABLE = ("destination_snapshot_unreadable", "deferred")
    DESTINATION_SNAPSHOT_INVALID = ("destination_snapshot_invalid", "invalid")
    DESTINATION_DISPOSITION_MISSING = ("destination_disposition_missing", "invalid")
    DESTINATION_DISPOSITION_MISMATCH = ("destination_disposition_mismatch", "invalid")
    AUTHORITY_MODE_MISSING = ("authority_mode_missing", "invalid")
    AUTHORITY_SNAPSHOT_SEMANTICALLY_INVALID = ("authority_snapshot_semantically_invalid", "invalid")
    AUTHORITY_EDGE_UNREADABLE = ("authority_edge_unreadable", "deferred")
    AUTHORITY_EDGE_DESTINATION_MISMATCH = ("authority_edge_destination_mismatch", "invalid")
    AUTHORITY_EDGE_EVENT_CAUSE_MISMATCH = ("authority_edge_event_cause_mismatch", "invalid")
    AUTHORITY_EDGE_EPOCH_MISMATCH = ("authority_edge_epoch_mismatch", "invalid")
    AUTHORITY_EDGE_SCOPE_MISMATCH = ("authority_edge_scope_mismatch", "invalid")
    SNAPSHOT_CONTENT_IDENTITY_MISSING = ("snapshot_content_identity_missing", "invalid")

    def inspection(self, **fields: Any) -> EvaluationEvidenceInspection:
        return EvaluationEvidenceInspection(state=self.value[1], reason=self.value[0], **fields)


class PopulationEvidenceSemantics:
    def __init__(self, snapshot_store: SnapshotStore, authority_store: AuthorityStore):
        self.snapshot_store = snapshot_store
        self.authority_store = authority_store

    @staticmethod
    def _population_authority_key(run_id: str) -> str:
        if not str(run_id).strip():
            raise ValueError("population authority requires a run_id")
        return f"population/{str(run_id).strip()}"

    @staticmethod
    def _snapshot_event_id(
        payload: Mapping[str, Any],
        *,
        snapshot_schema: str,
    ) -> str:
        try:
            envelope = evaluation_event_envelope_from_snapshot(
                payload,
                snapshot_schema=snapshot_schema,
            )
        except (TypeError, ValueError, KeyError):
            return ""
        return "" if envelope is None else envelope.event_id

    @staticmethod
    def _snapshot_disposition(
        payload: Mapping[str, Any],
    ) -> EvaluationDispositionEnvelope | None:
        raw = payload.get(LAST_EVALUATION_DISPOSITION_KEY)
        if not isinstance(raw, Mapping):
            return None
        try:
            return EvaluationDispositionEnvelope.from_dict(raw)
        except (TypeError, ValueError, KeyError):
            return None

    @staticmethod
    def _validate_event_authority_edge(
        envelope: EvaluationEventEnvelope,
        expected: AuthorityIdentity | None,
    ) -> AuthorityIdentity | None:
        """Bind the Event's full predecessor edge to the Journal reservation."""

        raw = envelope.identity.get("authority_before_edge")
        if expected is None:
            if raw is not None:
                raise ValueError(
                    "Evaluation Event carries an Authority edge absent from its journal"
                )
            return None
        if not isinstance(raw, Mapping):
            raise ValueError(
                "Evaluation Event is missing its reserved Authority predecessor edge"
            )
        observed = AuthorityIdentity.from_dict(raw)
        if observed != expected:
            raise ValueError(
                "Evaluation Event Authority edge disagrees with its journal reservation"
            )
        return observed

    def inspect_event(
        self,
        record: EvaluationEvidenceRecord,
        snapshots: SnapshotStore,
    ) -> EvaluationEvidenceInspection:
        """Implement BlackBase's read-only Event semantics for the coordinator."""

        if snapshots is not self.snapshot_store:
            return EvidenceReason.SNAPSHOT_STORE_MISMATCH.inspection()
        try:
            event_record, expected_event_ref = self._read_event_record(record)
        except (KeyError, OSError):
            return EvidenceReason.EVENT_SNAPSHOT_UNREADABLE.inspection()
        except Exception as exc:
            return EvidenceReason.EVENT_SNAPSHOT_INVALID.inspection(
                diagnostics={"error_type": type(exc).__name__, "message": str(exc)},
            )
        if event_record is None:
            return EvidenceReason.EVENT_SNAPSHOT_UNREADABLE.inspection()
        try:
            envelope, predecessor = validate_evaluation_event_snapshot(
                event_record.data,
                snapshot_schema=event_record.schema,
                expected_event_id=record.event_id,
                expected_run_id=record.run_id,
                expected_snapshot_key=record.event_snapshot_key,
            )
            event_ref = snapshots.identity(event_record)
            if expected_event_ref is None:
                snapshots.read_verified(event_ref)
            elif event_ref != expected_event_ref:
                raise ValueError("Verified Event view disagrees with its journal identity")
            raw_before = getattr(record, "authority_before_ref", None)
            before_edge = (
                None
                if raw_before is None
                else AuthorityIdentity.from_dict(raw_before)
            )
            self._validate_event_authority_edge(envelope, before_edge)
            if before_edge is not None:
                if predecessor != before_edge.snapshot:
                    raise ValueError(
                        "Event predecessor disagrees with reserved Authority edge"
                    )
                snapshots.read_verified_view(before_edge.snapshot)
            elif predecessor is not None:
                # v1/v2 journals did not carry an Authority edge.  Keep them
                # readable, but do not invent an epoch during migration.
                snapshots.read_verified_view(predecessor)
        except KeyError:
            return EvidenceReason.EVENT_PREDECESSOR_UNREADABLE.inspection()
        except Exception as exc:
            return EvidenceReason.EVENT_SNAPSHOT_INVALID.inspection(
                diagnostics={"error_type": type(exc).__name__, "message": str(exc)},
            )
        return EvidenceReason.VERIFIED.inspection(
            event_ref=event_ref,
            authority_before_ref=before_edge,
        )

    def _read_event_record(
        self, record: EvaluationEvidenceRecord,
    ) -> tuple[SnapshotRecord | None, SnapshotIdentity | None]:
        """Resolve one exact Event version without a preceding detached read."""
        if record.event_ref is None:
            # Preparing/legacy records may only know their reserved key. This
            # discovery never replaces a known but unreadable exact reference.
            return self.snapshot_store.read(record.event_snapshot_key), None
        identity = SnapshotIdentity.from_dict(record.event_ref)
        if identity.key != record.event_snapshot_key:
            raise ValueError("Event reference disagrees with its journal key")
        loaded = self.snapshot_store.read_verified_view(identity)
        if self.snapshot_store.identity(loaded) != identity:
            raise ValueError("Verified Event view disagrees with its journal identity")
        return loaded, identity

    def inspect_decision(
        self,
        record: EvaluationEvidenceRecord,
        snapshots: SnapshotStore,
    ) -> EvaluationEvidenceInspection:
        """Implement read-only disposition semantics for the coordinator."""

        if snapshots is not self.snapshot_store:
            return EvidenceReason.SNAPSHOT_STORE_MISMATCH.inspection()
        return self._inspect_evaluation_disposition_destination(record)

    def _inspect_evaluation_disposition_destination(
        self,
        record: EvaluationEvidenceRecord,
    ) -> EvaluationEvidenceInspection:
        """Read and compare the Event, intent, and terminal Snapshot edge."""

        destination_key = ""

        def result(reason: EvidenceReason, *, error: Exception | None = None, **fields: Any) -> EvaluationEvidenceInspection:
            diagnostics = {"destination_snapshot_key": destination_key}
            if error is not None:
                diagnostics.update(error_type=type(error).__name__, message=str(error))
            return reason.inspection(diagnostics=diagnostics, **fields)

        if record.disposition is None:
            return result(EvidenceReason.MISSING_DISPOSITION_INTENT)
        try:
            intent = EvaluationDispositionEnvelope.from_dict(record.disposition)
        except Exception as exc:
            return result(EvidenceReason.INVALID_DISPOSITION_INTENT, error=exc)
        if intent.event_id != record.event_id:
            return result(EvidenceReason.DISPOSITION_EVENT_ID_MISMATCH)
        if not intent.event_snapshot_key:
            return result(EvidenceReason.EVENT_SNAPSHOT_KEY_MISSING)
        if intent.event_snapshot_key != record.event_snapshot_key:
            return result(EvidenceReason.EVENT_SNAPSHOT_KEY_MISMATCH)
        try:
            event_record, _ = self._read_event_record(record)
        except (KeyError, OSError):
            return result(EvidenceReason.EVENT_SNAPSHOT_UNREADABLE)
        except Exception as exc:
            return result(EvidenceReason.EVENT_SNAPSHOT_INVALID, error=exc)
        if event_record is None:
            return result(EvidenceReason.EVENT_SNAPSHOT_UNREADABLE)
        try:
            event_envelope, authority_before = validate_evaluation_event_snapshot(
                event_record.data,
                snapshot_schema=event_record.schema,
                expected_event_id=intent.event_id,
                expected_run_id=record.run_id,
                expected_snapshot_key=intent.event_snapshot_key,
            )
        except Exception as exc:
            return result(EvidenceReason.EVENT_SNAPSHOT_INVALID, error=exc)
        if authority_before is not None:
            try:
                self.snapshot_store.read_verified_view(authority_before)
            except Exception as exc:
                return result(EvidenceReason.EVENT_PREDECESSOR_UNREADABLE, error=exc)
        journal_before_raw = getattr(record, "authority_before_ref", None)
        journal_before = (
            None
            if journal_before_raw is None
            else AuthorityIdentity.from_dict(journal_before_raw)
        )
        try:
            self._validate_event_authority_edge(event_envelope, journal_before)
        except Exception as exc:
            return result(EvidenceReason.EVENT_AUTHORITY_EDGE_MISMATCH, error=exc)
        if journal_before is not None and journal_before.snapshot != authority_before:
            return result(EvidenceReason.EVENT_AUTHORITY_PREDECESSOR_MISMATCH)
        if (
            event_record.schema == EVALUATION_EVENT_SNAPSHOT_SCHEMA_V1
            and intent.status in {"rejected", "failed"}
        ):
            expected_before_key = (
                "" if authority_before is None else authority_before.key
            )
            if intent.authority_snapshot_key != expected_before_key:
                return result(EvidenceReason.DISPOSITION_PREDECESSOR_MISMATCH)
        destination_key = (
            intent.authority_snapshot_key
            if intent.status == "committed"
            else record.disposition_snapshot_key
        )
        if not destination_key:
            return result(EvidenceReason.DESTINATION_SNAPSHOT_KEY_MISSING)
        destination_ref = None
        if intent.status == "committed":
            # A first settlement has no carrier identity in its Journal yet.
            # The published Authority supplies it. Recheck the current fence
            # below after inspecting the value: this lookup is not a cached
            # claim that the edge will remain current throughout inspection.
            published = self.authority_store.current(
                self._population_authority_key(record.run_id)
            )
            if published is not None and published.snapshot.key == destination_key:
                destination_ref = published.snapshot
        elif record.decision_carrier_ref is not None:
            destination_ref = SnapshotIdentity.from_dict(record.decision_carrier_ref)
            if destination_ref.key != destination_key:
                return result(EvidenceReason.DESTINATION_SNAPSHOT_INVALID)
        try:
            destination = (
                self.snapshot_store.read(destination_key)
                if destination_ref is None
                else self.snapshot_store.read_verified_view(destination_ref)
            )
        except (KeyError, OSError):
            return result(EvidenceReason.DESTINATION_SNAPSHOT_UNREADABLE)
        except Exception as exc:
            return result(EvidenceReason.DESTINATION_SNAPSHOT_INVALID, error=exc)
        if destination is None:
            return result(EvidenceReason.DESTINATION_SNAPSHOT_UNREADABLE)
        observed = self._snapshot_disposition(destination.data)
        if observed is None:
            return result(EvidenceReason.DESTINATION_DISPOSITION_MISSING)
        if observed.as_dict() != intent.as_dict():
            return result(EvidenceReason.DESTINATION_DISPOSITION_MISMATCH)
        event_identity = self.snapshot_store.identity(event_record)
        destination_identity = self.snapshot_store.identity(destination)
        if destination_ref is not None and destination_identity != destination_ref:
            return result(EvidenceReason.DESTINATION_SNAPSHOT_INVALID)
        authority_after: AuthorityIdentity | None = journal_before
        if intent.status == "committed":
            expected_mode = str(
                intent.metadata.get("authority_mode", "") or ""
            ).strip().lower()
            if not expected_mode:
                return result(EvidenceReason.AUTHORITY_MODE_MISSING)
            try:
                validate_population_snapshot_v2(
                    destination.data,
                    snapshot_schema=destination.schema,
                    expected_authority_mode=expected_mode,
                    require_semantic_identity=True,
                )
            except Exception as exc:
                return result(EvidenceReason.AUTHORITY_SNAPSHOT_SEMANTICALLY_INVALID, error=exc)
            authority_after = self.authority_store.current(
                self._population_authority_key(record.run_id)
            )
            if authority_after is None:
                return result(EvidenceReason.AUTHORITY_EDGE_UNREADABLE)
            if authority_after.snapshot != destination_identity:
                return result(EvidenceReason.AUTHORITY_EDGE_DESTINATION_MISMATCH)
            if authority_after.caused_by_event_identity != event_identity:
                return result(EvidenceReason.AUTHORITY_EDGE_EVENT_CAUSE_MISMATCH)
            expected_epoch = 1 if journal_before is None else journal_before.epoch + 1
            if authority_after.epoch != expected_epoch:
                return result(EvidenceReason.AUTHORITY_EDGE_EPOCH_MISMATCH)
            if journal_before is not None and (
                authority_after.authority_scope != journal_before.authority_scope
                or authority_after.authority_key != journal_before.authority_key
            ):
                return result(EvidenceReason.AUTHORITY_EDGE_SCOPE_MISMATCH)
        if not event_record.content_digest or not destination.content_digest:
            return result(EvidenceReason.SNAPSHOT_CONTENT_IDENTITY_MISSING)
        verification = EvaluationDispositionVerificationReceipt(
            event_id=intent.event_id,
            event_snapshot_key=intent.event_snapshot_key,
            event_snapshot_revision=event_record.revision,
            event_snapshot_digest=event_record.content_digest,
            event_snapshot_schema=event_record.schema,
            destination_snapshot_key=destination_key,
            destination_snapshot_revision=destination.revision,
            destination_snapshot_digest=destination.content_digest,
            destination_snapshot_schema=destination.schema,
            disposition_digest=evaluation_disposition_digest(intent),
            verifier="nsgablack.snapshot_store",
            verified_at=time.time(),
            metadata={
                "snapshot_backend": str(
                    getattr(self.snapshot_store, "backend", "unknown")
                ),
                "retention_owner": f"evaluation-evidence:{intent.event_id}",
            },
        )
        return result(
            EvidenceReason.VERIFIED,
            event_ref=event_identity,
            authority_before_ref=journal_before,
            authority_after_ref=authority_after,
            decision_carrier_ref=destination_identity,
            verification=verification,
        )
