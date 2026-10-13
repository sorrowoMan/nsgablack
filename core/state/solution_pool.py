"""Timestamped candidate regions backed by the shared SnapshotStore.

The pool owns candidate values, not membership, selection preferences or search
decisions. Units keep their own structures; orchestration exchanges references.
The clock never reuses a timestamp after rollback. Uncommitted records are not
enumerable by another search stage.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence
from uuid import uuid4

import numpy as np
from blackbase.context import SnapshotIdentity
from blackbase.types import CandidateBatch
from .pool_retention import PoolRetentionPolicy


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
    rows: tuple[int, ...] | None = None

    @property
    def available_rows(self):
        return tuple(range(len(self.tokens))) if self.rows is None else self.rows

    def as_dict(self):
        return dict(record_id=self.record_id, stamp=self.stamp.as_dict(),
                    region=self.region, stage=self.stage, source=self.source,
                    snapshot=self.snapshot.as_dict(), tokens=list(self.tokens),
                    published=self.published, rows=None if self.rows is None else list(self.rows))

    @classmethod
    def from_dict(cls, value):
        data = dict(value)
        data["stamp"] = SolutionStamp.from_dict(data["stamp"])
        data["snapshot"] = SnapshotIdentity.from_dict(data["snapshot"])
        data["tokens"] = tuple(data["tokens"])
        data["rows"] = None if data.get("rows") is None else tuple(data["rows"])
        rows = data["rows"]
        if rows is not None and (not rows or len(rows) != len(data["tokens"])
                                 or any(type(i) is not int or i < 0 for i in rows)
                                 or tuple(sorted(set(rows))) != rows):
            raise ValueError("invalid compacted solution rows")
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
        self.retention_policy: PoolRetentionPolicy | None = None
        self._retention_step = 0
        self._last_used: dict[str, dict[int, int]] = {}
        self._owners: dict[str, tuple[SolutionRef, ...]] = {}
        self._publications: list[dict] = []
        self._garbage: dict[str, SnapshotIdentity] = {}
        self._prepared_index = None
        self._retention_staged = False

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
        self._retention_step = 0
        self._last_used, self._owners, self._garbage = {}, {}, {}
        self._publications = []
        self._prepared_index = None
        self._retention_staged = False

    def begin_attempt(self):
        if self._in_attempt:
            raise RuntimeError("solution pool attempt already active")
        self._in_attempt = True
        self._retention_staged = False

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
        self._last_used[record_id] = {i: self._retention_step + int(self._in_attempt) for i in range(len(tokens))}
        return tuple(SolutionRef(self.pool_id, record_id, i, t) for i, t in enumerate(tokens))

    def _record(self, ref, *, allow_pending=False):
        if not isinstance(ref, SolutionRef) or ref.pool_id != self.pool_id:
            raise ValueError("solution reference belongs to another pool")
        record = self._records.get(ref.record_id)
        if record is None or (not record.published and not allow_pending):
            raise ValueError("solution reference is unavailable or uncommitted")
        if ref.row not in record.available_rows:
            raise ValueError("solution reference row was retired")
        if record.tokens[record.available_rows.index(ref.row)] != ref.candidate_token:
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
        rows = tuple(data.get("rows", range(len(record.tokens))))
        if rows != record.available_rows or tuple(batch.candidate_tokens) != record.tokens:
            raise ValueError("solution snapshot tokens disagree with its index")
        lineage = data.get("provenance")
        if lineage is not None and (len(lineage) != len(rows) or
                any(v.get("candidate_token") != t for v, t in zip(lineage, batch.candidate_tokens))):
            raise ValueError("solution snapshot provenance disagrees with its index")
        return data, batch

    def read(self, refs: Sequence[SolutionRef], *, allow_pending=False):
        states, tokens, rows, loaded = [], [], [], {}
        for ref in tuple(refs):
            record = self._record(ref, allow_pending=allow_pending)
            if record.record_id not in loaded:
                loaded[record.record_id] = self._payload(record)[1]
            batch = loaded[record.record_id]
            position = record.available_rows.index(ref.row)
            states.append(batch.semantic_states[position])
            tokens.append(ref.candidate_token)
            rows.append(batch.numeric_matrix[position])
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
            result.append(None if values is None else dict(values[record.available_rows.index(ref.row)]))
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
                        for i, t in zip(record.available_rows, record.tokens))
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

    def set_retention_policy(self, policy: PoolRetentionPolicy | None):
        self._assert_unprepared()
        if self._in_attempt:
            raise RuntimeError("configure pool retention outside a step attempt")
        if policy is not None and not isinstance(policy, PoolRetentionPolicy):
            raise TypeError("expected PoolRetentionPolicy or None")
        if policy != self.retention_policy and self._manifest is not None:
            raise RuntimeError("configure retention before the first pool publication")
        self.retention_policy = policy

    def retain(self, owner: str, refs):
        """Replace one consumer's explicit roots; duplicate memberships are valid."""
        self._assert_unprepared()
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("pool retention owner must be nonempty")
        if owner.startswith("adapter/"):
            raise ValueError("adapter/ retention roots belong to the control plane")
        values = tuple(refs)
        for ref in values:
            self._record(ref, allow_pending=True)
        self._owners[owner] = values

    def release(self, owner: str):
        self._assert_unprepared()
        self._owners.pop(owner, None)

    def replace_roots(self, prefix: str, roots: Mapping[str, Sequence[SolutionRef]]):
        """Atomically replace one named family's roots without guessing object graphs."""
        self._assert_unprepared()
        values = {k: tuple(v) for k, v in roots.items()}
        if not prefix or any(not isinstance(k, str) or not k.startswith(prefix) for k in values):
            raise ValueError("retention roots must belong to their declared family")
        for refs in values.values():
            for ref in refs:
                self._record(ref, allow_pending=True)
        self._owners = {**{k: v for k, v in self._owners.items() if not k.startswith(prefix)}, **values}

    def refs_for_tokens(self, tokens):
        """Conservative roots for Units that retain tokens without exact refs.

        Protect all accepted versions of a live token, never match by numbers.
        """
        values = tuple(tokens)
        if any(not isinstance(t, str) or not t for t in values):
            raise ValueError("live Unit candidates require explicit tokens for retention")
        requested = set(values)
        result = tuple(SolutionRef(self.pool_id, r.record_id, i, token)
                     for r in self._records.values() if r.published or r.stage == "accepted"
                     for i, token in zip(r.available_rows, r.tokens) if token in requested)
        if requested - {r.candidate_token for r in result}:
            raise ValueError("live Unit token has no retained pool candidate")
        return result

    def stage_retention_step(self):
        """Prune/compact as part of the pending semantic commit, never delete yet."""
        self._assert_unprepared()
        if self.retention_policy is None or not self._in_attempt or self._retention_staged:
            raise RuntimeError("pool retention requires one active, unstaged step")
        self._retention_staged = True
        self._retention_step += 1
        # Consumed references do not remain hidden lifetime roots. Selection IDs
        # remain valid for controllers that query an exhausted input later.
        self._inputs = {k: (refs[cursor:], 0) for k, (refs, cursor) in self._inputs.items()}
        protected = {(r.record_id, r.row) for refs in self._owners.values() for r in refs}
        protected.update((r.record_id, r.row) for refs, _ in self._inputs.values() for r in refs)
        for record in tuple(self._records.values()):
            if not record.published and record.stage != "accepted":
                continue
            ages = self._last_used[record.record_id]
            for row in record.available_rows:
                if (record.record_id, row) in protected:
                    ages[row] = self._retention_step
            keep = tuple(i for i in record.available_rows
                         if self._retention_step - ages[i] < self.retention_policy.idle_steps)
            if keep == record.available_rows:
                continue
            self._garbage[record.snapshot.key] = record.snapshot
            if not keep:
                del self._records[record.record_id]
                del self._last_used[record.record_id]
                continue
            data, batch = self._payload(record)
            positions = tuple(record.available_rows.index(i) for i in keep)
            compact = batch.subset(positions)
            payload = {**data, "rows": list(keep), "batch": compact.as_dict()}
            if data.get("provenance") is not None:
                payload["provenance"] = [data["provenance"][i] for i in positions]
            if data.get("raw_feedback") is not None:
                payload["raw_feedback"] = {name: [values[i] for i in positions]
                                           for name, values in data["raw_feedback"].items()}
            handle = self.snapshots.write(payload,
                key=f"solution-pool/{self.pool_id}/compact/{record.record_id}/{uuid4().hex}",
                schema=BATCH_SCHEMA, write_once=True)
            self._records[record.record_id] = replace(record, snapshot=handle.identity(), rows=keep,
                tokens=tuple(record.tokens[i] for i in positions))
            self._last_used[record.record_id] = {i: ages[i] for i in keep}

    def _remember_publication(self, identity):
        if self.retention_policy is None:
            return
        if not any(p["manifest"] == identity.as_dict() for p in self._publications):
            self._publications.append(dict(manifest=identity.as_dict(),
                values=[r.snapshot.as_dict() for r in self._records.values()]))

    def pin_publication(self, owner: str, identity=None):
        """Retain a historical restore root and its full transitive value closure.

        Physical store leases are local to that store, not portable components.
        Call outside a step; callers release the returned identity explicitly.
        """
        if self._in_attempt:
            raise RuntimeError("publication leases must be changed outside a step")
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("publication pin owner must be nonempty")
        if owner == "authority-pending":
            raise ValueError("authority-pending is a reserved publication lease")
        value = identity or self.publication_ref()
        return self._pin_publication(owner, value)

    def _pin_publication(self, owner, value):
        root = SnapshotIdentity.from_dict(value)
        state = self.snapshots.read_verified(root).data
        if root.schema != MANIFEST_SCHEMA or state.get("pool_id") != self.pool_id:
            raise ValueError("publication pin belongs to another pool")
        values = [_Record.from_dict(r).snapshot for r in state["records"]]
        # Each publication needs its own lease: two roots may share values.
        pin_owner = f"solution-pool:{self.pool_id}:{owner}:{root.key}"
        for item in (*values, root):
            self.snapshots.read_verified(item)
        for item in (*values, root):
            self.snapshots.pin(item.key, owner=pin_owner)
        return root.as_dict()

    def unpin_publication(self, owner: str, identity):
        if self._in_attempt:
            raise RuntimeError("publication leases must be changed outside a step")
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("publication pin owner must be nonempty")
        if owner == "authority-pending":
            raise ValueError("authority-pending is a reserved publication lease")
        self._unpin_publication(owner, identity)

    def _unpin_publication(self, owner, identity):
        root = SnapshotIdentity.from_dict(identity)
        state = self.snapshots.read_verified(root).data
        if root.schema != MANIFEST_SCHEMA or state.get("pool_id") != self.pool_id:
            raise ValueError("publication pin belongs to another pool")
        pin_owner = f"solution-pool:{self.pool_id}:{owner}:{root.key}"
        for item in (*(_Record.from_dict(r).snapshot for r in state["records"]), root):
            self.snapshots.unpin(item.key, owner=pin_owner)

    def protect_prepared_publication(self):
        """Keep the value closure readable across an uncertain Authority commit."""
        if self.retention_policy is not None and self._prepared_manifest is not None:
            self._pin_publication("authority-pending", self._prepared_manifest.as_dict())

    def release_prepared_publication(self):
        """Release only when the caller knows no durable commit intent exists."""
        if self.retention_policy is not None and self._prepared_manifest is not None:
            self._unpin_publication("authority-pending", self._prepared_manifest.as_dict())

    def collect_garbage(self):
        """Delete only after commit; retain pinned closures and retry failed deletes."""
        if self._in_attempt or self._prepared_manifest is not None:
            raise RuntimeError("physical pool collection requires a committed publication")
        if self.retention_policy is None:
            return dict(deleted=0, deferred=0, errors=[])
        protected = {r.snapshot.key for r in self._records.values()}
        retained = []
        errors = []
        window = self.retention_policy.retained_publications
        for i, publication in enumerate(self._publications):
            root = SnapshotIdentity.from_dict(publication["manifest"])
            # A root in the committed index no longer needs its temporary CAS
            # lease. Failed/unresolved roots are absent here and stay pinned.
            try:
                if self.snapshots.read(root.key) is not None:
                    self._unpin_publication("authority-pending", root.as_dict())
            except Exception as exc:
                errors.append(dict(key=root.key, error_type=type(exc).__name__, message=str(exc)))
            observed = self.snapshots.read(root.key)
            if i >= len(self._publications)-window or (observed is not None and observed.pinned):
                retained.append(publication)
                protected.add(root.key)
                protected.update(v["key"] for v in publication["values"])
            else:
                self._garbage[root.key] = root
                for value in publication["values"]:
                    item = SnapshotIdentity.from_dict(value)
                    self._garbage[item.key] = item
        self._publications = retained
        deleted = 0
        for key, identity in tuple(self._garbage.items()):
            if key in protected:
                continue
            try:
                observed = self.snapshots.read(key)
                if observed is not None:
                    value = self.snapshots.read_verified(identity).data
                    if value.get("pool_id") != self.pool_id:
                        raise ValueError("pool garbage snapshot belongs to another pool")
                    if observed.pinned:
                        continue
                    self.snapshots.delete(key)
                    deleted += 1
                del self._garbage[key]
            except Exception as exc:
                errors.append(dict(key=key, error_type=type(exc).__name__, message=str(exc)))
        return dict(deleted=deleted, deferred=len(self._garbage), errors=errors)

    def prepare_publication(self):
        self._assert_unprepared()
        for r in self._records.values():
            if self.retention_policy is not None and not r.published and r.stage != "accepted":
                self._garbage[r.snapshot.key] = r.snapshot
        records = [replace(r, published=True) if r.stage == "accepted" else r
                   for r in self._records.values() if r.published or r.stage == "accepted"]
        state = self._index_state(records)
        SolutionPool(self.snapshots)._restore_index(state)
        handle = self.snapshots.write(state, key=f"solution-pool/{self.pool_id}/manifest/{uuid4().hex}",
                                      schema=MANIFEST_SCHEMA, write_once=True)
        self.snapshots.read_verified(handle.identity())
        self._prepared_manifest = handle.identity()
        self._prepared_index = state
        return self._prepared_manifest.as_dict()

    def commit_publication(self):
        if self._prepared_manifest is None:
            raise RuntimeError("solution pool publication was not prepared")
        self._restore_index(self._prepared_index)
        self._manifest, self._prepared_manifest = self._prepared_manifest, None
        self._remember_publication(self._manifest)
        self._prepared_index = None
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
        self._remember_publication(identity)
        self._prepared_manifest = None
        self._prepared_index = None
        self._in_attempt = False

    def _index_state(self, records=None):
        return dict(schema=POOL_SCHEMA, pool_id=self.pool_id, run_id=self.run_id,
                    sequence=self._sequence,
                    records=[r.as_dict() for r in (self._records.values() if records is None else records)],
                    inputs={k: dict(refs=[r.as_dict() for r in refs], cursor=c)
                            for k, (refs, c) in self._inputs.items()},
                    retention=dict(policy=None if self.retention_policy is None else dict(
                        idle_steps=self.retention_policy.idle_steps,
                        retained_publications=self.retention_policy.retained_publications),
                        step=self._retention_step,
                        last_used={r.record_id: {str(i): self._last_used[r.record_id][i] for i in r.available_rows}
                                   for r in (self._records.values() if records is None else records)},
                        owners={k: [r.as_dict() for r in refs] for k, refs in self._owners.items()},
                        publications=[dict(manifest=dict(p["manifest"]), values=[dict(v) for v in p["values"]])
                                      for p in self._publications],
                        garbage=[s.as_dict() for s in self._garbage.values()]))

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
        retention = dict(state.get("retention", {}))
        policy = retention.get("policy")
        policy = None if policy is None else PoolRetentionPolicy(**policy)
        clock = retention.get("step", 0)
        if type(clock) is not int or clock < 0:
            raise ValueError("invalid pool retention step")
        ages = retention.get("last_used", {r.record_id: {str(i): clock for i in r.available_rows} for r in records})
        if set(ages) != {r.record_id for r in records}:
            raise ValueError("pool retention ages must align with records")
        last_used = {}
        for record in records:
            row_ages = {int(k): v for k, v in ages[record.record_id].items()}
            if (set(row_ages) != set(record.available_rows)
                    or any(type(v) is not int or not 0 <= v <= clock+1 for v in row_ages.values())):
                raise ValueError("invalid pool candidate last-use steps")
            last_used[record.record_id] = row_ages
        owners = {k: tuple(SolutionRef.from_dict(r) for r in refs)
                  for k, refs in retention.get("owners", {}).items()}
        if any(not isinstance(k, str) or not k.strip() for k in owners):
            raise ValueError("invalid pool retention owner")
        publications = []
        for value in retention.get("publications", ()):
            root = SnapshotIdentity.from_dict(value["manifest"])
            values = [SnapshotIdentity.from_dict(v) for v in value["values"]]
            if root.schema != MANIFEST_SCHEMA or root.store_scope != self.snapshots.store_scope:
                raise ValueError("pool publication history scope/schema mismatch")
            if any(v.schema != BATCH_SCHEMA or v.store_scope != self.snapshots.store_scope for v in values):
                raise ValueError("pool publication value scope/schema mismatch")
            publications.append(dict(manifest=root.as_dict(), values=[v.as_dict() for v in values]))
        garbage = [SnapshotIdentity.from_dict(v) for v in retention.get("garbage", ())]
        if any(v.schema not in {BATCH_SCHEMA, MANIFEST_SCHEMA} or v.store_scope != self.snapshots.store_scope for v in garbage):
            raise ValueError("pool garbage scope/schema mismatch")
        old = (self.pool_id, self.run_id, self._sequence, self._records, self._inputs,
               self.retention_policy, self._retention_step, self._last_used, self._owners, self._publications, self._garbage)
        try:
            self.pool_id, self.run_id = state["pool_id"], state["run_id"]
            self._sequence = state["sequence"]
            self._records = {r.record_id: r for r in records}
            self._inputs = inputs
            self.retention_policy, self._retention_step = policy, clock
            self._last_used, self._owners, self._publications = last_used, owners, publications
            self._garbage = {v.key: v for v in garbage}
            for refs, _ in inputs.values():
                for ref in refs:
                    self._record(ref)
            for refs in owners.values():
                for ref in refs:
                    self._record(ref, allow_pending=True)
        except BaseException:
            (self.pool_id, self.run_id, self._sequence, self._records, self._inputs,
             self.retention_policy, self._retention_step, self._last_used, self._owners, self._publications, self._garbage) = old
            raise

    def snapshot_step_state(self):
        return dict(index=self._index_state(), manifest=self._manifest,
                    prepared=self._prepared_manifest, in_attempt=self._in_attempt,
                    prepared_index=copy.deepcopy(self._prepared_index), retention_staged=self._retention_staged)

    def restore_step_state(self, state):
        # Writes made by a failed attempt are known local immutable snapshots.
        # Queue them for later cleanup; never delete the baseline while rolling
        # back. Cleanup bookkeeping, like timestamp high-water, is not undone.
        discarded = dict(self._garbage)
        discarded.update((r.snapshot.key, r.snapshot) for r in self._records.values())
        if self._prepared_manifest is not None:
            discarded[self._prepared_manifest.key] = self._prepared_manifest
        baseline_keys = {r["snapshot"]["key"] for r in state["index"]["records"]}
        baseline_keys.update(v.key for v in (state["manifest"], state["prepared"]) if v is not None)
        high_water = self._sequence if (self.pool_id, self.run_id) == (
            state["index"]["pool_id"], state["index"]["run_id"]) else 0
        # Validation uses the baseline index. Pending records from this failed
        # attempt are removed; a timestamp is never reused in the same run.
        self._restore_index(state["index"])
        if self.retention_policy is not None:
            self._garbage.update((k, v) for k, v in discarded.items() if k not in baseline_keys)
        self._sequence = max(high_water, self._sequence)
        self._manifest, self._prepared_manifest = state["manifest"], state["prepared"]
        self._in_attempt = state["in_attempt"]
        self._prepared_index = copy.deepcopy(state.get("prepared_index"))
        self._retention_staged = state.get("retention_staged", False)

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
        return self.collect_garbage() if self.retention_policy is not None and not self._in_attempt else None

    def step_transaction_children(self):
        return ()

    def get_state(self):
        if self._in_attempt:
            raise RuntimeError("checkpoint cannot capture an unfinished solution pool attempt")
        state = self._index_state()
        # Backend garbage and old physical publication leases do not migrate
        # to another store. This checkpoint carries the current values itself.
        state["retention"]["publications"] = []
        state["retention"]["garbage"] = []
        state["payloads"] = {r.record_id: dict(self._payload(r)[0]) for r in self._records.values()}
        return state

    def set_state(self, state):
        # Portable, explicit value restore; no services or object graphs copied.
        data = dict(state)
        data["retention"] = {**data.get("retention", {}), "publications": [], "garbage": []}
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
