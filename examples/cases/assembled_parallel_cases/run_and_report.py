"""正式 Project 执行 + 只读结果对账；不实现第二套求解/并发循环。"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import bootstrap

bootstrap()
from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text
from cases.de_bowl.config import MAX_STEPS as DE_STEPS, POPULATION_SIZE, BATCH_SIZE
from cases.de_bowl.problem import build_problem as de_problem
from cases.sa_valley.config import MAX_STEPS as SA_STEPS
from cases.sa_valley.problem import build_problem as sa_problem

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, payload):
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))


def utc_timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="milliseconds")


def summarize(project, wall_seconds):
    if project["exit_code"] or project["status"] != "ok":
        raise RuntimeError("Project failed; inspect results/project_result.json")
    cases = {case["request"]["case_name"]: case for case in project["cases"]}
    if set(cases) != {"de_bowl", "sa_valley"}:
        raise RuntimeError("Project must contain exactly the two assembled Cases")
    specifications = {"de_bowl": (de_problem, DE_STEPS, POPULATION_SIZE + (DE_STEPS - 1) * BATCH_SIZE),
                      "sa_valley": (sa_problem, SA_STEPS, SA_STEPS)}
    summaries = []
    for name, (problem_builder, expected_steps, expected_evaluations) in specifications.items():
        case = cases[name]
        if not case["ok"] or case["identity"]["project_run_id"] != project["run_id"]:
            raise RuntimeError(f"{name} did not successfully complete this Project run")
        output, resources = case["output"], case["resource_usage"]
        grant, context = resources["authorized_grant"], resources["effective_context"]
        if not resources["binding"]["current"] or grant["threads"] != 1 or grant["workers"] != 1:
            raise RuntimeError(f"{name} did not bind its one-thread/one-worker Project grant")
        if output["report"]["steps"] != expected_steps or output["report"]["evaluation_count"] != expected_evaluations:
            raise RuntimeError(f"{name} progress/evaluation count differs from its declared budget")
        candidate = output["best_solution"]["values"]
        # 报告阶段独立解析核对，不冒充持久 raw evidence，不加入求解求值计数。
        problem = problem_builder()
        raw_check = float(problem.evaluate(candidate))
        if not math.isfinite(raw_check) or not math.isclose(raw_check, output["best_objectives"][0], rel_tol=1e-12, abs_tol=1e-14):
            raise RuntimeError(f"{name} final objective disagrees with the analytical check")
        if len(candidate) != 2 or not all(-4.0 <= value <= 4.0 for value in candidate):
            raise RuntimeError(f"{name} final candidate violates the declared bounds")
        if not case["finished_at"] > case["started_at"] > 0:
            raise RuntimeError(f"{name} has no valid formal lifecycle timestamps")
        summaries.append({
            "case": name, "case_run_id": case["identity"]["case_run_id"], "status": case["status"],
            "adapter": case["metadata"]["runtime_state"]["adapter"],
            "best_candidate": candidate, "best_candidate_token": output["best_candidate_token"],
            "best_objectives": output["best_objectives"], "raw_objective_recomputed": raw_check,
            "known_optimum": list(problem.optimum), "known_optimal_objective": 0.0,
            "distance_to_known_optimum": math.dist(candidate, problem.optimum),
            "logical_steps": output["report"]["steps"], "evaluations": output["report"]["evaluation_count"],
            "started_at": case["started_at"], "finished_at": case["finished_at"],
            "started_utc": utc_timestamp(case["started_at"]), "finished_utc": utc_timestamp(case["finished_at"]),
            "elapsed_seconds": case["elapsed_seconds"], "solver_elapsed_seconds": output["report"]["elapsed_sec"],
            "authorized_grant": grant, "namespace": context["namespace"],
            "lease_id": context["lease"]["lease_id"], "resource_binding_current": resources["binding"]["current"],
        })
    if len({row["namespace"] for row in summaries}) != 2 or len({row["lease_id"] for row in summaries}) != 2:
        raise RuntimeError("Cases must have distinct Project namespaces and resource leases")
    overlap_start = max(row["started_at"] for row in summaries)
    overlap_end = min(row["finished_at"] for row in summaries)
    overlap = max(0.0, overlap_end - overlap_start)
    if overlap <= 0:
        raise RuntimeError("No observed lifecycle overlap; do not claim this run demonstrated concurrent Cases")
    return {
        "project_run_id": project["run_id"], "status": project["status"], "wall_seconds": wall_seconds,
        "stage_policy": "parallel", "stage_max_workers": 2, "cases": summaries,
        "lifecycle_overlap_seconds": overlap, "overlap_started_utc": utc_timestamp(overlap_start),
        "overlap_finished_utc": utc_timestamp(overlap_end),
        "overlap_note": "Formal Case lifecycle intervals overlap; this is not a CPU utilization or speedup benchmark.",
        "checks": ["两个独立 Case 均通过正式 Project 执行", "两段 Case 生命周期发生真实重叠",
                   "每个 Case 的 threads=1、workers=1 且 binding.current=true", "Case 运行身份、资源 lease 与 namespace 彼此独立",
                   "求值次数与各算法声明预算一致", "最终候选、原始函数解析核对和问题边界一致"],
    }


def write_report(summary):
    lines = ["# 两个独立 Case 的实际并发结果", "",
             f"Project run：`{summary['project_run_id']}`。", "",
             f"- Stage：`parallel`，`max_workers=2`。",
             f"- 实际观察到的 Case 生命周期重叠：`{summary['lifecycle_overlap_seconds']:.6f}` 秒。",
             f"- 重叠区间：`{summary['overlap_started_utc']}` → `{summary['overlap_finished_utc']}`。",
             f"- 整体入口耗时：`{summary['wall_seconds']:.6f}` 秒。", "",
             "重叠使用正式 CaseRunResult 的 started_at/finished_at 计算，包含构建、运行、清理和发布；",
             "它证明两个 Case 生命周期并发，不证明某一瞬间两个目标函数都占用 CPU，也不是加速比测试。", ""]
    for case in summary["cases"]:
        lines += [f"## {case['case']} · {case['adapter']}", "",
                  f"- 最终候选：`{case['best_candidate']}`。",
                  f"- 目标：`{case['best_objectives'][0]:.12g}`；已知最优值 `0`，最优点 `{case['known_optimum']}`。",
                  f"- `{case['logical_steps']}` 次逻辑提交、`{case['evaluations']}` 次求值。",
                  f"- 开始：`{case['started_utc']}`；结束：`{case['finished_utc']}`。",
                  f"- Case 生命周期耗时 `{case['elapsed_seconds']:.6f}` 秒；Solver 报告耗时 `{case['solver_elapsed_seconds']:.6f}` 秒。",
                  f"- L0 授权：threads=`{case['authorized_grant']['threads']}`、workers=`{case['authorized_grant']['workers']}`。",
                  f"- namespace：`{case['namespace']}`。", f"- lease：`{case['lease_id']}`。", ""]
    lines += ["## 对账", ""] + [f"- {item}。" for item in summary["checks"]]
    lines += ["", "解析重算仅用于报告核对；没有 Bias，所以本例选择目标与原始目标一致。",
              "DE 与 SA 使用不同问题、不同 Solver、不同解池，没有交换候选，也没有共享 Unit。",
              "该结果不能用于比较 DE 与 SA 优劣：问题、步数、批量数都不同。", "",
              "完整正式返回值：[project_result.json](results/project_result.json)；简明汇总：[summary.json](results/summary.json)。", ""]
    atomic_write_text(ROOT / "RESULTS.md", "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true", help="只重新核对已保存结果，不重新求解")
    args = parser.parse_args()
    if args.report_only:
        project = json.loads((RESULTS / "project_result.json").read_text(encoding="utf-8"))
        timing = json.loads((RESULTS / "timing.json").read_text(encoding="utf-8"))
        if timing["project_run_id"] != project["run_id"]:
            raise RuntimeError("saved wall timing belongs to a different Project run")
        wall_seconds = timing["wall_seconds"]
    else:
        started = time.perf_counter()
        project = execute_project(ROOT).as_dict()
        wall_seconds = time.perf_counter() - started
        write_json(RESULTS / "project_result.json", project)
        write_json(RESULTS / "timing.json", {"project_run_id": project["run_id"], "wall_seconds": wall_seconds})
    summary = summarize(project, wall_seconds)
    write_json(RESULTS / "summary.json", summary)
    for case in summary["cases"]:
        write_json(RESULTS / "cases" / (case["case"] + ".json"), case)
    write_report(summary)
    print(json.dumps({"project_run_id": summary["project_run_id"], "overlap_seconds": summary["lifecycle_overlap_seconds"],
                      "cases": [{key: row[key] for key in ("case", "logical_steps", "evaluations", "best_candidate", "best_objectives", "namespace")}
                                for row in summary["cases"]]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
