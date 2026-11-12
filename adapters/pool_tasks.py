"""Candidate handoff for existing role scheduling; no independent run loop."""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .role_adapters import RoleAdapter
from .strategy_task import StrategyTask
from .change_access import scoped_change_access
from .pool_scope import KEY_WORKING_POOL, working_pool_source
from .subpools import SubpoolSelection, adapter_path
from nsgablack.context_keys import KEY_PHASE, KEY_SEEDS, KEY_TASK, KEY_SOLUTION_INPUT_REF, KEY_SOLUTION_INPUT_MODE
from nsgablack.core.state.solution_pool import SolutionPool, SolutionRef, SolutionStamp
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

    Omitted ``select`` reads the nearest composite working area, or published
    root-pool candidates when no working area is bound. A named subpool
    must exist; a callback returns explicit source refs. ``count`` is per worker,
    or 'all' for the whole selection. Refine runs one seed per trajectory; compete
    presents the selected batch to a population's ordinary admission/selection.
    ``request_key`` defaults to phase; use a stable explicit key for repeated
    triggers in the same phase. A request never silently replaces active work.

    A SubpoolSelection selects directions once for the whole role; count then
    means seeds per selected view (default one). Partition distributes these
    jobs; shared repeats them explicitly. Each job freezes its projection.
    Refinement always publishes its final selections. ``output`` optionally
    retains an aggregate history of all admitted trials; omitting it does not
    disable final-result delivery.

    Ordinary change functions may read current input references and their
    owned parents. Additional donors require ``change_sources`` (exact public
    subpool names, without a task namespace) or ``change_allow_main=True``.
    Nested task declarations can only narrow the enclosing donor permissions.
    ``on_insufficient="available"`` completes an empty request without creating
    a result collection; ``"wait"`` retains waiting semantics instead.
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
    change_sources: tuple[str, ...] = ()
    change_allow_main: bool = False

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
        if (not isinstance(self.change_sources, tuple)
                or any(not isinstance(name, str) or not name.strip() for name in self.change_sources)
                or len(set(self.change_sources)) != len(self.change_sources)):
            raise ValueError("pool task change_sources must be distinct nonempty subpool names")
        if type(self.change_allow_main) is not bool:
            raise TypeError("pool task change_allow_main must be a boolean")

    def identity(self):
        selection = (self.select.identity() if isinstance(self.select, SubpoolSelection)
                     else None if self.select is None else _callable_id(self.select))
        return dict(select=selection, mode=self.mode, steps=self.steps,
                    output=self.output, phases=self.phases,
                    count=self.count, distribution=self.distribution,
                    on_insufficient=self.on_insufficient, shuffle=self.shuffle,
                    change_sources=self.change_sources, change_allow_main=self.change_allow_main,
                    request_key=None if self.request_key is None else _callable_id(self.request_key))


class PoolTaskAdapter(RoleAdapter):
    """Reusable input/result binding used by StrategyRouterAdapter roles.

    The child executes one normal proposal/update per dispatch. Its state is an
    ordinary transaction child. Task queues and views share SolutionPool's
    existing checkpoint, rollback, admission and retention mechanisms.
    """
    context_optional = (KEY_SOLUTION_INPUT_REF, KEY_SOLUTION_INPUT_MODE, KEY_WORKING_POOL)
    state_recovery_level = "L2"
    state_recovery_notes = "Restores frozen pool inputs, task interpretation, progress and RNG; child state restores independently."

    def supports_population_state_delivery(self):
        # A pool task is an input policy owner, not a transparent population
        # wrapper. Global initialization must not bypass its frozen seed spec.
        return False

    def set_population_state(self, control, batch, feedback, *, solution_refs, provenance):
        return False

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
        if self.spec.mode == "refine" and not callable(self.inner.get_pool_refinement_results):
            raise ValueError("refinement output requires explicit get_pool_refinement_results")
        if isinstance(self.spec.select, SubpoolSelection):
            if self.distribution == "independent":
                raise ValueError("projection subpool tasks use partition or shared distribution")
            if self.spec.mode != "refine":
                raise ValueError("created subpool tasks require refine mode")
            creator = self.spec.select.creator.pool_result_owner()
            if not (getattr(creator, "publishes_projection_subpools", False)
                    or getattr(creator, "publishes_subpools", False)
                    or callable(creator.get_pool_refinement_results)):
                raise ValueError("selected Adapter does not publish subpools")
            if root is not None:
                adapter_path(root, creator)
                self._validate_projection_publisher(root, creator, set())
        if count != "all" and (type(count) is not int or count < 1):
            raise ValueError(f"{self.inner.name} must declare default_pool_input_count or use explicit count")

    @staticmethod
    def _validate_projection_publisher(root, creator, visiting):
        """A refiner publishes views only through an explicitly assembled task.

        Supporting scalar feedback alone is not a publication contract. Follow
        declared producer dependencies to reject circular tasks at assembly.
        """
        adapter_path(root, creator)
        if id(creator) in visiting:
            raise ValueError("projection subpool task dependencies contain a cycle")
        if creator.publishes_projection_subpools or creator.publishes_subpools:
            return
        visiting = {*visiting, id(creator)}
        pending = [root]
        while pending:
            adapter = pending.pop()
            if isinstance(adapter, PoolTaskAdapter) and adapter.inner.pool_result_owner() is creator:
                if adapter.spec.mode != "refine" or not callable(creator.get_pool_refinement_results):
                    raise ValueError("selected refiner needs a projection pool task")
                if isinstance(adapter.spec.select, SubpoolSelection):
                    PoolTaskAdapter._validate_projection_publisher(
                        root, adapter.spec.select.creator.pool_result_owner(), visiting)
                return
            pending.extend(adapter.step_transaction_children())
        raise ValueError("selected refiner has no projection pool task")

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
        self._creator_path = (adapter_path(control.adapter, self.spec.select.creator.pool_result_owner())
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

    def _request_key(self, control, context):
        """Resolve one request identity without changing its input or progress.

        An enclosing execution plan may specialize this seam to bind repeated
        activations. Ordinary Router tasks retain their explicit callback or
        phase identity, including initialize-once semantics.
        """
        return (self.spec.request_key(control, context) if self.spec.request_key
                else str(context.get(KEY_PHASE, "default")))

    def _finish_empty_request(self, request, *, uses_view_jobs):
        self._local = dict(request=request, status="done", view=None, next=0,
                           count=0, steps=0, input=None, results=[], output=None,
                           result_views=[], uses_view_jobs=uses_view_jobs)
        if uses_view_jobs:
            self._local["jobs"] = []

    def _start_request(self, control, context):
        pool = control.solution_pool
        request = self._request_key(control, context)
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
        job_source = isinstance(self.spec.select, SubpoolSelection)
        source = None
        if isinstance(self.spec.select, str):
            job_source = self.spec.mode == "refine"
            # Another worker may already have frozen this whole request. Its
            # retained queue survives source updates, release and restoration.
            if not pool.has_subpool(base):
                source = self._name(self.spec.select, context)
                if not pool.has_subpool(source):
                    raise ValueError(f"pool task input subpool does not exist: {source}")
                self._validate_view_consumer(pool.subpool_metadata(source))
        if not pool.has_subpool(base) and job_source:
            allocations = self._allocate_projection_views(pool) if source is None else self._allocate_views(pool, (source,), named=True)
            if allocations is None:
                self._local = {}
                return
            if not any(allocations):
                self._finish_empty_request(request, uses_view_jobs=True)
                return
            pool.create_subpool(base)
            for i, jobs in enumerate(allocations):
                pool.create_subpool(f"{base}/{i}",
                    [SolutionRef.from_dict(job["ref"]) for job in jobs], metadata={"jobs": jobs})
        if not pool.has_subpool(base):
            if self.spec.select is None:
                refs = pool.select(stage=None, subpool=working_pool_source(pool, context))
            elif isinstance(self.spec.select, str):
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
            if not any(allocations):
                self._finish_empty_request(request, uses_view_jobs=False)
                return
            pool.create_subpool(base)
            for i, selected in enumerate(allocations):
                pool.create_subpool(f"{base}/{i}", selected)
        view = f"{base}/{self.worker}"
        refs = pool.subpool_refs(view, allow_pending=True)
        if not refs:
            # Another worker can own a nonempty slice of the same allocation.
            # Preserve its marker and queue; this worker owns no readable view
            # or output, including when an idle step rolls pool staging back.
            pool.drop_subpool(view)
            self._finish_empty_request(request, uses_view_jobs=job_source)
            return
        self._local = dict(request=request, status="running" if refs else "done",
                           view=view, next=0, count=len(refs), steps=0,
                           input=None, results=[], output=None, result_views=[],
                           uses_view_jobs=job_source)
        if "jobs" in pool.subpool_metadata(view):
            self._local["jobs"] = pool.subpool_metadata(view)["jobs"]
        if self.spec.output is not None:
            output = self._name(self.spec.output, context)
            if not pool.has_subpool(output):
                pool.create_subpool(output)
            self._local["output"] = output

    def _allocate(self, refs):
        count, mode = self.input_count, self.distribution
        needed = 1 if count == "all" else count * (self.workers if mode == "partition" else 1)
        if len(refs) < needed:
            if self.spec.on_insufficient == "error":
                raise ValueError(f"pool task {self.role} needs {needed} distinct references; available={len(refs)}")
            if self.spec.on_insufficient == "wait":
                return None
            if not refs:
                return tuple(() for _ in range(self.workers))
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
        names = pool.subpools_created_by(self._creator_path)
        count = self.spec.select.count
        wanted = len(names) if count is None else count
        if not names or len(names) < wanted:
            if self.spec.on_insufficient == "error":
                raise ValueError(f"creator has {len(names)} projection subpools; requested {wanted or 'all'}")
            if self.spec.on_insufficient == "wait":
                return None
            if not names:
                return tuple(() for _ in range(self.workers))
        if count is not None or self.spec.shuffle:
            names = tuple(names[i] for i in self._rng.permutation(len(names))[:wanted])
        return self._allocate_views(pool, names)

    def _validate_view_consumer(self, metadata):
        if metadata["kind"] == "objective_projection":
            if self.spec.mode != "refine" or not self.inner.supports_objective_projection:
                raise ValueError("projection subpool tasks require a refiner supporting objective projections")
        if self.spec.mode == "refine" and self.distribution == "independent":
            raise ValueError("view tasks use partition or shared distribution")

    def _allocate_views(self, pool, names, *, named=False):
        jobs = []
        for name in names:
            metadata = pool.subpool_metadata(name)
            self._validate_view_consumer(metadata)
            if not metadata["published"]:
                if self.spec.on_insufficient == "wait":
                    return None
                raise ValueError(f"pool task input view is uncommitted: {name}")
            refs = pool.subpool_refs(name)
            if named and metadata["kind"] != "objective_projection":
                allocations = self._allocate(refs)
                if allocations is None:
                    return None
                descriptor = pool.subpool_descriptor(name)
                return tuple([dict(source_view=name, source_descriptor=copy.deepcopy(descriptor),
                    created_by=metadata["created_by"], slot=None, projection=None, ref=ref.as_dict())
                    for ref in selected] for selected in allocations)
            n = len(refs) if self.input_count == "all" else self.input_count
            if len(refs) < n:
                if self.spec.on_insufficient == "error":
                    raise ValueError(f"projection subpool {name} needs {n} candidates; available={len(refs)}")
                if self.spec.on_insufficient == "wait":
                    return None
            order = self._rng.permutation(len(refs)) if self.spec.shuffle else range(len(refs))
            descriptor = pool.subpool_descriptor(name)
            jobs.extend(dict(source_view=name, source_descriptor=copy.deepcopy(descriptor),
                created_by=metadata["created_by"], slot=metadata.get("slot"),
                projection=metadata.get("projection"), ref=refs[i].as_dict()) for i in list(order)[:n])
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

    def _change_seed_refs(self, control):
        # A finished initialization task has released its queue. Its child's
        # current parents still carry exact source_refs in ChangeRequest.
        if self._local.get("status") != "running":
            return ()
        refs = control.solution_pool.subpool_refs(self._local["view"], allow_pending=True)
        if self.spec.mode == "refine":
            return refs[self._local["next"]:self._local["next"] + 1]
        return refs

    def _propose_with_change_access(self, control, context):
        # Additional sources use exact public SolutionPool names. Unlike the
        # legacy task select/output names, no task namespace is prepended.
        with scoped_change_access(self._change_seed_refs(control),
                                 subpools=self.spec.change_sources,
                                 allow_main=self.spec.change_allow_main):
            return super().propose(control, context)

    def propose(self, control, context):
        if self.spec.phases and context.get(KEY_PHASE) not in self.spec.phases:
            if self._local.get("status") == "running":
                return []  # Pause unfinished work; do not mutate it as a different task.
            self._local["passthrough"] = True
            return self._propose_with_change_access(control, context)
        self._local["passthrough"] = False
        self._start_request(control, context)
        if self._local.get("status") != "running":
            if self._local.get("status") == "done" and self.spec.mode in {"initialize", "compete"}:
                self._local["passthrough"] = True
                return self._propose_with_change_access(control, context)
            return []
        pool = control.solution_pool
        if "jobs" in self._local:
            # Queue membership and its frozen task interpretation must remain
            # aligned after restore; a valid projection on the wrong seed is
            # still a semantic error. Do not reread the changing source view.
            jobs = self._local["jobs"]
            refs = pool.subpool_refs(self._local["view"], allow_pending=True)
            if (refs != tuple(SolutionRef.from_dict(job["ref"]) for job in jobs)
                    or pool.subpool_metadata(self._local["view"]).get("jobs") != jobs):
                raise ValueError("projection task jobs differ from their frozen input queue")
        if self._local["input"] is None:
            refs = pool.subpool_refs(self._local["view"], allow_pending=True)
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
        proposed = self._propose_with_change_access(control, self._context(context))
        consumed = remaining - pool.input_remaining(key)
        if consumed not in (0, len(proposed)) or remaining and consumed == 0:
            raise ValueError("pool task must submit its input candidates before generating neighbors")
        self._local["intake"] = consumed
        return proposed

    def _proposal_contexts(self, proposed_count, context):
        return super()._proposal_contexts(proposed_count, self._context(context))

    def get_empty_proposal_outcome(self, control, context):
        outcome = super().get_empty_proposal_outcome(control, context)
        if (self._local.get("status") == "running"
                and not self._local.get("passthrough")
                and outcome is not None and outcome.terminal
                and outcome.status != "cancelled" and not outcome.stop_requested):
            raise RuntimeError(
                "pool task inner terminal before request completion is unsupported; "
                "remaining seeds and final-result publication must not be skipped")
        return outcome

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
            if job["projection"] is not None:
                projected = ObjectiveProjection.from_dict(job["projection"]).apply(feedback)
        # Update-side collection decisions have the same declared input scope
        # as proposal-side changes, including every enclosing task restriction.
        with scoped_change_access(self._change_seed_refs(control),
                                 subpools=self.spec.change_sources,
                                 allow_main=self.spec.change_allow_main):
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
        if self.spec.mode == "refine":
            self._publish_refinement_view(control)
        self._local["next"] += 1 if self.spec.mode == "refine" else self._local["count"]
        self._local["input"], self._local["results"] = None, []
        if self._local["next"] >= self._local["count"]:
            self._local["status"] = "done"
            pool.drop_subpool(self._local["view"])

    def _publish_refinement_view(self, control):
        """Publish selected results, distinct from the aggregate trial output.

        The Adapter declares its result. Retention roots protect state and are
        deliberately not interpreted as a selection policy here.
        """
        pool = control.solution_pool
        job = self._local["jobs"][self._local["next"]] if "jobs" in self._local else None
        refs = tuple(self.inner.get_pool_refinement_results(control))
        if not refs:
            raise ValueError("completed projected refinement has no selected result")
        name = self._refinement_result_name(self._local["next"])
        creator = adapter_path(control.adapter, self.inner.pool_result_owner())
        if job is not None and job["projection"] is not None:
            pool.publish_projection_subpool(name, refs, created_by=creator, slot=job["slot"],
                projection=ObjectiveProjection.from_dict(job["projection"]), parent=job["source_descriptor"])
        else:
            pool.publish_subpool_view(name, refs, created_by=creator,
                parent=None if job is None else job["source_descriptor"])
        metadata = pool.subpool_metadata(name)
        # This receipt records the staged view's identity/interpretation; the
        # Pool remains authoritative and the getter additionally requires its
        # normal publication commit before the receipt is usable.
        descriptor = dict(pool_id=pool.pool_id, name=name,
            view_id=metadata["view_id"], revision=metadata["revision"],
            ancestors=pool._view_ancestors(metadata))
        self._local["result_views"].append(dict(descriptor=descriptor,
            kind=metadata["kind"], created_by=copy.deepcopy(metadata["created_by"]),
            projection=copy.deepcopy(metadata.get("projection")),
            slot=metadata.get("slot"), refs=[ref.as_dict() for ref in refs]))

    def _refinement_result_name(self, index, *, state=None):
        state = self._local if state is None else state
        if state["output"] is None:
            base = state["view"].rsplit("/", 1)[0]
            return f"{base}/results/{self.worker}/{index}"
        request_id = hashlib.sha256(state["request"].encode()).hexdigest()[:24]
        return (f"{state['output']}/result:{self.role}/{request_id}/"
                f"{self.worker}/{index}")

    def get_pool_task_results(self, control):
        """Read this completed request's committed final selections in order.

        The aggregate output contains all admitted trials across requests. It
        is deliberately not used to deliver this request's selected results.
        """
        if self.spec.mode != "refine":
            raise ValueError("pool task results require a refine task")
        if self._local.get("status") != "done":
            raise RuntimeError("pool task results are unavailable before request completion")
        if self._local["count"] == 0:
            return ()
        self._validate_local(self._local)
        pool = control.solution_pool
        refs = []
        creator = list(adapter_path(control.adapter, self.inner.pool_result_owner()))
        for receipt in self._local["result_views"]:
            expected = receipt["descriptor"]
            if expected["pool_id"] != pool.pool_id:
                raise ValueError("pool task result belongs to another SolutionPool")
            name = expected["name"]
            if not pool.has_subpool(name) or not pool.subpool_metadata(name)["published"]:
                raise RuntimeError("pool task results are unavailable before result commit")
            metadata = pool.subpool_metadata(name)
            if (pool.subpool_descriptor(name) != expected
                    or metadata["kind"] != receipt["kind"]
                    or metadata["created_by"] != receipt["created_by"]
                    or receipt["created_by"] != creator
                    or metadata.get("projection") != receipt["projection"]
                    or metadata.get("slot") != receipt["slot"]):
                raise ValueError("pool task final-result view identity or interpretation changed")
            selected = pool.subpool_refs(name)
            if tuple(ref.as_dict() for ref in selected) != tuple(receipt["refs"]):
                raise ValueError("pool task final-result view members changed")
            refs.extend(selected)
        return tuple(refs)

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
        if not isinstance(state.get("request"), str) or not state["request"]:
            raise ValueError("pool task is missing its selection identity")
        empty_done = state["status"] == "done" and state["count"] == 0
        if not (empty_done and state.get("view") is None):
            if not isinstance(state.get("view"), str) or not state["view"]:
                raise ValueError("pool task is missing its selection identity")
        if empty_done and state.get("view") is None and any(
                state.get(key) is not None for key in ("input", "output")):
            raise ValueError("empty pool task must not retain input, view or output handles")
        for key in ("input", "output"):
            if state.get(key) is not None and (not isinstance(state[key], str) or not state[key]):
                raise ValueError(f"pool task {key} must be a nonempty reference or None")
        if not empty_done:
            request_id = hashlib.sha256(state["request"].encode()).hexdigest()[:24]
            suffix = f"/task:{self.role}/{request_id}/{self.worker}"
            if not state["view"].endswith(suffix) or len(state["view"]) <= len(suffix):
                raise ValueError("pool task selection differs from its request identity")
            namespace = state["view"][:-len(suffix)]
            output = None if self.spec.output is None else f"{namespace}/{self.spec.output}"
            if state.get("output") != output:
                raise ValueError("pool task output differs from its declared request")
        self._validate_result_views(state)
        if "stamp" in state:
            SolutionStamp.from_dict(state["stamp"])
        if not isinstance(state.get("results"), list):
            raise TypeError("pool task results must be a list of references")
        for ref in state["results"]:
            SolutionRef.from_dict(ref)
        if type(state.get("uses_view_jobs")) is not bool:
            raise ValueError("pool task checkpoint is missing its input view interpretation")
        expected_jobs = isinstance(self.spec.select, SubpoolSelection) or (self.spec.mode == "refine" and isinstance(self.spec.select, str))
        if state["uses_view_jobs"] != expected_jobs:
            raise ValueError("pool task checkpoint input view interpretation differs from its binding")
        if expected_jobs and "jobs" not in state:
            raise ValueError("projection task checkpoint is missing its jobs")
        if not state["uses_view_jobs"] and "jobs" in state:
            raise ValueError("pool task checkpoint has undeclared view jobs")
        if "jobs" in state:
            if not isinstance(state["jobs"], list) or len(state["jobs"]) != state["count"]:
                raise ValueError("projection jobs must align with task progress")
            for job in state["jobs"]:
                if set(job) != {"source_view", "source_descriptor", "created_by", "slot", "projection", "ref"}:
                    raise ValueError("invalid projection task job")
                if job["projection"] is not None:
                    ObjectiveProjection.from_dict(job["projection"])
                ref = SolutionRef.from_dict(job["ref"])
                descriptor = SolutionPool.validate_subpool_descriptor(
                    job["source_descriptor"], pool_id=ref.pool_id)
                if descriptor["name"] != job["source_view"]:
                    raise ValueError("projection job source differs from its frozen descriptor")
                if (not isinstance(job["source_view"], str) or not job["source_view"]
                        or (job["created_by"] is not None and (not isinstance(job["created_by"], list)
                            or not job["created_by"] or any(not isinstance(p, str) or not p for p in job["created_by"])))
                        or (job["slot"] is not None and (type(job["slot"]) is not int or job["slot"] < 0))):
                    raise ValueError("projection task requires source view, creator and slot")
                if isinstance(self.spec.select, SubpoolSelection) and tuple(job["created_by"] or ()) != self._creator_path:
                    raise ValueError("projection task creator differs from its selector")

    def _validate_result_views(self, state):
        receipts = state.get("result_views")
        if not isinstance(receipts, list):
            raise ValueError("pool task checkpoint is missing final-result identity receipts")
        expected_count = state["next"] if self.spec.mode == "refine" else 0
        if len(receipts) != expected_count:
            raise ValueError("pool task result receipts do not match completed seeds")
        fields = {"descriptor", "kind", "created_by", "projection", "slot", "refs"}
        for index, receipt in enumerate(receipts):
            if not isinstance(receipt, dict) or set(receipt) != fields:
                raise ValueError("invalid pool task final-result identity receipt")
            descriptor = SolutionPool.validate_subpool_descriptor(receipt["descriptor"])
            if descriptor["name"] != self._refinement_result_name(index, state=state):
                raise ValueError("pool task result receipt differs from its request")
            creator = receipt["created_by"]
            if (not isinstance(creator, list) or not creator
                    or any(not isinstance(part, str) or not part or "/" in part for part in creator)):
                raise ValueError("pool task result receipt requires a stable creator path")
            if not isinstance(receipt["refs"], list) or not receipt["refs"]:
                raise ValueError("pool task result receipt requires selected candidates")
            for value in receipt["refs"]:
                ref = SolutionRef.from_dict(value)
                if ref.pool_id != descriptor["pool_id"]:
                    raise ValueError("pool task result receipt has a foreign candidate")
            if receipt["kind"] == "objective_projection":
                ObjectiveProjection.from_dict(receipt["projection"])
                if receipt["slot"] is not None and (type(receipt["slot"]) is not int or receipt["slot"] < 0):
                    raise ValueError("pool task projection receipt has an invalid slot")
            elif receipt["kind"] != "candidate_view" or receipt["projection"] is not None or receipt["slot"] is not None:
                raise ValueError("pool task result receipt has an invalid view interpretation")

    def snapshot_step_state(self):
        return {**super().snapshot_step_state(), "pool_task": copy.deepcopy(self._local),
                "pool_task_rng": self._rng_state()}

    def restore_step_state(self, state):
        self._validate_local(state["pool_task"])
        super().restore_step_state(state)
        self._local = copy.deepcopy(state["pool_task"])
        self._restore_rng(state["pool_task_rng"])


__all__ = ["PoolTaskSpec", "PoolTaskAdapter"]
