"""Observe committed pool phases without creating Units or controlling search."""
import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text


def data_copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


class PoolTracePlugin(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Bounded JSON observations of committed phases."
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads owned algorithm state and exact pool references; never constructs Units."

    def __init__(self, *, output_dir, max_records):
        super().__init__(name="pool_recovery_trace")
        self.output_dir = Path(output_dir)
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self.max_records = max_records
        self.run_id, self.initial, self.records = None, None, []
        self._attempt_phase = None

    def observe(self):
        solver, root = self.solver, self.solver.adapter
        pool = solver.solution_pool
        populations = {}
        for spec in root.searches:
            adapter = spec.adapter
            structure = adapter.algorithm_unit
            members = None if structure is None else structure.population
            refs = () if members is None else adapter.get_population_solution_refs(solver)
            populations[adapter.name] = {
                "type": type(adapter).__name__, "unit_exists": structure is not None,
                "members": 0 if members is None else len(members),
                "refs": [ref.as_dict() for ref in refs],
                "provenance": list(pool.read_provenance(refs)) if refs else [],
            }
        incumbent = solver.get_incumbent()
        return {
            "steps": int(solver.run_progress_steps), "evaluations": int(solver.evaluation_count),
            "phase_after": root.phase, "prepared_count": root.prepared_count,
            "stagnation": root.stagnation, "best_metric": root.best_metric,
            "recovery_count": root.recovery_count,
            "input_remaining": {name: pool.input_remaining(key) for name, key in root.input_ids.items()},
            "pool_records": pool.record_count, "pool_sequence": pool.timestamp.sequence,
            "sa_unit_exists": root.producer.algorithm_unit is not None,
            "sa_temperature": float(root.producer.temperature),
            "sa_current_score": root.producer.current_score,
            "populations": populations,
            "best_selection_score": None if incumbent is None else float(incumbent.score),
        }

    def on_solver_init(self, solver):
        run_id = solver.run_session.run_id
        if self.run_id != run_id:
            self.records, self.initial = [], None
        self.run_id = run_id
        if self.initial is None:
            self.initial = self.observe()

    def on_step_attempt_start(self, attempt, logical_step):
        self._attempt_phase = self.solver.adapter.phase

    def on_generation_committed(self, generation, outcome):
        if not outcome.get("committed"):
            raise ValueError("trace requires a committed step")
        if len(self.records) >= self.max_records:
            raise ValueError("the teaching trace exhausted its configured committed-step capacity")
        self.records.append({"generation": int(generation), "executed_phase": self._attempt_phase,
                             **self.observe()})

    def on_solver_finalized(self, result):
        payload = {**self.get_state(), "final": self.observe()}
        atomic_write_text(self.output_dir / "trace.json",
                          json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
        fields = ("steps", "executed_phase", "phase_after", "evaluations", "prepared_count",
                  "stagnation", "recovery_count", "sa_temperature", "best_selection_score")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({name: row[name] for name in fields} for row in self.records)
        atomic_write_text(self.output_dir / "trace.csv", stream.getvalue())

    def get_state(self):
        return data_copy({"schema": "assembled_pool_recovery.trace/v1", "run_id": self.run_id,
                          "max_records": self.max_records,
                          "initial": self.initial, "records": self.records})

    def set_state(self, state):
        if not isinstance(state, Mapping) or state.get("schema") != "assembled_pool_recovery.trace/v1":
            raise ValueError("unsupported trace state")
        saved = data_copy(dict(state))
        if saved.get("max_records") != self.max_records:
            raise ValueError("trace capacity changed since checkpoint")
        if not isinstance(saved.get("records"), list) or len(saved["records"]) > self.max_records:
            raise ValueError("invalid trace records")
        self.run_id, self.initial, self.records = saved["run_id"], saved["initial"], saved["records"]
        self._attempt_phase = None
