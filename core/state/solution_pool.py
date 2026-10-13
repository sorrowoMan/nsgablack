"""Timestamped candidate regions backed by the shared SnapshotStore.

The pool owns candidate values, not membership, selection preferences or search
decisions. Units keep their own structures; orchestration exchanges references.
The clock never reuses a timestamp after rollback. Uncommitted records are not
enumerable by another search stage.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence
from uuid import uuid4

import numpy as np
from blackbase.context import SnapshotIdentity
from blackbase.types import CandidateBatch


POOL_SCHEMA = "nsgablack.solution_pool/v1"
BATCH_SCHEMA = "nsgablack.solution_pool_batch/v1"
MANIFEST_SCHEMA = "nsgablack.solution_pool_manifest/v1"


@dataclass(frozen=True)
class SolutionStamp:
    run_id: str
    sequence: int
    generation: int = 0
    attempt: int = 0

    def __post_init__(self):
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("solution timestamp requires a run identity")
        for name in ("sequence", "generation", "attempt"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"solution timestamp {name} must be a nonnegative integer")

    def as_dict(self):
        return dict(run_id=self.run_id, sequence=self.sequence,
                    generation=self.generation, attempt=self.attempt)

    @classmethod
    def from_dict(cls, value):
        return cls(**dict(value))


@dataclass(frozen=True)
class SolutionRef:
    pool_id: str
    record_id: str
    row: int
    candidate_token: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v for v in
               (self.pool_id, self.record_id, self.candidate_token)):
            raise ValueError("solution reference requires pool, record and candidate identities")
        if type(self.row) is not int or self.row < 0:
            raise ValueError("solution reference row must be nonnegative")

    def as_dict(self):
        return dict(pool_id=self.pool_id, record_id=self.record_id, row=self.row,
                    candidate_token=self.candidate_token)

    @classmethod
    def from_dict(cls, value):
        return cls(**dict(value))


@dataclass(frozen=True)
class _Record:
    record_id: str
    stamp: SolutionStamp
    region: str
    stage: str
    source: str
    snapshot: SnapshotIdentity
    tokens: tuple[str, ...]
    published: bool

    def as_dict(self):
        return dict(record_id=self.record_id, stamp=self.stamp.as_dict(),
                    region=self.region, stage=self.stage, source=self.source,
                    snapshot=self.snapshot.as_dict(), tokens=list(self.tokens),
                    published=self.published)

    @classmethod
    def from_dict(cls, value):
        data = dict(value)
        data["stamp"] = SolutionStamp.from_dict(data["stamp"])
        data["snapshot"] = SnapshotIdentity.from_dict(data["snapshot"])
        data["tokens"] = tuple(data["tokens"])
        if type(data["published"]) is not bool:
            raise ValueError("pool publication flag must be boolean")
        return cls(**data)


class SolutionPool:
    """One run's named candidate regions; all large values live in Snapshots.

    Public selection includes only published records. Draft access uses an
    explicit reference and ``allow_pending=True`` inside the owning attempt.
    Pool selection applies no numerical deduplication or implicit best policy.
    """
    name = "solver.solution_pool"

    def __init__(self, snapshots, *, run_id: str | None = None):
        self.snapshots = snapshots
        self.pool_id = uuid4().hex
        self.run_id = run_id or f"pool-run:{uuid4().hex}"
        self._sequence = 0
        self._records: dict[str, _Record] = {}
        self._inputs: dict[str, tuple[tuple[SolutionRef, ...], int]] = {}
        self._in_attempt = False
        self._manifest: SnapshotIdentity | None = None
        self._prepared_manifest: SnapshotIdentity | None = None

    @property
    def timestamp(self):
        return SolutionStamp(self.run_id, self._sequence)

    @property
    def record_count(self):
        return len(self._records)

    def reset(self, run_id):
        self.run_id = str(run_id)
        SolutionStamp(self.run_id, 0)
        self._sequence = 0
        self._records = {}
        self._inputs = {}
        self._manifest = self._prepared_manifest = None
        self._in_attempt = False

    def begin_attempt(self):
        if self._in_attempt:
            raise RuntimeError("solution pool attempt already active")
        self._in_attempt = True

    def _assert_unprepared(self):
        if self._prepared_manifest is not None:
            raise RuntimeError("solution pool publication is frozen")

    def put(self, batch: CandidateBatch, *, region="main", stage="initial",
            source="control", generation=0, attempt=0, feedback=None, provenance=None):
        self._assert_unprepared()
        if not isinstance(batch, CandidateBatch):
            raise TypeError("solution pool requires CandidateBatch")
        if any(not isinstance(v, str) or not v for v in (region, stage, source)):
            raise ValueError("pool region, stage and source must be nonempty")
        tokens = tuple(batch.candidate_tokens)
        if any(not isinstance(t, str) or not t for t in tokens):
            raise ValueError("pool candidates require explicit identities")
        if not tokens:
            return ()
        if feedback is not None and feedback.candidate_count != len(tokens):
            raise ValueError("pool feedback must align with candidates")
        lineage = None if provenance is None else [dict(v) for v in provenance]
        if lineage is not None and (len(lineage) != len(tokens) or
                any(v.get("candidate_token") != t for v, t in zip(lineage, tokens))):
            raise ValueError("pool provenance must align with candidate tokens")
        self._sequence += 1
        stamp = SolutionStamp(self.run_id, self._sequence, int(generation), int(attempt))
        record_id = uuid4().hex
        raw = None if feedback is None else dict(
            objectives=feedback.raw_objectives.tolist(),
            violations=feedback.raw_violations.tolist())
        data = dict(pool_id=self.pool_id, record_id=record_id, stamp=stamp.as_dict(),
                    region=region, stage=stage, source=source,
                    batch=batch.as_dict(), raw_feedback=raw, provenance=lineage)
        handle = self.snapshots.write(data, key=f"solution-pool/{self.pool_id}/{record_id}",
                                      schema=BATCH_SCHEMA, write_once=True)
        self._records[record_id] = _Record(record_id, stamp, region, stage, source,
                                          handle.identity(), tokens, not self._in_attempt)
        return tuple(SolutionRef(self.pool_id, record_id, i, t) for i, t in enumerate(tokens))

    def _record(self, ref, *, allow_pending=False):
        if not isinstance(ref, SolutionRef) or ref.pool_id != self.pool_id:
            raise ValueError("solution reference belongs to another pool")
        record = self._records.get(ref.record_id)
        if record is None or (not record.published and not allow_pending):
            raise ValueError("solution reference is unavailable or uncommitted")
        if ref.row >= len(record.tokens) or record.tokens[ref.row] != ref.candidate_token:
            raise ValueError("solution reference token does not match its row")
        return record

    def _payload(self, record):
        if record.snapshot.schema != BATCH_SCHEMA:
            raise ValueError("unsupported solution pool batch snapshot")
        data = self.snapshots.read_verified(record.snapshot).data
        for name, expected in (("pool_id", self.pool_id), ("record_id", record.record_id),
                               ("stamp", record.stamp.as_dict()), ("region", record.region),
                               ("stage", record.stage), ("source", record.source)):
            if data.get(name) != expected:
                raise ValueError(f"solution snapshot {name} disagrees with its index")
        batch = CandidateBatch.from_dict(data["batch"])
        if tuple(batch.candidate_tokens) != record.tokens:
            raise ValueError("solution snapshot tokens disagree with its index")
        lineage = data.get("provenance")
        if lineage is not None and (len(lineage) != len(record.tokens) or
                any(v.get("candidate_token") != t for v, t in zip(lineage, record.tokens))):
            raise ValueError("solution snapshot provenance disagrees with its index")
        return data, batch

    def read(self, refs: Sequence[SolutionRef], *, allow_pending=False):
        states, tokens, rows, loaded = [], [], [], {}
        for ref in tuple(refs):
            record = self._record(ref, allow_pending=allow_pending)
            if record.record_id not in loaded:
                loaded[record.record_id] = self._payload(record)[1]
            batch = loaded[record.record_id]
            states.append(batch.semantic_states[ref.row])
            tokens.append(ref.candidate_token)
            rows.append(batch.numeric_matrix[ref.row])
        if not rows:
            raise ValueError("reading an empty solution selection has no candidate dimension")
        return CandidateBatch(tuple(states), np.stack(rows), tuple(tokens))

    def read_provenance(self, refs, *, allow_pending=False):
        loaded, result = {}, []
        for ref in tuple(refs):
            record = self._record(ref, allow_pending=allow_pending)
            if record.record_id not in loaded:
                loaded[record.record_id] = self._payload(record)[0].get("provenance")
            values = loaded[record.record_id]
            result.append(None if values is None else dict(values[ref.row]))
        return tuple(result)

    def select(self, *, at: SolutionStamp | None = None, region="main", stage="accepted",
               source: str | None = None, limit: int | None = None):
        if at is not None and (at.run_id != self.run_id or at.sequence > self._sequence):
            raise ValueError("pool selection timestamp is outside this run")
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError("pool selection limit must be nonnegative")
        refs = []
        for record in self._records.values():
            if (not record.published or record.region != region
                    or (stage is not None and record.stage != stage)
                    or (source is not None and record.source != source)
                    or (at is not None and record.stamp.sequence > at.sequence)):
                continue
            refs.extend(SolutionRef(self.pool_id, record.record_id, i, t)
                        for i, t in enumerate(record.tokens))
        return tuple(refs if limit is None else refs[:limit])

    def bind_input(self, refs):
        self._assert_unprepared()
        values = tuple(refs)
        for ref in values:
            self._record(ref)
        key = uuid4().hex
        self._inputs[key] = (values, 0)
        return key

    def input_remaining(self, key):
        refs, cursor = self._inputs[key]
        return len(refs) - cursor

    def stamp_for(self, ref):
        return self._record(ref).stamp

    def take_input(self, key):
        self._assert_unprepared()
        refs, cursor = self._inputs[key]
        if cursor >= len(refs):
            raise ValueError("solution pool input exhausted; no implicit random fallback")
        self._inputs[key] = (refs, cursor + 1)
        return refs[cursor]

    def take_inputs(self, key, count):
        self._assert_unprepared()
        refs, cursor = self._inputs[key]
        if type(count) is not int or count < 0 or cursor + count > len(refs):
            raise ValueError("solution pool input exhausted or invalid count")
        self._inputs[key] = (refs, cursor + count)
        return refs[cursor:cursor + count]

    def settle_input(self, key, proposed_count, accepted_indices):
        """Keep denied seeds available; indexes refer to this intake proposal."""
        self._assert_unprepared()
        refs, cursor = self._inputs[key]
        start = cursor - proposed_count
        indices = tuple(accepted_indices)
        if (type(proposed_count) is not int or start < 0 or
                any(type(i) is not int or not 0 <= i < proposed_count for i in indices) or
                len(set(indices)) != len(indices)):
            raise ValueError("pool intake disposition is outside its original selection")
        consumed = refs[start:cursor]
        selected = set(indices)
        accepted = tuple(consumed[i] for i in indices)
        remaining = tuple(r for i, r in enumerate(consumed) if i not in selected)
        self._inputs[key] = (refs[:start] + accepted + remaining + refs[cursor:], start + len(accepted))

    def prepare_publication(self):
        self._assert_unprepared()
        records = [replace(r, published=True) if r.stage == "accepted" else r
                   for r in self._records.values() if r.published or r.stage == "accepted"]
        state = self._index_state(records)
        handle = self.snapshots.write(state, key=f"solution-pool/{self.pool_id}/manifest/{uuid4().hex}",
                                      schema=MANIFEST_SCHEMA, write_once=True)
        self.snapshots.read_verified(handle.identity())
        self._prepared_manifest = handle.identity()
        return self._prepared_manifest.as_dict()

    def commit_publication(self):
        if self._prepared_manifest is None:
            raise RuntimeError("solution pool publication was not prepared")
        self._records = {k: replace(r, published=True) if r.stage == "accepted" else r
                         for k, r in self._records.items() if r.published or r.stage == "accepted"}
        self._manifest, self._prepared_manifest = self._prepared_manifest, None
        self._in_attempt = False

    def publication_ref(self):
        identity = self._prepared_manifest or self._manifest
        return None if identity is None else identity.as_dict()

    def restore_publication(self, value):
        identity = SnapshotIdentity.from_dict(value)
        if identity.schema != MANIFEST_SCHEMA:
            raise ValueError("unsupported solution pool manifest")
        state = self.snapshots.read_verified(identity).data
        temporary = SolutionPool(self.snapshots)
        temporary._restore_index(state)
        for record in temporary._records.values():
            temporary._payload(record)
        high_water = self._sequence if (self.pool_id, self.run_id) == (temporary.pool_id, temporary.run_id) else 0
        self._restore_index(temporary._index_state())
        self._sequence = max(high_water, self._sequence)
        self._manifest = identity
        self._prepared_manifest = None
        self._in_attempt = False

    def _index_state(self, records=None):
        return dict(schema=POOL_SCHEMA, pool_id=self.pool_id, run_id=self.run_id,
                    sequence=self._sequence,
                    records=[r.as_dict() for r in (self._records.values() if records is None else records)],
                    inputs={k: dict(refs=[r.as_dict() for r in refs], cursor=c)
                            for k, (refs, c) in self._inputs.items()})

    def _restore_index(self, state):
        if state.get("schema") != POOL_SCHEMA:
            raise ValueError("unsupported solution pool state")
        SolutionStamp(state["run_id"], state["sequence"])
        if not isinstance(state["pool_id"], str) or not state["pool_id"]:
            raise ValueError("solution pool identity must be nonempty")
        records = [_Record.from_dict(v) for v in state["records"]]
        if (len({r.record_id for r in records}) != len(records)
                or any(r.stamp.run_id != state["run_id"] or r.stamp.sequence > state["sequence"] for r in records)
                or any(a.stamp.sequence >= b.stamp.sequence for a, b in zip(records, records[1:]))):
            raise ValueError("solution pool records disagree with the runtime clock")
        inputs = {}
        for key, value in state["inputs"].items():
            refs = tuple(SolutionRef.from_dict(v) for v in value["refs"])
            cursor = value["cursor"]
            if type(cursor) is not int or not 0 <= cursor <= len(refs):
                raise ValueError("invalid solution pool input cursor")
            inputs[key] = refs, cursor
        old = (self.pool_id, self.run_id, self._sequence, self._records, self._inputs)
        try:
            self.pool_id, self.run_id = state["pool_id"], state["run_id"]
            self._sequence = state["sequence"]
            self._records = {r.record_id: r for r in records}
            self._inputs = inputs
            for refs, _ in inputs.values():
                for ref in refs:
                    self._record(ref)
        except BaseException:
            self.pool_id, self.run_id, self._sequence, self._records, self._inputs = old
            raise

    def snapshot_step_state(self):
        return dict(index=self._index_state(), manifest=self._manifest,
                    prepared=self._prepared_manifest, in_attempt=self._in_attempt)

    def restore_step_state(self, state):
        high_water = self._sequence if (self.pool_id, self.run_id) == (
            state["index"]["pool_id"], state["index"]["run_id"]) else 0
        # Validation uses the baseline index. Pending records from this failed
        # attempt are removed; a timestamp is never reused in the same run.
        self._restore_index(state["index"])
        self._sequence = max(high_water, self._sequence)
        self._manifest, self._prepared_manifest = state["manifest"], state["prepared"]
        self._in_attempt = state["in_attempt"]

    def reject_attempt(self, baseline):
        """Rewind intake without invalidating a controller's new selection IDs.

        Normal rejection may retain Adapter scheduling/RNG state. Newly bound
        selections contain only previously published refs, so retain their IDs
        with an unconsumed cursor. Exceptions instead use full rollback.
        """
        prior_keys = set(baseline["index"]["inputs"])
        created = {k: refs for k, (refs, _) in self._inputs.items() if k not in prior_keys}
        self.restore_step_state(baseline)
        for key, refs in created.items():
            for ref in refs:
                self._record(ref)
            self._inputs[key] = refs, 0

    def commit_step_state(self, state):
        return None

    def step_transaction_children(self):
        return ()

    def get_state(self):
        if self._in_attempt:
            raise RuntimeError("checkpoint cannot capture an unfinished solution pool attempt")
        state = self._index_state()
        state["payloads"] = {r.record_id: dict(self._payload(r)[0]) for r in self._records.values()}
        return state

    def set_state(self, state):
        # Portable, explicit value restore; no services or object graphs copied.
        data = dict(state)
        temporary = SolutionPool(self.snapshots)
        restored = []
        for value in data["records"]:
            record = _Record.from_dict(value)
            payload = data["payloads"][record.record_id]
            handle = self.snapshots.write(payload, key=f"solution-pool/restore/{uuid4().hex}",
                                          schema=BATCH_SCHEMA, write_once=True)
            if handle.content_digest != record.snapshot.content_digest:
                raise ValueError("checkpoint solution payload digest disagrees with its reference")
            restored.append(replace(record, snapshot=handle.identity()).as_dict())
        data["records"] = restored
        temporary._restore_index(data)
        for record in temporary._records.values():
            temporary._payload(record)
        baseline = self.snapshot_step_state()
        try:
            self._restore_index(temporary._index_state())
            self._manifest = self._prepared_manifest = None
            self._in_attempt = False
            self.prepare_publication()
            self.commit_publication()
        except BaseException:
            self.restore_step_state(baseline)
            raise


__all__ = ["SolutionPool", "SolutionRef", "SolutionStamp"]
