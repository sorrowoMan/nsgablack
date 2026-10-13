"""Candidate handoff for existing role scheduling; no independent run loop."""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Callable

from .role_adapters import RoleAdapter
from .strategy_task import StrategyTask
from nsgablack.context_keys import KEY_PHASE, KEY_SEEDS, KEY_TASK, KEY_SOLUTION_INPUT_REF, KEY_SOLUTION_INPUT_MODE
from nsgablack.core.state.solution_pool import SolutionRef, SolutionStamp


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

    ``select(control, context)`` returns references, or ``select`` names an
    existing subpool. Refine runs one seed per independent trajectory; compete
    presents the selected batch to a population's ordinary admission/selection.
    ``request_key`` defaults to phase; use a stable explicit key for repeated
    triggers in the same phase. A request never silently replaces active work.
    """
    select: Callable | str
    mode: str = "refine"
    steps: int = 5
    output: str | None = None
    request_key: Callable | None = None
    phases: tuple[str, ...] = ()

    def __post_init__(self):
        if not (callable(self.select) or isinstance(self.select, str) and self.select.strip()):
            raise TypeError("pool task select must be a selector or subpool name")
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
        _callable_id(self.select)
        if self.request_key is not None:
            _callable_id(self.request_key)

    def identity(self):
        return dict(select=_callable_id(self.select), mode=self.mode, steps=self.steps,
                    output=self.output, phases=self.phases,
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
        if type(workers) is not int or workers < 1 or type(worker) is not int or not 0 <= worker < workers:
            raise ValueError("pool task worker must be an index within positive workers")
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("pool task namespace must be nonempty")
        self.validate_pool_task()

    def validate_pool_task(self):
        if not isinstance(self.spec, PoolTaskSpec):
            raise TypeError("role pool_task must be PoolTaskSpec")
        mode = "initialize" if self.spec.mode == "refine" else self.spec.mode
        if mode not in self.inner.pool_input_modes:
            raise ValueError(f"{self.inner.name} does not support pool {mode}")
        if self.spec.mode == "refine" and not self.inner.supports_pool_restart:
            raise ValueError(f"{self.inner.name} does not support explicit search restart")

    def setup(self, control):
        super().setup(control)
        control.solution_pool.checkpoint_required = True
        self._local = {}

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
        digest = hashlib.sha256(request.encode()).hexdigest()[:24]
        base = self._name(f"task:{self.role}/{digest}", context)
        # One selection shared by all role instances, partitioned by position.
        # The empty marker records selection completion without retaining values.
        if not pool.has_subpool(base):
            if isinstance(self.spec.select, str):
                source = self._name(self.spec.select, context)
                refs = pool.subpool_refs(source) if pool.has_subpool(source) else ()
            else:
                refs = tuple(self.spec.select(control, context))
            if not refs:
                return
            pool.create_subpool(base)
            for i in range(self.workers):
                pool.create_subpool(f"{base}/{i}", refs[i::self.workers])
        view = f"{base}/{self.worker}"
        refs = pool.subpool_refs(view)
        self._local = dict(request=request, status="running" if refs else "done",
                           view=view, next=0, count=len(refs), steps=0,
                           input=None, results=[], output=None)
        if self.spec.output is not None:
            output = self._name(self.spec.output, context)
            if not pool.has_subpool(output):
                pool.create_subpool(output)
            self._local["output"] = output
        if not refs:
            pool.drop_subpool(view)

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
        super().update(control, candidates, feedback, self._context(context))
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
                "pool_task_spec": self._identity()}

    def _identity(self):
        return {**self.spec.identity(), "worker": self.worker, "workers": self.workers, "namespace": self.namespace}

    def set_state(self, state):
        if state.get("pool_task_spec") != self._identity():
            raise ValueError("pool task checkpoint configuration mismatch")
        self._validate_local(state["pool_task"])
        super().set_state(state)
        self._local = copy.deepcopy(state["pool_task"])

    @staticmethod
    def _validate_local(state):
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

    def snapshot_step_state(self):
        return {**super().snapshot_step_state(), "pool_task": copy.deepcopy(self._local)}

    def restore_step_state(self, state):
        self._validate_local(state["pool_task"])
        super().restore_step_state(state)
        self._local = copy.deepcopy(state["pool_task"])


__all__ = ["PoolTaskSpec", "PoolTaskAdapter"]
