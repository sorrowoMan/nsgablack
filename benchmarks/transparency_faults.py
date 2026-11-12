"""透明性 Case 的提交后故障验证，独立于性能计时。

使用真实 Solver.run、Project L0 SQLite grant、文件 Snapshot 和 SQLite
证据日志。故障发生在下一次真实 update 之后；on_error 在 teardown 之前读取
回滚状态。恢复只完成已发生评估的证据对账，不要求失败后继续搜索重现无故障
轨迹（BO 等算法可以合法学习已发生的失败尝试观测）。没有独立 CLI。
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import os
import secrets
from uuid import uuid4

from benchmarks.transparency_core import ProblemMeter, compare, json_value


def _pool_state(solver):
    state = deepcopy(solver.solution_pool.get_state())
    # 单调时间高水位和物理垃圾不是可回滚的候选成员事实。
    state.pop("sequence", None)
    state["retention"].pop("garbage", None)
    return json_value({"index": state, "manifest": solver.solution_pool.publication_ref()})


def _snapshot(spec, solver, meter):
    authority = solver.get_population_authority_identity()
    project = json_value(spec.project(solver))
    return {"project": project,
            "authority": None if authority is None else authority.as_dict(),
            "pool": _pool_state(solver),
            "evaluations": int(solver.evaluation_count),
            "problem_calls": len(meter.records),
            "steps": int(solver.run_progress_steps),
            "budget": solver.shared_evaluation_budget_status()}


def _runtime(directory, name):
    from blackbase.project.runtime import ProjectL0Runtime, ProjectRuntimeConfig
    from blackbase.resources import ResourceOffer, ResourcePolicy, ResourceRequest
    return ProjectL0Runtime(ProjectRuntimeConfig(
        offer=ResourceOffer(threads=1, gpus=0, backend="local"),
        policy=ResourcePolicy(max_workers=1, max_threads=1, max_gpus=0),
        default_request=ResourceRequest(workers=1, threads=1),
        namespace="transparency_faults." + name,
        lease_backend="sqlite", lease_path="l0.sqlite",
        lease_ttl_seconds=600.0, lease_heartbeat_seconds=60.0,
        budgets={"evaluations": 10000}), project_root=directory)


def _build(spec, seed, directory, context, checkpoint_config):
    from nsgablack.core import ComposableSolver
    from nsgablack.plugins import CheckpointResumePlugin
    problem = spec.make_problem()
    meter = ProblemMeter(problem)
    solver = ComposableSolver(problem, adapter=spec.make_adapter(int(seed)),
        representation_pipeline=None if spec.make_pipeline is None else spec.make_pipeline(int(seed)),
        resource_context=context, plugin_strict=True, snapshot_strict=True,
        snapshot_store_backend="file", snapshot_store_dir=str(directory / "snapshots"),
        snapshot_store_key_prefix="transparency_faults")
    solver.set_random_seed(int(seed))
    solver.enable_progress_log = False
    if spec.population_size is not None:
        solver.pop_size = int(spec.population_size)
    checkpoint = CheckpointResumePlugin(config=checkpoint_config)
    solver.add_plugin(checkpoint)
    return solver, meter, checkpoint


def _run_mode(spec, seed, work_dir, mode):
    from blackbase.context import SnapshotIdentity, create_snapshot_store
    from blackbase.evaluation import create_evaluation_evidence_journal
    from blackbase.resources import CancellationRequested, SQLiteBudgetAuthority
    from nsgablack.plugins import CheckpointResumeConfig
    from nsgablack.plugins.base import Plugin

    directory = Path(work_dir).resolve() / spec.name / mode / uuid4().hex
    directory.mkdir(parents=True, exist_ok=True)
    runtime = _runtime(directory, spec.name)
    lease = runtime.acquire_case(spec.name)
    context = runtime.resource_context(lease, case_name=spec.name)
    key_name = "NSGABLACK_FAULT_CHECK_" + uuid4().hex.upper()
    os.environ[key_name] = secrets.token_hex(32)
    checkpoint_config = CheckpointResumeConfig(checkpoint_dir=str(directory / "checkpoints"),
        save_every=0, save_on_finish=False, strict=True, hmac_env_var=key_name,
        restore_plugin_state=False, trusted_roots=(str(directory),))
    expected_error = RuntimeError if mode == "runtime_error" else CancellationRequested
    caught = None

    class Observer(Plugin):
        def __init__(self):
            super().__init__("transparency_fault_observer")
            self.before = self.after = self.path = self.record = None
            self.armed = False
            self.observation_errors = []

        def on_generation_committed(self, generation, outcome):
            if self.before is None:
                self.before = _snapshot(spec, self.solver, meter)
                self.armed = True

        def on_error(self, error, context=None):
            if self.armed:
                try:
                    self.after = _snapshot(spec, self.solver, meter)
                except Exception as failure:
                    self.observation_errors.append({"phase": "post_rollback_observation",
                        "error_type": type(failure).__name__, "error": str(failure)})
                event = self.solver.get_last_evaluation_event()
                self.record = (None if event is None else
                    self.solver.evaluation_evidence_journal.get(event.event_id))
                try:
                    self.path = writer.save_checkpoint(reason="transparency_failed_attempt")
                except Exception as failure:
                    self.observation_errors.append({"phase": "post_failure_checkpoint",
                        "error_type": type(failure).__name__, "error": str(failure)})

    try:
        solver, meter, writer = _build(spec, seed, directory, context, checkpoint_config)
        observer = Observer()
        solver.add_plugin(observer)
        original_update = solver.adapter.update

        def fail_after_update(control, candidates, feedback, context):
            original_update(control, candidates, feedback, context)
            if observer.armed:
                raise expected_error("transparency injected after real update")

        solver.adapter.update = fail_after_update
        caught = None
        try:
            solver.run(max_steps=2)
        except expected_error as error:
            if "transparency injected after real update" not in str(error):
                raise
            caught = error
        if caught is None or observer.before is None or observer.after is None:
            raise AssertionError("fault was not observed after one real committed step")
        before, after = observer.before, observer.after
        issues = {"project_rollback": compare(before["project"], after["project"]),
                  "authority_rollback": compare(before["authority"], after["authority"]),
                  "pool_rollback": compare(before["pool"], after["pool"]),
                  "logical_steps_unchanged": compare(before["steps"], after["steps"])}
        rollback_errors = json_value(getattr(caught, "step_rollback_errors", ()))
        issues["adapter_rollback_completed"] = None if not rollback_errors else str(rollback_errors)
        consumed = after["evaluations"] - before["evaluations"]
        if consumed <= 0:
            issues["failure_evaluated_candidates"] = "failed update had no evaluated candidates"
        else:
            issues["failure_evaluated_candidates"] = None
        issues["problem_calls_retained"] = compare(consumed, after["problem_calls"] - before["problem_calls"])
        issues["sqlite_budget_retained"] = compare(consumed,
            after["budget"]["committed"] - before["budget"]["committed"])
        issues["no_budget_reservation_leak"] = compare(0, after["budget"]["reserved"])
        authority = runtime.budget_authority
        reopened_budget = SQLiteBudgetAuthority(authority.path, namespace=authority.namespace, scope=authority.scope)
        durable_budget = reopened_budget.status("evaluations")
        issues["budget_survives_reopen"] = compare(after["budget"]["committed"], durable_budget.committed)
        record = observer.record
        if record is None:
            raise AssertionError("failed attempt has no durable evaluation record")
        reopened_journal = create_evaluation_evidence_journal(backend="file",
            base_dir=directory / "snapshots", key_prefix="transparency_faults:evaluation-evidence")
        durable_record = reopened_journal.get(record.event_id)
        issues["evidence_survives_reopen"] = compare(record.as_dict(),
            None if durable_record is None else durable_record.as_dict())
        issues["failed_evidence_finalized"] = (None if record.status == "failed" and record.phase == "finalized"
                                                else f"unexpected {record.status}/{record.phase}")
        # 新建文件后端读取精确身份，确认不是仅保留进程内 Event 对象。
        disk = create_snapshot_store(backend="file", base_dir=directory / "snapshots",
                                     key_prefix="transparency_faults")
        event_snapshot = disk.read_verified(SnapshotIdentity.from_dict(dict(record.event_ref)))
        issues["event_snapshot_durable"] = None if event_snapshot is not None else "event is unreadable"
        if observer.path is None:
            raise AssertionError("post-failure checkpoint was not created")
        # 目标1已经完成；恢复只做prepare/apply/reconcile/finalize，不派发搜索。
        restored, restored_meter, reader = _build(spec, seed, directory, context, checkpoint_config)
        if not reader.resume(str(observer.path)):
            raise AssertionError("post-failure checkpoint restore was refused")
        result = restored.run(max_steps=1)
        restored.reconcile_evaluation_evidence()
        restored.reconcile_evaluation_evidence()
        issues["restore_no_problem_replay"] = compare(0, len(restored_meter.records))
        issues["restore_no_new_commits"] = compare(0, result.get("steps_executed"))
        issues["restore_keeps_consumed_evaluations"] = compare(after["evaluations"], int(restored.evaluation_count))
        issues["restore_no_budget_replay"] = compare(durable_budget.committed,
            reopened_budget.status("evaluations").committed)
        restored_record = restored.evaluation_evidence_journal.get(record.event_id)
        issues["restore_keeps_failed_evidence"] = (None if restored_record is not None
            and restored_record.status == "failed" else "failed evidence missing after checkpoint restore")
        failures = {key: value for key, value in issues.items() if value is not None}
        return {"status": "failed" if failures else "passed", "mode": mode,
            "checks": {key: value is None for key, value in issues.items()}, "mismatches": failures,
            "evidence": {"committed_steps_before_fault": before["steps"],
                "evaluations_before_fault": before["evaluations"], "failed_attempt_evaluations": consumed,
                "evaluations_after_fault": after["evaluations"],
                "sqlite_budget_committed": durable_budget.committed, "sqlite_budget_reserved": durable_budget.reserved,
                "event_id": record.event_id, "event_status": record.status, "event_phase": record.phase,
                "authority_unchanged": issues["authority_rollback"] is None,
                "checkpoint": str(observer.path), "restored_problem_calls": len(restored_meter.records),
                "restored_new_commits": result.get("steps_executed"), "run_directory": str(directory)}}
    except Exception as error:
        return {"status": "failed", "mode": mode, "error_type": type(error).__name__,
                "error": str(error), "run_directory": str(directory),
                "rollback_errors": json_value(getattr(caught, "step_rollback_errors", ())),
                "observation_errors": [] if "observer" not in locals() else observer.observation_errors}
    finally:
        os.environ.pop(key_name, None)
        runtime.release(lease)
        runtime.close()


def run_fault_checks(spec, seed=11, work_dir=None):
    """在报告中独立列出故障语义；不计入裸参考/完整框架的性能数字。"""
    if work_dir is None:
        raise ValueError("fault checks require an explicit local work_dir")
    modes = [_run_mode(spec, seed, work_dir, mode) for mode in ("runtime_error", "cancellation")]
    return {"status": "passed" if all(row["status"] == "passed" for row in modes) else "failed",
        "name": spec.name, "seed": int(seed), "modes": modes,
        "scope": "unit resource fixture: real local SQLite Project L0 grant and durable evaluation evidence",
        "recovery_scope": "restore and reconcile failed evidence without dispatch; no assertion of no-fault continuation equivalence",
        "cost_scope": "excluded from paired algorithm benchmark timing",
        "not_covered": ["process kill between SQLite writes", "network/remote backend outage",
                        "external cancellation signal delivery latency"],
        "checkpoint_key": "ephemeral in-process HMAC key; fixture checkpoints are not reusable after this check"}


__all__ = ["run_fault_checks"]
