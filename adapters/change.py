"""Ordinary, stateless Python functions for complete candidate changes.

The owning Adapter supplies detached inputs and its checkpointed RNG.  This
module does not evaluate candidates, publish pools, or own a search lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import partial
from hashlib import sha256
import dis
import inspect
import json
from types import BuiltinFunctionType, CodeType, FunctionType, ModuleType
from typing import Any, Mapping

import numpy as np

from ..core.state.solution_pool import SolutionRef
from ..units.contracts import candidate_array
from ..units.features import _snapshot
from .change_batch import ChangeBatchResult
from .change_pool import ChangePool, ChangeResult, Pool
from .change_outputs import prepare_pool_outputs, prepare_pool_edits
from .change_access import current_change_access


@dataclass(frozen=True, init=False)
class ChangeRequest:
    """A frozen parent view; the first row is the algorithm's anchor.

    ``source_refs`` identifies the supplied input versions, not a claim that
    the function read every parent. Parameters contain algorithm-specific data;
    context is deliberately restricted to the call's scalar projection. ``pool``
    is an optional, call-scoped read capability; it is never checkpoint state.
    """

    parents: np.ndarray
    source_refs: tuple[SolutionRef, ...]
    parameters: Mapping[str, Any]
    context: Mapping[str, Any]
    unit_id: str | None
    pool: ChangePool | None
    max_outputs: int | None
    parent_pool: Pool | None
    parent_member_indices: tuple[int | None, ...]

    def __init__(self, parents, *, source_refs=(), parameters=None, context=None, unit_id=None, pool=None,
                 max_outputs=None, parent_pool=None, parent_member_indices=()):
        matrix = np.asarray(parents)
        if matrix.ndim != 2 or not all(matrix.shape) or matrix.dtype.kind not in "biuf":
            raise ValueError("change parents must be a nonempty real numeric matrix")
        refs = tuple(source_refs)
        if refs and (len(refs) != len(matrix) or any(not isinstance(ref, SolutionRef) for ref in refs)):
            raise ValueError("change source_refs must align with the supplied parent rows")
        if unit_id is not None and (not isinstance(unit_id, str) or not unit_id.strip()):
            raise ValueError("change unit_id must be nonempty when supplied")
        if parameters is not None and not isinstance(parameters, Mapping):
            raise TypeError("change parameters must be a data Mapping")
        if context is not None and not isinstance(context, Mapping):
            raise TypeError("change context must be a Mapping")
        if pool is not None and not isinstance(pool, ChangePool):
            raise TypeError("change pool must be a call-scoped ChangePool")
        member_indices = tuple(parent_member_indices)
        if member_indices and (len(member_indices) != len(matrix) or any(
                row is not None and (type(row) is not int or row < 0) for row in member_indices)):
            raise ValueError("change parent member indices must align with supplied parents")
        if parent_pool is not None:
            if not isinstance(parent_pool, Pool) or parent_pool.refs != refs:
                raise ValueError("change parent_pool must identify the supplied parent references")
            rows = parent_pool._root.member_rows
            if rows is None or member_indices != tuple(rows[i] for i in parent_pool._positions):
                raise ValueError("change parent member indices disagree with parent_pool occurrences")
            if not np.array_equal(parent_pool.values, matrix, equal_nan=True):
                raise ValueError("change parent_pool values differ from supplied parents")
        if max_outputs is not None and (not isinstance(max_outputs, (int, np.integer))
                or isinstance(max_outputs, (bool, np.bool_)) or max_outputs < 0):
            raise ValueError("change max_outputs must be a nonnegative integer or None")
        lightweight = {key: value for key, value in dict(context or {}).items()
                       if isinstance(key, str) and (value is None or type(value) in (str, bool, int, float))}
        _, data = _snapshot({"parameters": dict(parameters or {}), "context": lightweight})
        frozen = np.frombuffer(matrix.tobytes(), dtype=matrix.dtype).reshape(matrix.shape)
        object.__setattr__(self, "parents", frozen)
        object.__setattr__(self, "source_refs", refs)
        object.__setattr__(self, "parameters", data["parameters"])
        object.__setattr__(self, "context", data["context"])
        object.__setattr__(self, "unit_id", unit_id)
        object.__setattr__(self, "pool", pool)
        object.__setattr__(self, "max_outputs", None if max_outputs is None else int(max_outputs))
        object.__setattr__(self, "parent_pool", parent_pool)
        object.__setattr__(self, "parent_member_indices", member_indices)

    @property
    def candidate(self):
        return self.parents[0]


def _code_value(value):
    """Fingerprint Python code without absolute paths or source line numbers."""
    if isinstance(value, CodeType):
        return {"bytecode": value.co_code.hex(), "constants": [_code_value(v) for v in value.co_consts],
                "names": value.co_names, "variables": value.co_varnames,
                "freevars": value.co_freevars, "cellvars": value.co_cellvars,
                "arguments": (value.co_argcount, value.co_posonlyargcount, value.co_kwonlyargcount),
                "flags": value.co_flags, "exceptions": getattr(value, "co_exceptiontable", b"").hex()}
    if isinstance(value, tuple):
        return {"tuple": [_code_value(v) for v in value]}
    if isinstance(value, frozenset):
        items = [_code_value(v) for v in value]
        return {"frozenset": sorted(items, key=lambda v: json.dumps(v, sort_keys=True))}
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, complex):
        return {"complex": [value.real, value.imag]}
    if value is Ellipsis:
        return {"ellipsis": True}
    if value is None or type(value) in (bool, int, float, str):
        return value
    raise TypeError(f"unsupported Python code constant: {type(value).__name__}")


def _configuration(value, active):
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, tuple):
        return {"tuple": [_configuration(v, active) for v in value]}
    if isinstance(value, (FunctionType, partial)):
        return _function_identity(value, active)
    raise TypeError("plain change functions cannot capture mutable or runtime objects; "
                    "use request data and the supplied rng, or an explicit stateful operator")


def _function_identity(function, active=None, *, follow_globals=True):
    active = set() if active is None else active
    if id(function) in active:
        raise TypeError("recursive captured change configuration is unsupported")
    active.add(id(function))
    try:
        if isinstance(function, partial):
            return {"partial": _function_identity(function.func, active),
                    "args": _configuration(function.args, active),
                    "kwargs": {key: _configuration(value, active)
                               for key, value in (function.keywords or {}).items()}}
        if not isinstance(function, FunctionType):
            raise TypeError("change must be an ordinary Python function or functools.partial")
        if inspect.iscoroutinefunction(function) or inspect.isgeneratorfunction(function) or inspect.isasyncgenfunction(function):
            raise TypeError("plain change must return candidate results synchronously")
        code = json.dumps(_code_value(function.__code__), sort_keys=True).encode()
        closed = {} if function.__closure__ is None else {
            name: _configuration(cell.cell_contents, active)
            for name, cell in zip(function.__code__.co_freevars, function.__closure__)}
        dependencies = {}
        if follow_globals:
            # Inspect names actually referenced by this function, never an
            # arbitrary module/object graph. Direct same-module helpers have a
            # code fingerprint too; external libraries remain environment deps.
            names = {instruction.argval for instruction in dis.get_instructions(function)
                     if instruction.opname in {"LOAD_GLOBAL", "LOAD_NAME"}}
            for name in sorted(names):
                if name not in function.__globals__:
                    continue
                value = function.__globals__[name]
                if isinstance(value, ModuleType):
                    dependencies[name] = {"module": value.__name__}
                elif isinstance(value, FunctionType):
                    if id(value) in active:
                        dependencies[name] = {"function": value.__module__ + "." + value.__qualname__}
                    elif value.__module__ == function.__module__:
                        dependencies[name] = _function_identity(value, active, follow_globals=False)
                    else:
                        dependencies[name] = {"function": value.__module__ + "." + value.__qualname__}
                elif isinstance(value, np.ufunc):
                    dependencies[name] = {"external_ufunc": "numpy." + value.__name__}
                elif isinstance(value, (BuiltinFunctionType, type)):
                    module = getattr(value, "__module__", None) or type(value).__module__
                    qualified = getattr(value, "__qualname__", value.__name__)
                    receiver = getattr(value, "__self__", None)
                    if isinstance(receiver, np.ufunc):
                        qualified = receiver.__name__ + "." + value.__name__
                    dependencies[name] = {"external": module + "." + qualified}
                else:
                    dependencies[name] = _configuration(value, active)
        return {"module": function.__module__, "name": function.__qualname__,
                "code": sha256(code).hexdigest(), "defaults": _configuration(function.__defaults__, active),
                "keywords": {key: _configuration(value, active)
                             for key, value in (function.__kwdefaults__ or {}).items()},
                "closed": closed, "dependencies": dependencies}
    finally:
        active.remove(id(function))


class OrdinaryFunctionChange:
    """Internal bridge: users provide only ``function(request, *, rng)``.

    The function is a pure calculation by contract. Global Python side effects
    cannot be sandboxed or rolled back; hidden mutable state is unsupported.
    """

    stateless = True

    def __init__(self, function):
        inspect.signature(function).bind(object(), rng=object())
        _function_identity(function)
        self.function = function

    def checkpoint_identity(self):
        return {"schema": "nsgablack.plain_change/v1", "function": _function_identity(self.function)}

    def change(self, request, *, rng):
        if not isinstance(request, ChangeRequest):
            raise TypeError("ordinary change requires ChangeRequest")
        return self.function(request, rng=rng)


class _ChangeInvocation:
    """Call-scoped adapter into the existing candidate/provenance pipeline."""

    def __init__(self, operation, request, rng, pool):
        self.operation, self.request, self.rng, self.pool = operation, request, rng, pool
        self.result = None
        self.outputs = ()
        self.edits = ()

    def mutate(self, candidate, context):
        result = self.operation.change(self.request, rng=self.rng)
        if isinstance(result, ChangeBatchResult):
            if len(result) != 1:
                raise ValueError("a scalar change requires exactly one candidate result; use a batch consumer")
            result = result.results[0]
        self.result, self.outputs, self.edits = _prepare_change_result(result, self.request, self.pool)
        return self.result.candidate


def _prepare_change_result(result, request, pool):
    """Validate one result without creating a proposal or evaluating it."""
    result = result if isinstance(result, ChangeResult) else ChangeResult(result)
    values = candidate_array(result.candidate)
    if values.shape != (request.parents.shape[1],):
        raise ValueError(f"change candidate dimension mismatch: got {len(values)} != expected {request.parents.shape[1]}")
    if result.source_refs is not None:
        if request.pool is None:
            if result.source_refs:
                raise ValueError("declared change sources require a solution pool")
        else:
            request.pool.read(result.source_refs)
    outputs = prepare_pool_outputs(pool, result.outputs)
    if request.pool is not None:
        for edit in result.edits:
            # Revalidate in this invocation's scope, including a frozen absent
            # target. Planning creation never grants other source references.
            expected = request.pool.replace_members(edit.name, edit.members,
                create=bool(edit.expected.get("absent", False)))
            if expected.expected != edit.expected:
                raise ValueError("change pool edit target identity or revision changed")
    edits = prepare_pool_edits(pool, result.edits)
    return result, outputs, edits


def _change_scope(control, request, context=None):
    pool = getattr(control, "solution_pool", None)
    access = current_change_access()
    permissions = ({} if access is None else {
        "allowed_refs": (*access.seed_refs, *request.source_refs),
        "allowed_subpools": access.subpools, "allow_main": access.allow_main})
    from .pool_scope import working_pool_descriptor
    return pool, None if pool is None else ChangePool(
        pool, working_pool=working_pool_descriptor(context), **permissions)


def _bind_change_result(control, changed, request, scope, result, outputs, edits):
    """Bind independent proposal instructions and exact per-child sources."""
    extra = () if scope is None else scope.used_refs
    declared = request.source_refs if result.source_refs is None else result.source_refs
    # Supplied default slots retain their order and multiplicity. Shared reads
    # are causal evidence for the calculation; per-child source declarations
    # remain separately available instead of being conflated with that union.
    refs = list(request.source_refs)
    for ref in (*extra, *declared):
        if ref not in refs:
            refs.append(ref)
    provenance = control.candidate_provenance_for(changed)
    if provenance is None:
        raise RuntimeError("complete change produced no candidate provenance")
    metadata = {**dict(provenance.metadata),
        "change_input_refs": [ref.as_dict() for ref in refs],
        "change_source_refs": [ref.as_dict() for ref in declared]}
    if request.parent_member_indices:
        metadata["parent_member_indices"] = request.parent_member_indices
    # Instructions inherited from an input are historical evidence only.
    metadata.pop("change_outputs", None)
    metadata.pop("change_pool_edits", None)
    if outputs:
        metadata["change_outputs"] = {
            "schema": "nsgablack.change_outputs/v1",
            "proposal_token": provenance.candidate_token,
            "targets": list(outputs),
        }
    if edits:
        metadata["change_pool_edits"] = {
            "schema": "nsgablack.change_pool_edits/v1",
            "proposal_token": provenance.candidate_token,
            "edits": list(edits),
        }
    provenance = replace(provenance, metadata=metadata)
    control.bind_candidate_provenance((changed,), (provenance,), activate=False)
    return changed


def apply_function_change(owner, control, candidate, request, context, *, rng):
    operation = owner.get_bound_change()
    if operation is None:
        raise ValueError("no complete change function is bound")
    if not isinstance(request, ChangeRequest):
        raise TypeError("complete change requires ChangeRequest")
    pool, scope = _change_scope(control, request, context)
    scoped_request = replace(request, pool=scope, max_outputs=1)
    invocation = _ChangeInvocation(operation, scoped_request, rng, pool)
    try:
        changed = control.mutate_candidate(candidate, context, mutator=invocation)
        return _bind_change_result(control, changed, request, scope, invocation.result,
                                   invocation.outputs, invocation.edits)
    finally:
        if scope is not None:
            scope.close()
