"""Explicit algorithm operations owned by their actual Adapter consumer.

These are behavior roles, not a mandatory four-stage execution loop. Each
Adapter declares only the roles its native control flow actually invokes.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from functools import partial
from types import MappingProxyType
from types import FunctionType

import numpy as np

from .operator_binding import OperatorBinding


OPERATION_METHODS = MappingProxyType({"initializer": "initialize", "mutator": "mutate",
                                    "parent_selector": "select", "selector": "select", "repair": "repair",
                                    "change": "change", "pool_maintenance": "maintain"})


class OperatorBindingRestoreError(RuntimeError):
    """A component restore and one or more compensating restores failed."""

    def __init__(self, original_error, compensation_errors):
        self.original_error = original_error
        self.compensation_errors = tuple(compensation_errors)
        super().__init__(f"Operator restore failed; {len(self.compensation_errors)} compensation operation(s) also failed")


class AdapterOperationsMixin:
    operation_methods = {}
    _operation_groups = {"initializer": "initialization", "mutator": "variation",
                          "parent_selector": "selection", "selector": "selection", "repair": "repair",
                          "change": "variation", "pool_maintenance": "selection"}

    def _operator_bindings(self):
        return dict(getattr(self, "_operation_bindings", {}))

    def get_local_operator_bindings(self):
        """Only locally owned codecs; never include a child's bindings."""
        return self._operator_bindings()

    def get_bound_operator(self, role):
        binding = self._operator_bindings().get(role)
        return None if binding is None else binding.component

    def get_bound_initializer(self):
        return self.get_bound_operator("initializer")

    def get_bound_mutator(self):
        return self.get_bound_operator("mutator")

    def get_bound_selector(self):
        return self.get_bound_operator("selector")

    def set_operation(self, role, component):
        methods = self.operation_methods
        if not isinstance(methods, Mapping):
            raise TypeError("operation_methods must be a Mapping")
        if role not in methods or role not in self._operation_groups:
            if component is None:
                return
            raise ValueError(f"{self.name}: unsupported operation role {role!r}; bind operations to a declared leaf consumer")
        if methods[role] != OPERATION_METHODS[role]:
            raise ValueError(f"unsupported operation declaration {role!r}: {methods[role]!r}")
        if role == "mutator" and component is not None and self.mutation_operator is not None:
            raise ValueError("a direct mutator cannot be combined with a named pipeline mutation")
        if role == "mutator" and component is not None and self.get_bound_change() is not None:
            raise ValueError("a complete change cannot be combined with a direct mutator")
        if role == "change" and component is not None and (self.get_bound_mutator() is not None or self.mutation_operator is not None):
            raise ValueError("a complete change cannot be combined with direct or named pipeline mutation")
        binding = None if component is None else OperatorBinding(component, method=methods[role])
        if role == "repair":
            # Retain the existing leaf/draft/admission validation and execution
            # through JointRepairPolicy, rather than calling repair in propose.
            self.set_unit_repair(component)
        values = self._operator_bindings()
        if binding is None:
            values.pop(role, None)
        else:
            values[role] = binding
        self._operation_bindings = values

    def set_initializer(self, component):
        self.set_operation("initializer", component)

    def set_mutator(self, component):
        self.set_operation("mutator", component)

    def set_parent_selector(self, component):
        self.set_operation("parent_selector", component)

    def set_selector(self, component):
        if isinstance(component, (FunctionType, partial)):
            from .selection import OrdinaryPoolSelection
            component = OrdinaryPoolSelection(component)
        self.set_operation("selector", component)

    def set_repair(self, component):
        self.set_operation("repair", component)

    def set_change(self, function):
        """Bind an ordinary pure function; no user base class or codec boilerplate."""
        from .change import OrdinaryFunctionChange
        self.set_operation("change", None if function is None else OrdinaryFunctionChange(function))

    def get_bound_change(self):
        return self.get_bound_operator("change")

    def set_pool_maintenance(self, function):
        from .pool_maintenance import OrdinaryPoolMaintenance
        self.set_operation("pool_maintenance", None if function is None else OrdinaryPoolMaintenance(function))

    def apply_change(self, control, candidate, request, context, *, rng):
        from .change import apply_function_change
        return apply_function_change(self, control, candidate, request, context, rng=rng)

    def seed_operator_bindings(self, rng):
        for binding in self._operator_bindings().values():
            binding.seed(int(rng.integers(0, 2**32)))

    def operator_bindings_state(self):
        return {role: binding.get_state() for role, binding in self._operator_bindings().items()}

    def restore_operator_bindings(self, saved):
        bindings = self._operator_bindings()
        if saved is None and not bindings:
            saved = {}
        if not isinstance(saved, Mapping) or set(saved) != set(bindings):
            raise ValueError(f"{self.name}: checkpoint operator bindings do not match the current assembly")
        for role, binding in bindings.items():
            binding.validate_state(saved[role])
        before = {role: binding.get_state() for role, binding in bindings.items()}
        attempted = []
        try:
            for role, binding in bindings.items():
                attempted.append(role)
                binding.set_state(saved[role])
        except Exception as original:
            failures = []
            for role in reversed(attempted):
                try:
                    bindings[role].set_state(before[role])
                except Exception as failure:
                    failures.append(failure)
            if failures:
                raise OperatorBindingRestoreError(original, failures) from original
            raise

    @contextmanager
    def restoring_operator_bindings(self, saved):
        """Compensate component state if subsequent algorithm restore rejects.

        Binding preflight/set failures already compensate inside restore; do
        not invoke setters again when an incompatible envelope was rejected.
        This guard does not claim arbitrary third-party restore is atomic.
        """
        before = self.operator_bindings_state()
        self.restore_operator_bindings(saved)
        try:
            yield
        except Exception as original:
            try:
                self.restore_operator_bindings(before)
            except Exception as compensation:
                raise OperatorBindingRestoreError(original, (compensation,)) from original
            raise

    def merge_operator_context_contract(self, result):
        bindings = self._operator_bindings()
        if not bindings:
            return result
        from blackbase.context import ContextContract, get_component_contract
        fields = ("requires", "provides", "mutates", "cache", "artifact_requires",
                  "artifact_provides", "phase_in", "phase_out")
        merged = ContextContract(**{field: result.get(field, ()) for field in fields}, notes=result.get("notes"))
        for binding in bindings.values():
            contract = get_component_contract(binding.component)
            if contract is not None:
                merged = merged.merge(contract)
        return {**result, **{field: list(getattr(merged, field)) for field in fields}, "notes": merged.notes}

    def get_operation_contract(self):
        """Report actual assembly support, not a claim of interchangeable algorithms."""
        groups = {name: {} for name in ("initialization", "variation", "selection", "repair")}
        for role, method in self.operation_methods.items():
            binding = self._operator_bindings().get(role)
            groups[self._operation_groups[role]][role] = {
                "method": method, "binding": None if binding is None else binding.describe()}
        return groups

    def init_candidate(self, control, context=None):
        component = self.get_bound_initializer()
        if component is None:
            return control.init_candidate(context)
        return control.init_candidate(context, initializer=component)

    def init_population(self, control, count, context=None):
        component = self.get_bound_initializer()
        if component is None:
            return control.init_population(count, context)
        return control.init_population(count, context, initializer=component)

    @staticmethod
    def semantic_proposal(control, candidate):
        """Preserve semantic metadata when a numeric algorithm returns a proposal."""
        from ..units.contracts import candidate_array
        record = control.candidate_provenance_for(candidate)
        if record is None:
            raise ValueError("bound search proposals require control-plane provenance")
        row = candidate_array(candidate)
        control.bind_candidate_provenance((row,), (record,), activate=False)
        state = control.semantic_candidate_state(row)
        control.bind_candidate_provenance((state,), (record,), activate=False)
        return state

    def select_indices(self, request, *, rng):
        from .selection import SelectionRequest
        from ..units.operator_inputs import selection_unit_spec
        if not isinstance(request, SelectionRequest):
            raise TypeError("selection requires SelectionRequest")
        selector = self.get_bound_selector()
        if selector is None:
            raise ValueError(f"{self.name}: no selector is bound")
        spec = selection_unit_spec(selector)
        inputs = {} if spec is None else {"unit": spec.capture(self.get_operator_unit())}
        from contextlib import nullcontext
        writing = (request.pool._scope._writing("selection", request.pool)
                   if request.pool is not None and request.purpose == "survivor"
                   else nullcontext())
        with writing:
            result = selector.select(request, rng=rng, **inputs)
        from .change_pool import Pool
        outputs = None
        if (isinstance(result, tuple) and len(result) == 2
                and isinstance(result[0], Pool) and isinstance(result[1], Mapping)):
            if request.purpose != "survivor":
                raise ValueError("named selection outputs require a survivor selection purpose")
            result, outputs = result
        if isinstance(result, Pool):
            from .selection_pool import pool_selection_indices
            result = pool_selection_indices(request.pool, result)
        if isinstance(result, (str, bytes, Mapping, set, frozenset)):
            raise TypeError("selector must return ordered row indices")
        try:
            rows = tuple(result)
        except TypeError as exc:
            raise TypeError("selector must return ordered row indices") from exc
        if (len(rows) != request.count or any(isinstance(row, (bool, np.bool_))
                or not isinstance(row, (int, np.integer)) for row in rows)):
            raise ValueError(f"{self.name}: {request.purpose} selector indices must be integers matching the requested count "
                             f"(expected {request.count}, got {len(rows)})")
        indices = tuple(int(row) for row in rows)
        if len(set(indices)) != len(indices) or any(row < 0 or row >= len(request.violations) for row in indices):
            raise ValueError("selector indices must be distinct and within the offered rows")
        if outputs is not None:
            from .selection_pool import stage_selection_outputs
            stage_selection_outputs(request.pool, outputs)
        if request.pool is not None and request.pool._scope._automatic_edits:
            from .pool_maintenance import collect_selection_edits
            collect_selection_edits(request.pool._scope._pool,
                                    tuple(request.pool._scope._automatic_edits.values()))
        return np.asarray(indices, dtype=int)
