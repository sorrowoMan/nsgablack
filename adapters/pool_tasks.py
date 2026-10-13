"""Candidate handoff for existing role scheduling; no independent run loop."""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .role_adapters import RoleAdapter
from .strategy_task import StrategyTask
from .subpools import SubpoolSelection, adapter_path
from nsgablack.context_keys import KEY_PHASE, KEY_SEEDS, KEY_TASK, KEY_SOLUTION_INPUT_REF, KEY_SOLUTION_INPUT_MODE
from nsgablack.core.state.solution_pool import SolutionRef, SolutionStamp
from nsgablack.core.state.pool_views import ObjectiveProjection


def _callable_id(value):
    if isinstance(value, str):
        return value
    module, name = getattr(value, "__module__", None), getattr(value, "__qualname__", None)
    if not module or not name or "<lambda>" in name:
        raise TypeError("pool task callbacks must be named functions with stable module/qualname")
    return f"{module}.{name}"


@dataclass(frozen=True)
class PoolTaskSpec:
    """Select a subpool once per request and run bounded searches on its refs.

    Omitted ``select`` reads published mother-pool candidates. A named subpool
    must exist; a callback returns explicit source refs. ``count`` is per worker,
    or 'all' for the whole selection. Refine runs one seed per trajectory; compete
    presents the selected batch to a population's ordinary admission/selection.
    ``request_key`` defaults to phase; use a stable explicit key for repeated
    triggers in the same phase. A request never silently replaces active work.

    A SubpoolSelection selects directions once for the whole role; count then
    means seeds per selected view (default one). Partition distributes these
    jobs; shared repeats them explicitly. Each job freezes its projection.
    """
    select: Callable | str | SubpoolSelection | None = None
    mode: str = "refine"
    steps: int = 5
    output: str | None = None
    request_key: Callable | None = None
    phases: tuple[str, ...] = ()
    count: int | str | None = None
    distribution: str | None = None
    on_insufficient: str = "error"
    shuffle: bool = True

    def __post_init__(self):
        if self.select is not None and not (isinstance(self.select, SubpoolSelection) or callable(self.select) or isinstance(self.select, str) and self.select.strip()):
            raise TypeError("pool task select must be None, a selector or subpool name")
        if self.mode not in {"refine", "initialize", "compete"}:
            raise ValueError("unknown pool task input mode")
        if type(self.steps) is not int or self.steps < 1:
            raise ValueError("pool task steps must be a positive integer")
        if self.output is not None and (not isinstance(self.output, str) or not self.output.strip()):
            raise ValueError("pool task output must be a subpool name")
        if self.request_key is not None and not callable(self.request_key):
            raise TypeError("pool task request_key must be callable")
        if not isinstance(self.phases, tuple) or any(not isinstance(p, str) or not p for p in self.phases):
            raise TypeError("pool task phases must be a tuple of nonempty names")
        if self.select is not None and not isinstance(self.select, SubpoolSelection):
            _callable_id(self.select)
        if self.request_key is not None:
            _callable_id(self.request_key)
        if self.count is not None and not (self.count == "all" or type(self.count) is int and self.count > 0):
            raise ValueError("pool task count must be a positive integer, 'all', or None")
        if self.distribution not in {None, "partition", "independent", "shared"}:
            raise ValueError("unknown pool task distribution")
        if self.on_insufficient not in {"error", "wait", "available"}:
            raise ValueError("unknown pool task shortage policy")
        if type(self.shuffle) is not bool:
            raise TypeError("pool task shuffle must be a boolean")

    def identity(self):
        selection = (self.select.identity() if isinstance(self.select, SubpoolSelection)
                     else None if self.select is None else _callable_id(self.select))
        return dict(select=selection, mode=self.mode, steps=self.steps,
                    output=self.output, phases=self.phases,
                    count=self.count, distribution=self.distribution,
                    on_insufficient=self.on_insufficient, shuffle=self.shuffle,
                    request_key=None if self.request_key is None else _callable_id(self.request_key))


class PoolTaskAdapter(RoleAdapter):
    """Reusable input/result binding used by StrategyRouterAdapter roles.

    The child executes one normal proposal/update per dispatch. Its state is an
    ordinary transaction child. Task queues and views share SolutionPool's
    existing checkpoint, rollback, admission and retention mechanisms.
    """
    context_optional = (KEY_SOLUTION_INPUT_REF, KEY_SOLUTION_INPUT_MODE)

    def __init__(self, inner, spec: PoolTaskSpec, *, role, worker=0, workers=1, namespace="root"):
        super().__init__(role, inner, name=f"pool_task:{role}:{worker}", context_requires=(KEY_TASK,))
        self.spec, self.worker, self.workers = spec, worker, workers
        self.namespace = namespace
        self._local = {}
        self._rng = None
        self._creator_path = None
        if type(workers) is not int or workers < 1 or type(worker) is not int or not 0 <= worker < workers:
            raise ValueError("pool task worker must be an index within positive workers")
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("pool task namespace must be nonempty")
        self.validate_pool_task()

    def validate_pool_task(self, root=None):
        if not isinstance(self.spec, PoolTaskSpec):
            raise TypeError("role pool_task must be PoolTaskSpec")
        mode = "initialize" if self.spec.mode == "refine" else self.spec.mode
        if mode not in self.inner.pool_input_modes:
            raise ValueError(f"{self.inner.name} does not support pool {mode}")
        if self.spec.mode == "refine" and not self.inner.supports_pool_restart:
            raise ValueError(f"{self.inner.name} does not support explicit search restart")
        count = self.input_count
        if isinstance(self.spec.select, SubpoolSelection):
            if self.distribution == "independent":
                raise ValueError("projection subpool tasks use partition or shared distribution")
            if self.spec.mode != "refine" or not getattr(self.inner, "supports_objective_projection", False):
                raise ValueError("projection subpool tasks require a refiner supporting objective projections")
            if not getattr(self.spec.select.creator, "publishes_projection_subpools", False):
                raise ValueError("selected Adapter does not publish projection subpools")
            if root is not None:
                adapter_path(root, self.spec.select.creator)
        if count != "all" and (type(count) is not int or count < 1):
            raise ValueError(f"{self.inner.name} must declare default_pool_input_count or use explicit count")

    @property
    def input_count(self):
        if self.spec.count is not None:
            return self.spec.count
        if self.spec.mode == "initialize":
            return self.inner.default_pool_input_count()
        return 1 if self.spec.mode == "refine" else "all"

    @property
    def distribution(self):
        return self.spec.distribution or ("independent" if self.spec.mode == "initialize" else "partition")

    def setup(self, control):
        self.validate_pool_task(control.adapter)
        self._creator_path = (adapter_path(control.adapter, self.spec.select.creator)
                              if isinstance(self.spec.select, SubpoolSelection) else None)
        super().setup(control)
        control.solution_pool.checkpoint_required = True
        # Tasks are serialized inside the root Adapter component. Silently
        # skipping an invalid child would mismatch the restored pool cursors.
        control.adapter.checkpoint_required = True
        self._local = {}
        # fork_rng may cache streams by name. Keep an owned generator even when
        # nested routers use identical role names; checkpoint restores no aliases.
        stream = self.create_local_rng(control)
        self._rng = np.random.default_rng(int(stream.integers(0, 2**63 - 1)))

    @property
    def task_status(self):
        return {key: copy.deepcopy(self._local.get(key))
                for key in ("request", "status", "next", "count", "steps", "output")}

    def _namespace(self, context):
        task = StrategyTask.from_context(context)
        return "/".join((*task.owner_path[:-1], self.namespace))

    def _name(self, value, context):
        return f"{self._namespace(context)}/{value}"

    def _start_request(self, control, context):
        pool = control.solution_pool
        request = (self.spec.request_key(control, context) if self.spec.request_key
                   else str(context.get(KEY_PHASE, "default")))
        if not isinstance(request, str) or not request:
            raise ValueError("pool task request key must be a nonempty string")
        if self._local.get("status") == "running" or self._local.get("request") == request:
            return
        if self.spec.mode == "initialize" and self.spec.request_key is None and self._local.get("status") == "done":
            return
        digest = hashlib.sha256(request.encode()).hexdigest()[:24]
        base = self._name(f"task:{self.role}/{digest}", context)
        # One allocation shared by all role instances, retained across retries.
        # The empty marker records selection completion without retaining values.
        if not pool.has_subpool(base) and isinstance(self.spec.select, SubpoolSelection):
            allocations = self._allocate_projection_views(pool)
            if allocations is None:
                self._local = {}
                return
            pool.create_subpool(base)
            for i, jobs in enumerate(allocations):
                pool.create_subpool(f"{base}/{i}",
                    [SolutionRef.from_dict(job["ref"]) for job in jobs], metadata={"jobs": jobs})
        if not pool.has_subpool(base):
            if self.spec.select is None:
                refs = pool.select(stage=None)
            elif isinstance(self.spec.select, str):
                source = self._name(self.spec.select, context)
                if not pool.has_subpool(source):
                    raise ValueError(f"pool task input subpool does not exist: {source}")
                refs = pool.subpool_refs(source)
            else:
                refs = tuple(self.spec.select(control, context))
            # Exact versions are the sampling objects; equal numbers never
            # collapse distinct identities. A worker uses each reference once.
            refs = tuple(dict.fromkeys(refs))
            allocations = self._allocate(refs)
            if allocations is None:
                # A new request waiting for input must not inherit the previous
                # request's done status and fall through to ordinary search.
                self._local = {}
                return
            pool.create_subpool(base)
            for i, selected in enumerate(allocations):
                pool.create_subpool(f"{base}/{i}", selected)
        view = f"{base}/{self.worker}"
        refs = pool.subpool_refs(view)
        self._local = dict(request=request, status="running" if refs else "done",
                           view=view, next=0, count=len(refs), steps=0,
                           input=None, results=[], output=None)
        if isinstance(self.spec.select, SubpoolSelection):
            self._local["jobs"] = pool.subpool_metadata(view)["jobs"]
        if self.spec.output is not None:
            output = self._name(self.spec.output, context)
            if not pool.has_subpool(output):
                pool.create_subpool(output)
            self._local["output"] = output
        if not refs:
            pool.drop_subpool(view)

    def _allocate(self, refs):
        count, mode = self.input_count, self.distribution
        needed = 1 if count == "all" else count * (self.workers if mode == "partition" else 1)
        if len(refs) < needed:
            if self.spec.on_insufficient == "error":
                raise ValueError(f"pool task {self.role} needs {needed} distinct references; available={len(refs)}")
            if self.spec.on_insufficient == "wait" or not refs:
                return None
        def sample(limit):
            indices = self._rng.permutation(len(refs)) if self.spec.shuffle else range(len(refs))
            return tuple(refs[i] for i in list(indices)[:limit])
        if mode == "partition":
            selected = sample(len(refs) if count == "all" else count * self.workers)
            return tuple(selected[i::self.workers] for i in range(self.workers))
        limit = len(refs) if count == "all" else count
        if mode == "shared":
            selected = sample(limit)
            return (selected,) * self.workers
        return tuple(sample(limit) for _ in range(self.workers))

    def _allocate_projection_views(self, pool):
        names = pool.projection_subpools(self._creator_path)
        count = self.spec.select.count
        wanted = len(names) if count is None else count
        if not names or len(names) < wanted:
            if self.spec.on_insufficient == "error":
                raise ValueError(f"creator has {len(names)} projection subpools; requested {wanted or 'all'}")
            if self.spec.on_insufficient == "wait" or not names:
                return None
        if count is not None or self.spec.shuffle:
            names = tuple(names[i] for i in self._rng.permutation(len(names))[:wanted])
        jobs = []
        for name in names:
            metadata = pool.subpool_metadata(name)
            refs = pool.subpool_refs(name)
            n = len(refs) if self.input_count == "all" else self.input_count
            if len(refs) < n:
                if self.spec.on_insufficient == "error":
                    raise ValueError(f"projection subpool {name} needs {n} candidates; available={len(refs)}")
                if self.spec.on_insufficient == "wait":
                    return None
            order = self._rng.permutation(len(refs)) if self.spec.shuffle else range(len(refs))
            jobs.extend(dict(source_view=name, created_by=metadata["created_by"], slot=metadata["slot"],
                projection=metadata["projection"], ref=refs[i].as_dict()) for i in list(order)[:n])
        # View selection is once per request, never once per worker or per step.
        if self.distribution == "partition":
            return tuple(jobs[i::self.workers] for i in range(self.workers))
        return tuple(copy.deepcopy(jobs) for _ in range(self.workers))

    def _context(self, context):
        if self._local.get("passthrough"):
            return context
        local = dict(context)
        # Pool references are the input authority for this task. Legacy numeric
        # seeds are not a second source, nor inherited input IDs from ancestors.
        local.pop(KEY_SOLUTION_INPUT_REF, None)
        local.pop(KEY_SOLUTION_INPUT_MODE, None)
        local[KEY_SEEDS] = ()
        local.update(self._local.get("call_input", {}))
        return local

    def propose(self, control, context):
        if self.spec.phases and context.get(KEY_PHASE) not in self.spec.phases:
            if self._local.get("status") == "running":
                return []  # Pause unfinished work; do not mutate it as a different task.
            self._local["passthrough"] = True
            return super().propose(control, context)
        self._local["passthrough"] = False
        self._start_request(control, context)
        if self._local.get("status") != "running":
            if self._local.get("status") == "done" and self.spec.mode in {"initialize", "compete"}:
                self._local["passthrough"] = True
                return super().propose(control, context)
            return []
        pool = control.solution_pool
        if self._local["input"] is None:
            refs = pool.subpool_refs(self._local["view"])
            selected = refs[self._local["next"]:self._local["next"]+1] if self.spec.mode == "refine" else refs
            self._local["input"] = pool.bind_input(selected)
            self._local["steps"] = 0
            self._local["results"] = []
            if self.spec.mode == "refine":
                self.inner.restart_search(control, context)
        key = self._local["input"]
        remaining = pool.input_remaining(key)
        self._local["call_input"] = ({KEY_SOLUTION_INPUT_REF: key,
            KEY_SOLUTION_INPUT_MODE: "initialize" if self.spec.mode == "refine" else self.spec.mode} if remaining else {})
        self._local["stamp"] = pool.timestamp.as_dict()
        proposed = super().propose(control, self._context(context))
        consumed = remaining - pool.input_remaining(key)
        if consumed not in (0, len(proposed)) or remaining and consumed == 0:
            raise ValueError("pool task must submit its input candidates before generating neighbors")
        self._local["intake"] = consumed
        return proposed

    def _proposal_contexts(self, proposed_count, context):
        return super()._proposal_contexts(proposed_count, self._context(context))

    def proposal_repair_children(self, repair, context):
        return super().proposal_repair_children(repair, self._context(context))

    def on_proposal_disposition(self, control, disposition, context):
        intake = 0 if self._local.get("passthrough") else self._local.get("intake", 0)
        if intake:
            control.solution_pool.settle_input(self._local["input"], intake, disposition.accepted_indices)
        super().on_proposal_disposition(control, disposition, self._context(context))
        if intake and self.spec.mode == "refine" and not disposition.accepted_indices:
            # The input cursor was restored. Discard the unaccepted seed draft
            # too, so retry consumes that exact reference through initialization.
            self.inner.restart_search(control, self._context(context))

    def update(self, control, candidates, feedback, context):
        projected = feedback
        if not self._local.get("passthrough") and "jobs" in self._local:
            job = self._local["jobs"][self._local["next"]]
            projected = ObjectiveProjection.from_dict(job["projection"]).apply(feedback)
        super().update(control, candidates, projected, self._context(context))
        if self._local.get("passthrough") or not len(candidates):
            return
        pool = control.solution_pool
        refs = pool.accepted_refs_since(self.candidate_tokens_for(control, candidates),
                                       SolutionStamp.from_dict(self._local["stamp"]))
        self._local["results"].extend(ref.as_dict() for ref in refs)
        self._local["steps"] += 1
        if pool.input_remaining(self._local["input"]):
            return
        if self.spec.mode == "refine" and self._local["steps"] < self.spec.steps:
            return
        if self._local["output"] is not None:
            pool.add_to_subpool(self._local["output"], self.get_solution_pool_roots(control))
        self._local["next"] += 1 if self.spec.mode == "refine" else self._local["count"]
        self._local["input"], self._local["results"] = None, []
        if self._local["next"] >= self._local["count"]:
            self._local["status"] = "done"
            pool.drop_subpool(self._local["view"])

    def get_solution_pool_roots(self, control):
        return tuple(SolutionRef.from_dict(ref) for ref in self._local.get("results", ()))

    def get_state(self):
        return {**super().get_state(), "pool_task": copy.deepcopy(self._local),
                "pool_task_rng": self._rng_state(),
                "pool_task_spec": self._identity()}

    def _identity(self):
        identity = {**self.spec.identity(), "worker": self.worker, "workers": self.workers,
                "namespace": self.namespace, "effective_count": self.input_count,
                "effective_distribution": self.distribution}
        if isinstance(self.spec.select, SubpoolSelection):
            identity["creator_path"] = self._creator_path
        return identity

    def set_state(self, state):
        if state.get("pool_task_spec") != self._identity():
            raise ValueError("pool task checkpoint configuration mismatch")
        self._validate_local(state["pool_task"])
        super().set_state(state)
        self._local = copy.deepcopy(state["pool_task"])
        self._restore_rng(state["pool_task_rng"])

    def _rng_state(self):
        return None if self._rng is None else copy.deepcopy(self._rng.bit_generator.state)

    def _restore_rng(self, state):
        if state is None:
            self._rng = None
        else:
            rng = np.random.default_rng()
            rng.bit_generator.state = copy.deepcopy(state)
            self._rng = rng

    def _validate_local(self, state):
        if not isinstance(state, dict):
            raise TypeError("pool task state must be a mapping")
        if "request" not in state:
            if set(state) - {"passthrough"}:
                raise ValueError("pool task state is missing its request")
            return
        if state.get("status") not in {"running", "done"}:
            raise ValueError("invalid pool task status")
        if any(type(state.get(key)) is not int or state[key] < 0 for key in ("next", "count", "steps")):
            raise ValueError("invalid pool task progress")
        if state["next"] > state["count"] or (state["status"] == "done" and state["next"] != state["count"]):
            raise ValueError("pool task progress exceeds its selection")
        for key in ("request", "view"):
            if not isinstance(state.get(key), str) or not state[key]:
                raise ValueError("pool task is missing its selection identity")
        for key in ("input", "output"):
            if state.get(key) is not None and (not isinstance(state[key], str) or not state[key]):
                raise ValueError(f"pool task {key} must be a nonempty reference or None")
        if "stamp" in state:
            SolutionStamp.from_dict(state["stamp"])
        if not isinstance(state.get("results"), list):
            raise TypeError("pool task results must be a list of references")
        for ref in state["results"]:
            SolutionRef.from_dict(ref)
        if isinstance(self.spec.select, SubpoolSelection) and "jobs" not in state:
            raise ValueError("projection task checkpoint is missing its jobs")
        if "jobs" in state:
            if not isinstance(state["jobs"], list) or len(state["jobs"]) != state["count"]:
                raise ValueError("projection jobs must align with task progress")
            for job in state["jobs"]:
                if set(job) != {"source_view", "created_by", "slot", "projection", "ref"}:
                    raise ValueError("invalid projection task job")
                ObjectiveProjection.from_dict(job["projection"])
                SolutionRef.from_dict(job["ref"])
                if (not isinstance(job["source_view"], str) or not job["source_view"]
                        or not isinstance(job["created_by"], list) or not job["created_by"]
                        or any(not isinstance(p, str) or not p for p in job["created_by"])
                        or type(job["slot"]) is not int or job["slot"] < 0):
                    raise ValueError("projection task requires source view, creator and slot")
                if tuple(job["created_by"]) != self._creator_path:
                    raise ValueError("projection task creator differs from its selector")

    def snapshot_step_state(self):
        return {**super().snapshot_step_state(), "pool_task": copy.deepcopy(self._local),
                "pool_task_rng": self._rng_state()}

    def restore_step_state(self, state):
        self._validate_local(state["pool_task"])
        super().restore_step_state(state)
        self._local = copy.deepcopy(state["pool_task"])
        self._restore_rng(state["pool_task_rng"])


__all__ = ["PoolTaskSpec", "PoolTaskAdapter"]
