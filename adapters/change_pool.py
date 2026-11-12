"""Call-scoped pool views and local drafts at existing owner update seams.

Selections keep exact version references. Candidate values are loaded only when
requested, and materialized inputs are reported to the owning change invocation.
Reads never publish candidates. Named drafts detach to existing member plans;
only the owning control-plane transaction can publish those membership changes.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

import numpy as np
from blackbase.wire import freeze_wire_mapping, thaw_wire_mapping

from ..core.state.solution_pool import SolutionPool, SolutionRef


_choosing_pool = ContextVar("nsgablack_pure_pool_choice", default=False)
_NO_MEMBER_DEFAULT = object()


@contextmanager
def _pure_pool_choice():
    token = _choosing_pool.set(True)
    try:
        yield
    finally:
        _choosing_pool.reset(token)


def _refs(values):
    if isinstance(values, (str, bytes)):
        raise TypeError("change selection requires SolutionRef values")
    result = tuple(values)
    if any(not isinstance(ref, SolutionRef) for ref in result):
        raise TypeError("change selection requires SolutionRef values")
    return result


def _readonly(values):
    matrix = np.asarray(values)
    if matrix.dtype.kind not in "biuf":
        raise ValueError("change pool values must be real numeric data")
    return np.frombuffer(matrix.tobytes(), dtype=matrix.dtype).reshape(matrix.shape)


@dataclass(frozen=True)
class PoolOutput:
    """Request delivery of an accepted proposal to a named pool collection."""

    name: str
    create: bool = field(default=False, kw_only=True)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("pool output name must be nonempty")
        if type(self.create) is not bool:
            raise TypeError("pool output create must be boolean")


@dataclass(frozen=True, init=False)
class PoolEdit:
    """An exact member plan for an ordinary collection.

    Helpers fold add/remove/trim into this one primitive. Declaring a plan
    changes no membership; the control plane applies it only on admission.
    Selection outputs may also freeze an absent target by pool ID and name.
    """

    name: str
    members: tuple[SolutionRef, ...]
    expected: object

    def __init__(self, name, members, *, expected):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("pool edit name must be nonempty")
        descriptor = self._validate_expected(expected)
        if descriptor["name"] != name:
            raise ValueError("pool edit descriptor names another collection")
        refs = _refs(members)
        if any(ref.pool_id != descriptor["pool_id"] for ref in refs):
            raise ValueError("pool edit members belong to another pool")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "members", refs)
        object.__setattr__(self, "expected", freeze_wire_mapping(descriptor))

    @staticmethod
    def _validate_expected(expected):
        if isinstance(expected, Mapping) and "absent" in expected:
            if (set(expected) != {"pool_id", "name", "absent"}
                    or expected["absent"] is not True
                    or any(not isinstance(expected[key], str) or not expected[key].strip()
                           for key in ("pool_id", "name"))):
                raise ValueError("invalid absent pool edit target")
            return dict(expected)
        return SolutionPool.validate_subpool_descriptor(expected)

    def as_dict(self):
        return {"name": self.name, "members": [ref.as_dict() for ref in self.members],
                "expected": thaw_wire_mapping(self.expected)}


@dataclass(frozen=True, init=False)
class ChangeResult:
    """A candidate plus optional exact sources and post-admission destinations."""

    candidate: object
    source_refs: tuple[SolutionRef, ...] | None
    outputs: tuple[PoolOutput, ...]
    edits: tuple[PoolEdit, ...]

    def __init__(self, candidate, *, source_refs=None, outputs=(), edits=()):
        refs = None if source_refs is None else _refs(source_refs)
        unique = {}
        for output in tuple(outputs):
            if not isinstance(output, PoolOutput):
                raise TypeError("change outputs require PoolOutput declarations")
            previous = unique.get(output.name)
            if previous is not None and previous != output:
                raise ValueError("conflicting declarations for the same pool output")
            unique[output.name] = output
        updates = {}
        for edit in tuple(edits):
            if not isinstance(edit, PoolEdit):
                raise TypeError("change edits require PoolEdit declarations")
            if edit.name in unique:
                raise ValueError("a change cannot append and replace the same pool")
            previous = updates.get(edit.name)
            if previous is not None and previous.as_dict() != edit.as_dict():
                raise ValueError("conflicting edits for the same pool")
            updates[edit.name] = edit
        object.__setattr__(self, "candidate", candidate)
        object.__setattr__(self, "source_refs", refs)
        object.__setattr__(self, "outputs", tuple(unique.values()))
        object.__setattr__(self, "edits", tuple(updates.values()))


class ChangePool:
    """Freeze visible reference sets for one ordinary change invocation.

    ``allowed_refs=None`` is unrestricted access to committed data at the
    captured clock. A task-restricted scope can authorize individual versions,
    named views, and optional mother-pool selection independently. The optional
    ``accepted_refs`` capability grants exact versions explicitly delivered by
    the owning update; it never makes other pending records visible.
    """

    def __init__(self, pool, *, allowed_refs=None, allowed_subpools=(), allow_main=True,
                 accepted_refs=(), working_pool=None):
        if not isinstance(pool, SolutionPool):
            raise TypeError("change pool requires SolutionPool")
        if type(allow_main) is not bool:
            raise TypeError("change pool allow_main must be boolean")
        if isinstance(allowed_subpools, (str, bytes)):
            raise TypeError("allowed_subpools must contain names")
        names = tuple(allowed_subpools)
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("allowed_subpools must contain nonempty names")
        self._pool = pool
        self.timestamp = pool.timestamp
        self._published_records = pool.published_record_ids()
        accepted = _refs(accepted_refs)
        for ref in accepted:
            record = pool._record(ref, allow_pending=True)
            if record.stage != "accepted" or (not record.published and not pool._in_attempt):
                raise ValueError("accepted read capability requires this attempt's admitted versions")
        self._accepted_refs = frozenset(accepted)
        self._closed = False
        self._working_pool = None
        self._main_refs = None
        if working_pool is not None:
            from .pool_scope import _validate_binding
            self._working_pool = _validate_binding(pool, working_pool)
            self._main_refs = tuple(pool.subpool_refs(self._working_pool["name"]))
        self._used = {}
        self._restricted = allowed_refs is not None
        self._allowed = set() if allowed_refs is None else set(_refs(allowed_refs))
        self._allowed.update(accepted)
        self._allowed_subpools = frozenset(names)
        self._allow_main = allow_main
        self._views = {}
        self._view_info = {}
        self._drafts = {}
        self._automatic_edits = {}
        self._write_mode = None
        self._write_offered = None
        # A task can only access its explicitly named sources: do not enumerate
        # unrelated algorithm views (e.g. every MOEA/D direction) on each call.
        # Unrestricted calls retain the full beginning-of-call view inventory.
        visible_names = (tuple(name for name in names if pool.has_subpool(name))
                         if self._restricted else pool.published_subpool_names())
        # Freeze descriptors and exact member refs, without loading values.
        for name in visible_names:
            data = pool.subpool_metadata(name)
            if data["published"]:
                descriptor = pool.subpool_descriptor(name)
                refs = tuple(pool.subpool_refs(name))
                self._validate(refs)
                self._views[name] = (descriptor, refs)
                self._view_info[name] = freeze_wire_mapping(data)

    def _open(self):
        if self._closed:
            raise RuntimeError("change pool access has ended")

    @contextmanager
    def _writing(self, mode, offered=None):
        """Expose local syntax only at an existing owner-controlled write seam."""
        previous = self._write_mode, self._write_offered
        self._write_mode, self._write_offered = mode, offered
        try:
            yield
        finally:
            self._write_mode, self._write_offered = previous

    def _require_writer(self):
        self._open()
        if _choosing_pool.get():
            raise ValueError("chosen rules must be pure selections; inject is not allowed")
        if self._write_mode not in {"selection", "maintenance"}:
            raise RuntimeError("named Pool injection requires a survivor or pool maintenance callback")
        from .pool_maintenance import require_pool_edit_collector
        require_pool_edit_collector(self._pool)

    def _validate(self, refs):
        self._open()
        for ref in refs:
            if ref in self._accepted_refs:
                stamp = self._pool._record(ref, allow_pending=True).stamp
            else:
                stamp = self._pool.stamp_for(ref)
            if ref not in self._accepted_refs and ref.record_id not in self._published_records:
                raise ValueError("solution reference was uncommitted at the change pool cutoff")
            if stamp.run_id != self.timestamp.run_id or stamp.sequence > self.timestamp.sequence:
                raise ValueError("solution reference is newer than the change pool cutoff")

    def _selection(self, refs, *, grant=False, root=None, positions=None):
        refs = _refs(refs)
        self._validate(refs)
        if self._restricted and not grant and any(ref not in self._allowed for ref in refs):
            raise ValueError("solution reference is outside this change task's declared inputs")
        if grant:
            self._allowed.update(refs)
        return ChangeSelection(self, refs, root=root, positions=positions)

    @property
    def used_refs(self):
        self._open()
        return tuple(self._used)

    def main(self, *, region="main", stage=None, source=None):
        self._open()
        if self._restricted and not self._allow_main:
            raise ValueError("mother pool access is outside this change task's declared inputs")
        if self._main_refs is None:
            refs = tuple(ref for ref in self._pool.select(
                at=self.timestamp, region=region, stage=stage, source=source)
                if ref.record_id in self._published_records)
        else:
            if region != "main":
                raise ValueError("working_pool main access cannot select another physical region")
            refs = tuple(ref for ref in self._main_refs
                if (stage is None or self._pool._record(ref).stage == stage)
                and (source is None or self._pool._record(ref).source == source))
        return self._selection(refs, grant=True)

    def subpool(self, name):
        self._open()
        if not isinstance(name, str) or not name.strip():
            raise ValueError("subpool name must be nonempty")
        if self._restricted and name not in self._allowed_subpools:
            raise ValueError("subpool is outside this change task's declared inputs")
        if name not in self._views:
            if self._pool.has_subpool(name):
                raise ValueError("subpool is unavailable at the change pool cutoff or uncommitted")
            raise KeyError(f"subpool does not exist at the change pool cutoff: {name}")
        return self._selection(self._views[name][1], grant=True)

    def read(self, refs):
        """Select exact authorized versions; this alone does not load values."""
        return self._selection(refs)

    def describe(self, name=None):
        """Return frozen index metadata without reading candidates or Units."""
        self._open()
        if name is None:
            return freeze_wire_mapping({"pool_id": self._pool.pool_id,
                "timestamp": self.timestamp.as_dict(), "subpools": tuple(self._views)})
        selected = self.subpool(name)
        descriptor, _ = self._views[name]
        return freeze_wire_mapping({"descriptor": descriptor, "members": len(selected),
            "kind": self._view_info[name]["kind"],
            "created_by": self._view_info[name]["created_by"],
            "projection": self._view_info[name].get("projection")})

    def replace_members(self, name, refs, *, create=False):
        """Plan exact members, optionally freezing an absent ordinary target.

        Creation grants no extra read permission and performs no writes. The
        same name must still be absent when the whole step publishes the plan.
        """
        self._open()
        if type(create) is not bool:
            raise TypeError("pool edit create must be boolean")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("pool edit name must be nonempty")
        if self._restricted and name not in self._allowed_subpools:
            raise ValueError("subpool is outside this change task's declared inputs")
        if name not in self._views and create:
            if self._pool.has_subpool(name):
                raise ValueError(f"pool edit target {name!r} is unavailable at the change pool cutoff or uncommitted")
            expected = {"pool_id": self._pool.pool_id, "name": name, "absent": True}
        else:
            self.subpool(name)
            if self._view_info[name]["kind"] != "candidate_collection":
                raise ValueError("pool edits only support ordinary candidate_collection views")
            expected = self._views[name][0]
        members = self.read(refs).refs
        return PoolEdit(name, members, expected=expected)

    def update_members(self, name, *, add=(), remove=()):
        """Plan additions/removals against this invocation's frozen members."""
        previous = self.subpool(name).refs
        additions, removals = _refs(add), _refs(remove)
        if set(additions).intersection(removals):
            raise ValueError("pool edit add and remove sets overlap")
        if set(removals).difference(previous):
            raise ValueError("cannot remove a reference that is not a collection member")
        self.read(additions)
        removed = frozenset(removals)
        kept = tuple(ref for ref in previous if ref not in removed)
        members = kept + tuple(ref for ref in dict.fromkeys(additions) if ref not in kept)
        return self.replace_members(name, members)

    def remove_members(self, name, refs):
        return self.update_members(name, remove=refs)

    def trim_members(self, name, limit):
        """Plan keeping the first limit members, without inventing a ranking."""
        if type(limit) is not int or limit < 0:
            raise ValueError("pool trim limit must be a nonnegative integer")
        return self.replace_members(name, self.subpool(name).refs[:limit])

    def _materialize(self, refs, *, raw=False, semantic=False):
        self._validate(refs)
        if not refs:
            raise ValueError("cannot read an empty change selection")
        if raw:
            values = tuple(_readonly(v) for v in self._pool.read_raw_feedback(
                refs, allow_pending=any(ref in self._accepted_refs for ref in refs)))
        else:
            batch = self._pool.read(refs, allow_pending=any(ref in self._accepted_refs for ref in refs))
            # SolutionPool.read already returns a detached CandidateBatch and
            # its semantic states use the shared closed data codec.
            values = (tuple(batch.semantic_states) if semantic else
                      _readonly(batch.numeric_matrix))
        self._used.update(dict.fromkeys(refs))
        return values

    def close(self):
        """End the capability; retained selections cannot read after return."""
        self._closed = True


@dataclass(frozen=True)
class _PoolCoordinates:
    refs: tuple[SolutionRef, ...]
    objectives: object = None
    violations: object = None
    member_fields: object = None
    member_rows: object = None


class ChangeSelection:
    """Ordered references; parent= creates an empty call-local injection draft."""

    __slots__ = ("_scope", "_refs", "_root", "_positions", "_draft", "_parent",
                 "_name", "_expected", "_injected")

    def __new__(cls, scope=None, refs=(), *, root=None, positions=None, parent=None, name=None):
        if parent is not None:
            owner = parent._scope if isinstance(parent, ChangeSelection) else parent
            if not isinstance(owner, ChangePool):
                raise TypeError("Pool parent must be a live Pool or ChangePool")
            owner._open()
            if name is not None:
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Pool name must be nonempty")
                owner._require_writer()
                if name in owner._drafts:
                    return owner._drafts[name]
        return super().__new__(cls)

    def __init__(self, scope=None, refs=(), *, root=None, positions=None, parent=None, name=None):
        if parent is not None:
            if scope is not None or refs or root is not None or positions is not None:
                raise TypeError("Pool(parent=...) cannot also supply internal selection coordinates")
            if hasattr(self, "_scope"):
                return  # Same call scope and target name share one local draft.
            scope = parent._scope if isinstance(parent, ChangeSelection) else parent
            if not isinstance(scope, ChangePool):
                raise TypeError("Pool parent must be a live Pool or ChangePool")
            scope._open()
            expected = None
            if name is not None:
                scope._require_writer()
                if scope._write_mode == "selection":
                    from .change_outputs import _target
                    target = _target(scope._pool, name, True)
                    expected = target["descriptor"] or {
                        "pool_id": scope._pool.pool_id, "name": name, "absent": True}
                else:
                    expected = scope.replace_members(name, (), create=True).expected
            self._draft, self._parent, self._name = True, parent, name
            self._expected, self._injected = expected, False
        else:
            if name is not None:
                raise TypeError("a named Pool requires parent=...")
            self._draft, self._parent, self._name = False, None, None
            self._expected, self._injected = None, False
        if not isinstance(scope, ChangePool):
            raise TypeError("change selection requires a ChangePool scope")
        scope._open()
        values = _refs(refs)
        scope._validate(values)
        if scope._restricted and any(ref not in scope._allowed for ref in values):
            raise ValueError("solution reference is outside this change task's declared inputs")
        self._scope = scope
        self._refs = values
        self._root = _PoolCoordinates(values) if root is None else root
        self._positions = tuple(range(len(values))) if positions is None else tuple(positions)
        if (not isinstance(self._root, _PoolCoordinates) or len(self._positions) != len(values)
                or any(type(index) is not int or not 0 <= index < len(self._root.refs)
                       for index in self._positions)
                or tuple(self._root.refs[index] for index in self._positions) != values):
            raise ValueError("pool positions must identify exact rows of their selection root")
        if self._draft and name is not None:
            scope._drafts[name] = self

    def all(self):
        """Return this complete frozen view, never a larger source pool."""
        self._scope._open()
        return (self._scope._selection(self._refs, root=self._root, positions=self._positions)
                if self._draft else self)

    @property
    def parent(self):
        """Call-local source, not persistent subpool topology or return routing."""
        self._scope._open()
        return self._parent

    def chosen(self, rule, *, rng=None):
        """Apply one pure Pool-to-Pool rule and retain original occurrences."""
        from .pool_partition import _choose_call
        from .selection_pool import pool_selection_indices
        source = self.all()
        kwargs, needs_rng = _choose_call(rule, rng)
        if not len(source):
            return source.take(())
        if needs_rng:
            raise TypeError("chosen rule requires an explicit rng Generator")
        if source._root.objectives is None or source._root.violations is None:
            root = _PoolCoordinates(source.refs)
        else:
            objectives, violations = source.selection_feedback()
            root = _PoolCoordinates(source.refs, objectives, violations)
        if source._root.member_rows is not None:
            root = _PoolCoordinates(root.refs, root.objectives, root.violations,
                source._root.member_fields,
                tuple(source._root.member_rows[i] for i in source._positions))
        offered = self._scope._selection(source.refs, root=root,
                                        positions=tuple(range(len(source))))
        with _pure_pool_choice():
            result = rule(offered, **kwargs)
            rows = pool_selection_indices(offered, result, allow_repeated=True)
        return source.take(rows)

    def inject(self, source, *, replace=False):
        """Update a local draft; named changes publish only with its owner step.

        Append keeps old occurrences and adds each new exact version once.
        Replacement preserves the source's exact order and multiplicity.
        """
        self._scope._open()
        if not self._draft:
            raise TypeError("inject requires an empty draft created by Pool(parent=...)")
        if type(replace) is not bool:
            raise TypeError("inject replace must be boolean")
        self._same_scope((source,))
        if _choosing_pool.get():
            raise ValueError("chosen rules must be pure selections; inject is not allowed")
        source = source.all()
        if self._name is not None:
            self._scope._require_writer()
            if self._scope._write_mode == "selection":
                from .selection_pool import pool_selection_indices
                pool_selection_indices(self._scope._write_offered, source, allow_repeated=True)
        previous = self.all()
        if (not replace and self._name is not None and not self._injected
                and not self._expected.get("absent", False)):
            # Appending needs explicit access to the old target. Replacement
            # never gains a read grant just because the target is writable.
            previous = self._scope.subpool(self._name)
        if replace:
            selected = source
        else:
            seen, rows = set(previous.refs), []
            for index, ref in enumerate(source.refs):
                if ref not in seen:
                    seen.add(ref)
                    rows.append(index)
            additions = source.take(rows)
            selected = (additions if not len(previous) else previous
                        if not rows else previous.concat(additions))
        plan = None
        if self._name is not None:
            plan = PoolEdit(self._name, selected.refs, expected=self._expected)
            if self._scope._write_mode == "maintenance":
                checked = self._scope.replace_members(self._name, selected.refs,
                    create=bool(self._expected.get("absent", False)))
                if checked.expected != plan.expected:
                    raise ValueError("Pool injection target identity or revision changed")
        self._refs, self._root, self._positions = selected.refs, selected._root, selected._positions
        self._injected = True
        if plan is not None:
            self._scope._automatic_edits[self._name] = plan
        return self

    @property
    def refs(self):
        self._scope._open()
        return self._refs

    def __len__(self):
        self._scope._open()
        return len(self._refs)

    @property
    def values(self):
        return self._scope._materialize(self._refs)

    @property
    def candidates(self):
        return self._scope._materialize(self._refs, semantic=True)

    def raw_feedback(self):
        """Return original Problem objectives/violations, without view projection."""
        return self._scope._materialize(self._refs, raw=True)

    def selection_feedback(self):
        """Read the owner's supplied selection view, without recomputing Bias."""
        self._scope._open()
        if self._root.objectives is None or self._root.violations is None:
            raise ValueError("this Pool has no explicitly supplied selection feedback (cross-root concat/merge "
                             "does not combine scoring views); use raw_feedback() in your key "
                             "or select within each source before combining")
        rows = list(self._positions)
        return _readonly(self._root.objectives[rows]), _readonly(self._root.violations[rows])

    @property
    def objectives(self):
        return self.selection_feedback()[0]

    def member_field(self, name, *, default=_NO_MEMBER_DEFAULT):
        """Read this owner's declared member field in this view's row order.

        New proposals use the explicit default. Repeated candidate references
        retain distinct member slots. Pool access ends with the scope; detached
        return values remain readable.
        """
        self._scope._open()
        fields = self._root.member_fields
        if fields is None:
            raise KeyError(f"member field {name!r} has no Unit owner in this Pool; "
                           "select within the owner's offered Pool or request.members "
                           "before combining different sources")
        if name not in fields:
            raise KeyError(f"member field {name!r} is not declared in Unit.member_fields; "
                           f"available fields: {tuple(fields)}")
        values = fields[name]
        rows = tuple(self._root.member_rows[i] for i in self._positions)
        if any(row is None for row in rows) and default is _NO_MEMBER_DEFAULT:
            raise ValueError(f"member field {name!r} includes new proposals; specify default= "
                             "for their initial member value")
        if not isinstance(values, np.ndarray) or values.dtype.kind not in "biuf":
            from ..units.features import _detached_readonly
            fallback = (None if default is _NO_MEMBER_DEFAULT else _detached_readonly(default))
            return tuple(fallback if row is None else values[row] for row in rows)
        if not any(row is None for row in rows):
            return _readonly(values[list(rows)])
        fallback = np.asarray(default)
        if fallback.dtype.kind not in "biuf":
            raise TypeError("numeric member field default must be real numeric data")
        if fallback.shape != values.shape[1:]:
            raise ValueError("member field default must match one member's shape")
        dtype = np.result_type(values.dtype, fallback.dtype)
        if values.dtype.kind in "biu" and fallback.dtype.kind in "biu":
            # Signed/unsigned promotion can produce float64 and silently lose
            # exact slot data. Select an integer type using the actual bounds.
            if dtype.kind == "f":
                low = min(int(values.min()) if values.size else 0,
                          int(fallback.min()) if fallback.size else 0)
                high = max(int(values.max()) if values.size else 0,
                           int(fallback.max()) if fallback.size else 0)
                dtype = (np.dtype("uint64") if low >= 0 else np.dtype("int64"))
                limits = np.iinfo(dtype)
                if low < limits.min or high > limits.max:
                    raise ValueError("member field and default have no common exact integer dtype")
        elif dtype.kind == "f":
            # Every existing integer must remain exact if a float default is
            # requested. Do not silently turn distinct member IDs into ties.
            for value in (values, fallback):
                if value.dtype.kind in "iu" and any(
                        int(item) != int(dtype.type(item)) for item in value.flat):
                    raise ValueError("member field default would lose integer precision")
        result = np.empty((len(rows), *values.shape[1:]), dtype=dtype)
        for index, row in enumerate(rows):
            result[index] = fallback if row is None else values[row]
        return _readonly(result)

    @property
    def violations(self):
        return self.selection_feedback()[1]

    def take(self, indices):
        self._scope._open()
        if isinstance(indices, (str, bytes)):
            raise TypeError("selection indices must be integers")
        indices = tuple(indices)
        if any(not isinstance(i, (int, np.integer)) or isinstance(i, (bool, np.bool_)) for i in indices):
            raise TypeError("selection indices must be integers")
        if any(i < 0 or i >= len(self._refs) for i in indices):
            raise IndexError("change selection index is out of range")
        return self._scope._selection(tuple(self._refs[i] for i in indices),
            root=self._root, positions=tuple(self._positions[i] for i in indices))

    def random(self, n, *, rng):
        self._scope._open()
        if type(n) is not int or n < 0 or n > len(self._refs):
            raise ValueError("random selection count must be between zero and selection size")
        if not isinstance(rng, np.random.Generator):
            raise TypeError("random selection requires the owning Adapter's numpy Generator")
        return self.take(rng.choice(len(self._refs), size=n, replace=False))

    def sample(self, count, *, rng, replace=False):
        self._scope._open()
        if type(replace) is not bool:
            raise TypeError("sample replace must be boolean")
        if not replace:
            return self.random(count, rng=rng)
        if type(count) is not int or count < 0 or (count and not self._refs):
            raise ValueError("sample count requires available positions")
        if not isinstance(rng, np.random.Generator):
            raise TypeError("sample requires the owning Adapter's numpy Generator")
        return self.take(rng.choice(len(self._refs), size=count, replace=True))

    def concat(self, *others):
        """Concatenate positions without deduplicating references or slots."""
        self._same_scope(others)
        selections = (self, *others)
        refs = tuple(ref for item in selections for ref in item.refs)
        if all(item._root is self._root for item in selections):
            return self._scope._selection(refs, root=self._root,
                positions=tuple(index for item in selections for index in item._positions))
        return self._scope._selection(refs)

    def merge(self, *others):
        combined = self.concat(*others)
        seen, rows = set(), []
        for index, ref in enumerate(combined.refs):
            if ref not in seen:
                seen.add(ref)
                rows.append(index)
        return combined.take(rows)

    def where(self, predicate):
        """Filter by one aligned boolean mask, without implicit evaluation.

        ``predicate(selection)`` runs once for a nonempty selection. It can
        explicitly read detached values or existing raw feedback; this method
        never supplies a default feasibility or objective interpretation.
        """
        self._scope._open()
        if not callable(predicate):
            raise TypeError("selection predicate must be callable")
        if not self._refs:
            return self.take(())
        mask = np.asarray(predicate(self))
        if mask.dtype.kind != "b" or mask.ndim != 1 or len(mask) != len(self._refs):
            raise ValueError("selection predicate must return an aligned one-dimensional boolean mask")
        return self.take(np.flatnonzero(mask))

    def filter(self, predicate):
        return self.where(predicate)

    def order_by(self, key, *, reverse=False):
        """Stably order by explicit finite scores or lexicographic score rows.

        ``key(selection)`` returns shape ``(N,)`` or ``(N, K)`` with ``K > 0``.
        Column zero is compared first. Complete ties retain input order in
        either direction. No callback is invoked for an empty selection.
        """
        self._scope._open()
        if not callable(key):
            raise TypeError("selection ordering key must be callable")
        if type(reverse) is not bool:
            raise TypeError("selection ordering reverse must be boolean")
        if not self._refs:
            return self.take(())
        scores = np.asarray(key(self))
        if (scores.dtype.kind not in "iuf" or scores.ndim not in (1, 2)
                or scores.shape[0] != len(self._refs)
                or (scores.ndim == 2 and scores.shape[1] == 0)
                or not np.all(np.isfinite(scores))):
            raise ValueError("selection ordering key must return aligned finite real scores of shape (N,) or (N, K)")
        # Python's stable ordering preserves ties under reverse as well, and
        # does not negate unsigned/minimum signed integers or coerce precise
        # integer scores into floats.
        rows = scores.reshape(len(self._refs), -1)
        indices = sorted(range(len(self._refs)), key=lambda i: tuple(rows[i]), reverse=reverse)
        return self.take(indices)

    def sort(self, key, *, reverse=False):
        return self.order_by(key, reverse=reverse)

    def top(self, n, *, key, reverse=False):
        """Take up to ``n`` explicitly ranked references; never infer a score."""
        self._scope._open()
        if not isinstance(n, (int, np.integer)) or isinstance(n, (bool, np.bool_)) or n < 0:
            raise ValueError("top selection count must be a nonnegative integer")
        if not callable(key):
            raise TypeError("selection ordering key must be callable")
        if type(reverse) is not bool:
            raise TypeError("selection ordering reverse must be boolean")
        if n == 0:
            return self.take(())
        ordered = self.order_by(key, reverse=reverse)
        return ordered.take(range(min(n, len(ordered))))

    def _same_scope(self, others):
        """Validate operands before any local set operation."""
        self._scope._open()
        for other in others:
            if not isinstance(other, ChangeSelection) or other._scope is not self._scope:
                raise ValueError("cannot combine selections from different change invocations")
            other._scope._open()

    def intersection(self, *others):
        """Keep left occurrences present in every operand by exact version ref."""
        self._same_scope(others)
        allowed = [set(other.refs) for other in others]
        return self.take(tuple(index for index, ref in enumerate(self._refs)
                               if all(ref in values for values in allowed)))

    def difference(self, *others):
        """Keep left occurrences absent from all operands by exact version ref."""
        self._same_scope(others)
        removed = set().union(*(set(other.refs) for other in others))
        return self.take(tuple(index for index, ref in enumerate(self._refs) if ref not in removed))

    def groups(self, size):
        """Split into temporary consecutive selections, including the last tail.

        These groups only organize references inside this call. They do not
        create named subpools or construct algorithm Units.
        """
        self._scope._open()
        if (not isinstance(size, (int, np.integer))
                or isinstance(size, (bool, np.bool_)) or size <= 0):
            raise ValueError("selection group size must be a positive integer")
        return tuple(self.take(range(start, min(start + size, len(self._refs))))
                     for start in range(0, len(self._refs), size))


# One public collection interface; existing ChangeSelection imports remain valid.
Pool = ChangeSelection
