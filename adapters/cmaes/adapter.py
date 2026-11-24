"""Full-cohort CMA-ES on the existing Solver transaction/evidence surfaces."""
from copy import deepcopy
from dataclasses import asdict
from collections.abc import Mapping

import numpy as np

from ...core.evaluation_feedback import OptimizationFeedbackBatch
from ...core.state.solution_pool import SolutionRef
from ...representation.cmaes_builder import CMAUnitBuilder
from ...representation.structure_builders import encode_unit_value, decode_unit_value
from ...units.cmaes import validate_distribution
from ..unit_backed import UnitBackedAdapter
from .components import CMAParameters, GaussianCohortSampler, PositiveCMAUpdate, StableObjectiveRanking


class CMAESAdapter(UnitBackedAdapter):
    unit_builder_type = CMAUnitBuilder
    unit_schema = CMAUnitBuilder.unit_type.schema
    state_recovery_level = "L1"
    state_recovery_notes = "Restores distribution, cohort relations and explicit sampler RNG state."
    operation_methods = {}
    accepts_proposal_replacement = False
    context_requires = context_provides = context_mutates = context_cache = ()
    context_notes = "CMA distribution and cohort relations are local Unit data; no shared context writes."

    def __init__(self, mean, *, sigma=.5, covariance=None, parameters=None, sampler=None,
                 ranking=None, updater=None, seed=42, name="cmaes", unit_binding=None):
        super().__init__(name, unit_binding=unit_binding)
        self.initial_mean = np.asarray(mean, dtype=float).copy()
        if self.initial_mean.ndim != 1 or not len(self.initial_mean):
            raise ValueError("CMA initial mean must be a nonempty vector")
        n = len(self.initial_mean)
        self.initial_covariance = np.eye(n) if covariance is None else np.array(covariance, dtype=float, copy=True)
        self.initial_sigma = float(sigma)
        self.parameters = parameters or CMAParameters()
        self.parameters.resolve(n)
        self.sampler = sampler or GaussianCohortSampler(seed)
        self.ranking = ranking or StableObjectiveRanking()
        self.updater = updater or PositiveCMAUpdate(self.parameters)
        if not callable(getattr(self.sampler, "reset", None)):
            raise TypeError("CMA sampler must provide reset()")
        for component in self._components.values():
            if not isinstance(getattr(component, "checkpoint_identity", None), dict):
                raise TypeError("CMA components must declare a stable checkpoint_identity mapping")
            if getattr(component, "stateless", False) is not True:
                if any(not callable(getattr(component, method, None)) for method in ("get_state", "set_state", "reset")):
                    raise TypeError("Stateful CMA components require reset/get_state/set_state")
        # Validate the initial distribution without constructing a runtime Unit.
        validate_distribution(self.initial_mean, self.initial_covariance, self.initial_sigma,
                              np.zeros(n), np.zeros(n))

    @property
    def _components(self):
        return {"sampler": self.sampler, "ranking": self.ranking, "updater": self.updater}

    def setup(self, control):
        pending, seen, owners = [getattr(control, "adapter", self)], set(), {}
        while pending:
            adapter = pending.pop()
            if id(adapter) in seen:
                continue
            seen.add(id(adapter))
            pending.extend(adapter.step_transaction_children())
            components = getattr(adapter, "_components", {})
            if not isinstance(components, Mapping):
                continue
            for name, component in components.items():
                if getattr(component, "stateless", False) is True:
                    continue
                key = id(component)
                if key in owners:
                    raise ValueError("stateful CMA component has multiple Adapter owners or role bindings")
                owners[key] = (adapter, name)
        self.reset_unit()
        for component in self._components.values():
            if getattr(component, "stateless", False) is not True:
                component.reset()

    @property
    def configuration_identity(self):
        return {"schema": "cma.adapter/v1", "mean": self.initial_mean.tolist(),
            "covariance": self.initial_covariance.tolist(), "sigma": self.initial_sigma,
            "parameters": asdict(self.parameters),
            "components": [deepcopy(c.checkpoint_identity) for c in (self.sampler, self.ranking, self.updater)]}

    def _distribution(self):
        u = self.ensure_unit()
        if u.mean is None:
            u.mean = self.initial_mean.copy()
            u.covariance = self.initial_covariance.copy()
            u.sigma = self.initial_sigma
            u.path_c = np.zeros_like(u.mean)
            u.path_sigma = np.zeros_like(u.mean)
        u.validate()
        return u

    def propose(self, control, context):
        u = self._distribution()
        if u.pending:
            raise ValueError("CMA cannot open another cohort before disposing the current cohort")
        z = np.array(self.sampler.sample(self.parameters.population_size, len(u.mean)), dtype=float, copy=True)
        if z.shape != (self.parameters.population_size, len(u.mean)) or not np.all(np.isfinite(z)):
            raise ValueError("CMA sampler must return a finite full cohort")
        eigenvalues, basis = np.linalg.eigh(u.covariance)
        sqrt_c = (basis * np.sqrt(eigenvalues)) @ basis.T
        y = z @ sqrt_c.T
        x = u.mean[None, :] + u.sigma * y
        u.pending = {"cohort_id": f"{u.unit_id}:{u.iteration}", "distribution_revision": u.iteration,
                     "source_distribution": {"mean": u.mean.copy(), "covariance": u.covariance.copy(),
                         "sigma": u.sigma, "path_c": u.path_c.copy(), "path_sigma": u.path_sigma.copy()},
                     "z": z, "offsets": y, "candidates": x, "tokens": (), "proposal_indices": tuple(range(len(x)))}
        return tuple(row.copy() for row in x)

    def on_proposal_repair(self, control, repair, context):
        if repair.changed_indices:
            raise ValueError(f"CMA changed repair is unsupported; indices={repair.changed_indices}")
        u = self.ensure_unit()
        if not u.pending or repair.proposed_count != self.parameters.population_size:
            raise ValueError("CMA repair does not address its full cohort")
        u.pending["tokens"] = tuple(repair.after.candidate_tokens)
        u.pending["evaluated_indices"] = tuple(repair.proposal_indices)

    def on_proposal_disposition(self, control, disposition, context):
        expected = tuple(range(self.parameters.population_size))
        if disposition.proposed_count != len(expected) or tuple(disposition.accepted_indices) != expected:
            missing = tuple(i for i in expected if i not in disposition.accepted_indices)
            raise ValueError(f"CMA incomplete cohort; missing original indices={missing}; lambda stays {len(expected)}")

    def update(self, control, candidates, feedback, context):
        fb = OptimizationFeedbackBatch.coerce(feedback)
        u, count = self.ensure_unit(), self.parameters.population_size
        x = np.asarray(candidates, dtype=float)
        p = u.pending
        if (not p or len(x) != count or fb.candidate_count != count
                or p["distribution_revision"] != u.iteration
                or not np.array_equal(x, p["candidates"])):
            raise ValueError("CMA update requires its unchanged complete cohort")
        if any(not np.array_equal(getattr(u, field), value) for field, value in p["source_distribution"].items()):
            raise ValueError("CMA source distribution changed while its cohort was pending")
        order = np.asarray(self.ranking.rank(fb))
        if order.shape != (count,) or sorted(order.tolist()) != list(range(count)):
            raise ValueError("CMA ranking must be a permutation of the full cohort")
        updates = self.updater.update(mean=u.mean.copy(), covariance=u.covariance.copy(), sigma=u.sigma,
            path_c=u.path_c.copy(), path_sigma=u.path_sigma.copy(), iteration=u.iteration,
            offsets=p["offsets"].copy(), ranking=order.copy())
        expected_fields = {"mean", "covariance", "sigma", "path_c", "path_sigma", "iteration", "h_sigma"}
        if (not isinstance(updates, Mapping) or set(updates) != expected_fields
                or updates["iteration"] != u.iteration + 1 or updates["h_sigma"] not in (0, 1)):
            raise ValueError("CMA updater must return exactly one complete distribution advance")
        updates = decode_unit_value(encode_unit_value(dict(updates)))
        validate_distribution(updates["mean"], updates["covariance"], updates["sigma"],
                              updates["path_c"], updates["path_sigma"], updates["iteration"])
        refs = tuple(dict(item.info["accepted_solution_ref"]) for item in fb.items)
        tokens = tuple(SolutionRef.from_dict(r).candidate_token for r in refs)
        if p["tokens"] and tuple(p["tokens"]) != tokens:
            raise ValueError("CMA feedback tokens differ from repaired cohort")
        # A Solver with no RepresentationPipeline has no repair notification.
        # Its full, ordered accepted receipts establish the same cohort binding.
        p["tokens"] = tokens
        if not np.array_equal(control.solution_pool.read(tuple(SolutionRef.from_dict(r) for r in refs),
                                  allow_pending=True).numeric_matrix, x):
            raise ValueError("CMA exact observed references differ from evaluated cohort")
        best_index = int(order[0])
        raw = np.asarray(fb.raw_objectives)
        if not u.best or raw[best_index, 0] < u.best["objective"]:
            u.best = {"candidate": x[best_index].copy(), "objective": float(raw[best_index, 0]), "ref": refs[best_index]}
        u.last_cohort = {**deepcopy(p), "refs": refs, "raw_objectives": raw.copy(),
                         "ranking": order.copy(), "selected_indices": tuple(int(i) for i in order[:self.parameters.parents]),
                         "raw_violations": np.asarray(fb.raw_violations).copy(), "h_sigma": updates.pop("h_sigma")}
        for name, value in updates.items():
            setattr(u, name, value)
        u.pending = {}
        u.validate()

    def get_current_candidates(self):
        u = self.algorithm_unit
        return None if u is None or not u.best else (np.array(u.best["candidate"], copy=True),)

    def get_solution_pool_roots(self, control):
        u = self.algorithm_unit
        if u is None:
            return ()
        cohort_refs = tuple(SolutionRef.from_dict(r) for r in u.last_cohort.get("refs", ()))
        if cohort_refs:
            batch = control.solution_pool.read(cohort_refs, allow_pending=True)
            raw, violations = control.solution_pool.read_raw_feedback(cohort_refs, allow_pending=True)
            if (not np.array_equal(batch.numeric_matrix, u.last_cohort["candidates"])
                    or tuple(batch.candidate_tokens) != tuple(u.last_cohort["tokens"])
                    or not np.array_equal(raw, u.last_cohort["raw_objectives"])
                    or not np.array_equal(violations, u.last_cohort["raw_violations"])):
                raise ValueError("CMA cohort projection differs from its exact observed pool versions")
        if u.best:
            best_ref = (SolutionRef.from_dict(u.best["ref"]),)
            candidate = control.solution_pool.read(best_ref, allow_pending=True).numeric_matrix[0]
            objective = control.solution_pool.read_raw_feedback(best_ref, allow_pending=True)[0][0, 0]
            if not np.array_equal(candidate, u.best["candidate"]) or objective != u.best["objective"]:
                raise ValueError("CMA incumbent differs from its exact evaluated pool version")
        payloads = list(u.last_cohort.get("refs", ())) + ([u.best["ref"]] if u.best else [])
        refs = tuple(dict.fromkeys(SolutionRef.from_dict(r) for r in payloads))
        if refs:
            control.solution_pool.read(refs, allow_pending=True)
        return refs

    def _get_algorithm_state(self):
        states = {}
        for name, component in self._components.items():
            if getattr(component, "stateless", False) is not True:
                state = component.get_state()
                if not isinstance(state, Mapping):
                    raise TypeError(f"CMA {name} get_state must return a Mapping")
                states[name] = decode_unit_value(encode_unit_value(dict(state)))
        return {"configuration": self.configuration_identity, "components": states}

    def _set_algorithm_state(self, state):
        if state.get("configuration") != self.configuration_identity:
            raise ValueError("CMA checkpoint configuration differs from configured components")
        expected = {name for name, component in self._components.items()
                    if getattr(component, "stateless", False) is not True}
        if not isinstance(state.get("components"), Mapping) or set(state["components"]) != expected:
            raise ValueError("CMA checkpoint stateful component set differs")
        previous = self._get_algorithm_state()["components"]
        try:
            for name in expected:
                self._components[name].set_state(decode_unit_value(encode_unit_value(state["components"][name])))
        except BaseException:
            for name in expected:
                self._components[name].set_state(previous[name])
            raise
