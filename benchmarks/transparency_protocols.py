"""候选提案基类协议与真实事件调度的独立透明性对照。

CandidateProposerAdapter 本身是扩展基类。这里的具体 Case 子类只验证其
Unit/repair/disposition/retention 协议，不将基类计为已验证的优化算法。
Async 的 case 模式和加权随机模式执行非空队列、预算裁剪、完成、补充与
切换；不宣称线程并行。随机模式另用独立裸路由流验证运行种子交接。
"""
from __future__ import annotations

from copy import deepcopy
import numpy as np

from blackbase.types import UnknownState
from nsgablack.adapters import CandidateProposerAdapter
from nsgablack.core import BlackBoxProblem


class ProtocolProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="transparency_candidate_protocol", dimension=2,
                         objectives=["min"], bounds=[(-1.0, 1.0)] * 2)

    def evaluate(self, candidate):
        return np.asarray([np.sum(np.asarray(candidate) ** 2)])


class ProtocolCaseProposer(CandidateProposerAdapter):
    """A real Case-local implementation with exact accepted-ref retention."""
    accepts_proposal_replacement = True

    def __init__(self, name="protocol_proposer", start=1.4):
        super().__init__(name=name)
        self.start = float(start)
        self.iteration, self.references, self.last_objectives = 0, (), []

    def setup(self, control):
        self.proposal_units = ()
        self._unit_counter = self.iteration = 0
        self.references, self.last_objectives = (), []

    def propose(self, control, context):
        anchor = self.start - 0.2 * self.iteration
        values = [[anchor, 0.35], [anchor, 0.35], [anchor - 0.8, -0.35]]
        candidates = [UnknownState(value, {"lane": lane, "iteration": self.iteration})
                      for lane, value in enumerate(values)]
        return self.build_candidate_units(candidates, context)

    def update(self, control, candidates, feedback, context):
        self.references = self.pool_refs_from_feedback(feedback)
        self.last_objectives = np.asarray(feedback.objectives).tolist()
        self.iteration += 1

    def get_solution_pool_roots(self, control):
        return self.references

    def get_state(self):
        return {**super().get_state(), "fixture_start": self.start, "iteration": self.iteration,
                "references": [ref.as_dict() for ref in self.references], "objectives": deepcopy(self.last_objectives)}

    def set_state(self, state):
        from nsgablack.core.state.solution_pool import SolutionRef

        if state.get("fixture_start") != self.start:
            raise ValueError("candidate protocol fixture configuration mismatch")
        super().set_state(state)
        self.iteration = int(state["iteration"])
        self.references = tuple(SolutionRef.from_dict(value) for value in state["references"])
        self.last_objectives = deepcopy(state["objectives"])


def make_protocol_pipeline(seed):
    from nsgablack.representation import RepresentationPipeline, ClipRepair
    return RepresentationPipeline(repair=ClipRepair(-1.0, 1.0))


def _unit_projection(adapter):
    result = []
    for unit in adapter.proposal_units:
        candidate = unit.to_candidate()
        metadata = getattr(candidate, "metadata", {})
        result.append({"id": unit.unit_id, "values": np.asarray(getattr(candidate, "values", candidate), dtype=float).tolist(),
                       "lane": metadata.get("lane"), "iteration": metadata.get("iteration")})
    return result


def proposer_state(adapter, solver):
    refs = adapter.references
    values = [] if not refs else solver.read_solutions(refs).numeric_matrix.tolist()
    return {"iteration": adapter.iteration, "unit_counter": adapter._unit_counter,
            "units": _unit_projection(adapter), "retained_values": values,
            "objectives": deepcopy(adapter.last_objectives),
            "distinct_candidate_tokens": len({ref.candidate_token for ref in refs}),
            "retained_count": len(refs)}


def project_proposer(solver):
    return proposer_state(solver.adapter, solver)


class ProposerReference:
    """No Unit, Adapter, Pool or framework codec is used in this bare engine."""
    def __init__(self, name="protocol_proposer", start=1.4):
        self.name, self.start, self.iteration, self.counter = name, float(start), 0, 0
        self.units, self.retained, self.objectives = [], [], []

    def propose(self, count=3):
        anchor = self.start - 0.2 * self.iteration
        rows = [[anchor, 0.35], [anchor, 0.35], [anchor - 0.8, -0.35]]
        self.units = [{"id": f"{self.name}:candidate:{self.counter + i + 1}",
                       "values": np.clip(row, -1.0, 1.0).tolist(), "lane": i, "iteration": self.iteration}
                      for i, row in enumerate(rows[:count])]
        self.counter += 3  # Count construction before event allocation crops rows.
        return [unit["values"] for unit in self.units]

    def update(self, candidates, objectives):
        self.retained, self.objectives = deepcopy(candidates), deepcopy(objectives)
        self.iteration += 1

    def state(self):
        return {"iteration": self.iteration, "unit_counter": self.counter, "units": deepcopy(self.units),
                "retained_values": deepcopy(self.retained), "objectives": deepcopy(self.objectives),
                "distinct_candidate_tokens": len(self.retained), "retained_count": len(self.retained)}


def run_proposer_reference(seed, steps, evaluate):
    del seed
    reference, trace = ProposerReference(), []
    for _ in range(steps):
        rows = reference.propose()
        feedback = [evaluate(np.asarray(row)) for row in rows]
        f, v = [value[0].tolist() for value in feedback], [float(value[1]) for value in feedback]
        reference.update(rows, f)
        trace.append({"candidates": rows, "objectives": f, "violations": v, "state": reference.state()})
    return {"state": reference.state(), "trace": trace}


def _early(context):
    return int(context["generation"]) < 3


def _late(context):
    return int(context["generation"]) >= 3


def make_event_adapter(seed):
    from nsgablack.adapters import AsyncEventDrivenAdapter, AsyncEventDrivenConfig, EventCaseSpec

    return AsyncEventDrivenAdapter([
        EventCaseSpec(ProtocolCaseProposer("early_proposer", 1.4), "early", when=_early, priority=2),
        EventCaseSpec(ProtocolCaseProposer("late_proposer", -1.2), "late", when=_late, priority=1),
    ], config=AsyncEventDrivenConfig(total_batch_size=2, target_queue_size=3,
        max_archive_size=4, refill_events_per_completion=1))


def make_weighted_event_adapter(seed):
    from nsgablack.adapters import AsyncEventDrivenAdapter, AsyncEventDrivenConfig, EventStrategySpec

    return AsyncEventDrivenAdapter([
        EventStrategySpec(ProtocolCaseProposer("early_proposer", 1.4), "early", weight=1.0),
        EventStrategySpec(ProtocolCaseProposer("late_proposer", -1.2), "late", weight=3.0),
    ], config=AsyncEventDrivenConfig(total_batch_size=4, target_queue_size=7,
        bootstrap_events_per_strategy=1, max_archive_size=6, refill_events_per_completion=1))


def _event_history(events):
    allowed = {"kind", "step", "event_id", "strategy", "source", "budget", "accepted",
               "case", "score", "violation", "active_case"}
    return [{key: value for key, value in event.items() if key in allowed} for event in events]


def _event_archive(archive):
    return [{key: np.asarray(value).tolist() if isinstance(value, np.ndarray) else value
             for key, value in record.items() if key != "solution_ref"} for record in archive]


def project_events(solver):
    adapter = solver.adapter
    return {"children": {spec.name: proposer_state(spec.adapter, solver) for spec in adapter.strategies},
            "step": adapter._step, "event_id": adapter._event_id, "queue": deepcopy(adapter._queue),
            "inflight_count": len(adapter._inflight), "archive": _event_archive(adapter.archive),
            "history": _event_history(adapter.event_history), "stats": deepcopy(adapter._stats),
            "active_case": adapter._active_case_name, "active_since": adapter._active_case_since,
            "last_exit": deepcopy(adapter._case_last_exit)}


class EventReference:
    def __init__(self, evaluate):
        self.evaluate = evaluate
        self.children = {"early": ProposerReference("early_proposer", 1.4),
                         "late": ProposerReference("late_proposer", -1.2)}
        self.steps, self.event_id = 0, 0
        self.queue, self.archive, self.history = [], [], []
        self.stats = {name: {"proposed": 0.0, "completed": 0.0, "best_score": float("inf")}
                      for name in self.children}
        self.active_case, self.active_since, self.last_exit = None, None, {}

    def enqueue(self, name, source):
        self.event_id += 1
        self.queue.append({"event_id": self.event_id, "type": "propose", "strategy": name,
                           "case": name, "budget": 1, "source": source, "created_step": self.steps})
        self.history.append({"kind": "enqueue", "step": self.steps, "event_id": self.event_id,
                             "strategy": name, "source": source})

    def step(self):
        chosen = "early" if self.steps < 3 else "late"
        if self.active_case != chosen:
            if self.active_case is not None:
                self.last_exit[self.active_case] = self.steps
            self.active_case, self.active_since = chosen, self.steps
        self.history.append({"kind": "decision", "step": self.steps, "active_case": chosen})
        if {event["strategy"] for event in self.queue} != {chosen}:
            self.queue = []
        while len(self.queue) < 3:
            self.enqueue(chosen, "topup")
        events, self.queue = self.queue[:2], self.queue[2:]
        rows = self.children[chosen].propose(count=2)
        for event in events:
            self.stats[chosen]["proposed"] += 1.0
            self.history.append({"kind": "dispatch", "step": self.steps,
                "event_id": event["event_id"], "strategy": chosen, "budget": 1, "accepted": 1})
        feedback = [self.evaluate(np.asarray(row)) for row in rows]
        f, v = [value[0].tolist() for value in feedback], [float(value[1]) for value in feedback]
        for event, x, objective, violation in zip(events, rows, f, v):
            score = float(np.sum(objective) + 1e6 * violation)
            record = {"event_id": event["event_id"], "strategy": chosen, "case": chosen,
                      "step": self.steps, "score": score, "violation": violation}
            self.archive.append({**record, "objective": objective, "x": x})
            self.archive.sort(key=lambda item: item["score"])
            self.archive = self.archive[:4]
            self.stats[chosen]["completed"] += 1.0
            self.stats[chosen]["best_score"] = min(self.stats[chosen]["best_score"], score)
            self.history.append({"kind": "completion", **record})
            self.enqueue(chosen, "completion")
        self.children[chosen].update(rows, f)
        self.steps += 1
        return {"candidates": rows, "objectives": f, "violations": v, "state": self.state()}

    def state(self):
        return {"children": {name: child.state() for name, child in self.children.items()},
                "step": self.steps, "event_id": self.event_id, "queue": deepcopy(self.queue),
                "inflight_count": 0, "archive": deepcopy(self.archive), "history": deepcopy(self.history),
                "stats": deepcopy(self.stats), "active_case": self.active_case,
                "active_since": self.active_since, "last_exit": dict(self.last_exit)}


class WeightedEventReference(EventReference):
    """Two eligible strategies actually compete for queue slots at weights1:3."""
    def __init__(self, seed, evaluate):
        super().__init__(evaluate)
        root = np.random.default_rng(int(seed))
        self.rng = np.random.default_rng(int(root.integers(0, 2**63 - 1)))
        for name in self.children:
            self.enqueue(name, "bootstrap")

    def topup(self):
        names = tuple(self.children)
        while len(self.queue) < 7:
            selected = int(self.rng.choice(2, p=np.asarray([0.25, 0.75])))
            self.enqueue(names[selected], "topup")

    def step(self):
        self.topup()
        events, self.queue = self.queue[:4], self.queue[4:]
        groups = {}
        for event in events:
            groups.setdefault(event["strategy"], []).append(event)
        dispatched = []
        for name, allocated in groups.items():
            rows = self.children[name].propose(count=min(3, len(allocated)))
            for event, row in zip(allocated, rows):
                dispatched.append((name, event, row))
                self.stats[name]["proposed"] += 1.0
            for index, event in enumerate(allocated):
                self.history.append({"kind": "dispatch", "step": self.steps,
                    "event_id": event["event_id"], "strategy": name, "budget": 1,
                    "accepted": int(index < len(rows))})
        feedback = [self.evaluate(np.asarray(row)) for _, _, row in dispatched]
        f, v = [item[0].tolist() for item in feedback], [float(item[1]) for item in feedback]
        by_name = {}
        for (name, event, row), objective, violation in zip(dispatched, f, v):
            score = float(np.sum(objective) + 1e6 * violation)
            record = {"event_id": event["event_id"], "strategy": name, "case": name,
                      "step": self.steps, "score": score, "violation": violation}
            self.archive.append({**record, "objective": objective, "x": row})
            self.archive.sort(key=lambda item: item["score"])
            self.archive = self.archive[:6]
            self.stats[name]["completed"] += 1.0
            self.stats[name]["best_score"] = min(self.stats[name]["best_score"], score)
            self.history.append({"kind": "completion", **record})
            self.enqueue(name, "completion")
            selected = by_name.setdefault(name, ([], []))
            selected[0].append(row)
            selected[1].append(objective)
        for name, (rows, objectives) in by_name.items():
            self.children[name].update(rows, objectives)
        self.steps += 1
        self.topup()
        return {"candidates": [row for _, _, row in dispatched], "objectives": f,
                "violations": v, "state": self.state()}


def run_event_reference(seed, steps, evaluate):
    del seed
    reference = EventReference(evaluate)
    trace = [reference.step() for _ in range(steps)]
    return {"state": reference.state(), "trace": trace}


def run_weighted_event_reference(seed, steps, evaluate):
    reference = WeightedEventReference(seed, evaluate)
    trace = [reference.step() for _ in range(steps)]
    return {"state": reference.state(), "trace": trace}


def specs():
    from benchmarks.transparency_core import PairSpec
    return [
        PairSpec(name="candidate_proposer_contract", make_problem=ProtocolProblem,
            make_adapter=lambda seed: ProtocolCaseProposer(), make_pipeline=make_protocol_pipeline,
            reference=run_proposer_reference, project=project_proposer, steps=6,
            metadata={"family": "protocol", "base_contract": "CandidateProposerAdapter",
                "concrete_fixture": "ProtocolCaseProposer", "counts_as_concrete_algorithm": False,
                "scope": "three semantic candidates; duplicate values retain distinct tokens; clip repair rebuilds stable Unit IDs; exact references and checkpoint",
                "reference": "independent numeric sequence and counters; no Unit/Adapter/Pool or state codec"}),
        PairSpec(name="async_event_driven_cases", make_problem=ProtocolProblem,
            make_adapter=make_event_adapter, make_pipeline=make_protocol_pipeline,
            reference=run_event_reference, project=project_events, steps=6,
            metadata={"family": "protocol", "adapters": ["AsyncEventDrivenAdapter"],
                "scope": "priority cases switch at generation3; queue3 dispatch2; proposal3 budget2; refill, completion, bounded archive, exact child feedback",
                "reference": "independent Python queue/case/counter state machine",
                "execution": "synchronous Solver event scheduling, not threaded concurrency",
                "not_covered": ["cooldown/min-active policy", "queue overflow", "concurrent evaluators"]}),
        PairSpec(name="async_event_driven_weighted", make_problem=ProtocolProblem,
            make_adapter=make_weighted_event_adapter, make_pipeline=make_protocol_pipeline,
            reference=run_weighted_event_reference, project=project_events, steps=6,
            metadata={"family": "protocol", "adapters": ["AsyncEventDrivenAdapter"],
                "scope": "two enabled strategies weight1:3; queue7 dispatch4; grouped budget allocation and exact feedback; completion refill and bounded archive6",
                "reference": "independent NumPy weighted sampling and Python queue/counter state machine",
                "rng_pairing": "first Solver child stream; independent root draw default_rng(seed).integers(0,2**63-1)",
                "execution": "synchronous Solver event scheduling, not threaded concurrency",
                "regression": "Async setup must bind its routing RNG through create_local_rng before fresh queue work; checkpoint restore replaces that state later",
                "not_covered": ["queue overflow", "weighted adaptive policies", "concurrent evaluators"]}),
    ]
