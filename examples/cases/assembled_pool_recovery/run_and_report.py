"""Run the official Project runner, then validate and export teaching results."""
import argparse
import json
from collections import Counter
from pathlib import Path
from _bootstrap import bootstrap

bootstrap()
from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, value):
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def summarize(project, trace):
    if project["exit_code"] or len(project["cases"]) != 1 or not project["cases"][0]["ok"]:
        raise RuntimeError("Project did not return one successful Case")
    case = project["cases"][0]
    if not trace["run_id"].startswith(case["identity"]["case_run_id"] + ":solver-run:"):
        raise RuntimeError("trace and formal result belong to different runs")
    rows, initial, final = trace["records"], trace["initial"], trace["final"]
    expected = ["preparing"] * 3 + ["search"] * 2 + ["recovery"] * 2 + ["return"]
    if [row["executed_phase"] for row in rows] != expected:
        raise RuntimeError("the default example did not execute its complete intended phase cycle")
    if [row["steps"] for row in rows] != list(range(1, 9)):
        raise RuntimeError("committed progress is missing or duplicated")
    if initial["sa_unit_exists"] or any(pop["unit_exists"] for pop in initial["populations"].values()):
        raise RuntimeError("algorithm Units were created before their first actual use")
    if any(pop["unit_exists"] for row in rows[:3] for pop in row["populations"].values()):
        raise RuntimeError("a waiting population created its Unit prematurely")
    if rows[4]["stagnation"] != 1 or rows[4]["phase_after"] != "recovery":
        raise RuntimeError("recovery was not triggered by the declared stagnation metric")
    if rows[5]["sa_temperature"] != 0.4 or rows[5]["sa_current_score"] is None:
        raise RuntimeError("SA did not restart with an independently evaluated recovery baseline")
    if any(pop["members"] != 3 for pop in final["populations"].values()):
        raise RuntimeError("the two private populations did not retain their declared capacities")
    output = case["output"]
    if output["report"]["evaluation_count"] != final["evaluations"] or final["evaluations"] != 29:
        raise RuntimeError("formal and committed evaluation counts do not agree with the default plan")
    if not case["resource_usage"]["binding"]["current"]:
        raise RuntimeError("the effective Project L0 grant is not acknowledged")
    populations_at_intake = rows[3]["populations"]
    a_refs, b_refs = (populations_at_intake[name]["refs"] for name in ("population_a", "population_b"))
    # The installed proposals derive new identities; original allocations are
    # evidenced separately by each exact version's provenance in trace.json.
    if {ref["candidate_token"] for ref in a_refs} & {ref["candidate_token"] for ref in b_refs}:
        raise RuntimeError("the separately allocated population intakes share a proposal identity")
    allocations = {name: [item["metadata"]["solution_source_ref"] for item in population["provenance"]]
                   for name, population in populations_at_intake.items()}
    source_keys = [json.dumps(ref, sort_keys=True) for refs in allocations.values() for ref in refs]
    if len(source_keys) != 6 or len(set(source_keys)) != 6:
        raise RuntimeError("the two populations did not receive six disjoint exact source versions")
    increments, previous = [], 0
    for row in rows:
        increments.append(row["evaluations"] - previous)
        previous = row["evaluations"]
    return {
        "project_run_id": project["run_id"], "solver_run_id": trace["run_id"],
        "case_run_id": case["identity"]["case_run_id"], "status": case["status"],
        "logical_steps": final["steps"], "evaluations": final["evaluations"],
        "executed_phases": [row["executed_phase"] for row in rows],
        "phase_counts": dict(Counter(row["executed_phase"] for row in rows)),
        "evaluations_per_step": increments, "best_selection_objectives": output["best_objectives"],
        "best_candidate": output["best_solution"]["values"],
        "best_candidate_token": output["best_candidate_token"], "final_phase": final["phase_after"],
        "initial_source_allocations": allocations,
        "population_sizes": {name: pop["members"] for name, pop in final["populations"].items()},
        "prepared_candidate_count": rows[2]["prepared_count"], "initial_intake_quotas": [3, 3],
        "resource_binding_current": True, "resource_grant": case["resource_usage"]["authorized_grant"],
        "checks": ["正式结果与轨迹运行身份一致", "完整执行 preparing/search/recovery/return",
                   "等待阶段不创建种群 Unit", "按 raw metric 停滞后唤醒 SA",
                   "SA 重新加热并先评估起点", "两个私有种群保持各自容量",
                   "两群初始化提案身份不重叠", "正式求值数与提交轨迹一致", "L0 授权生效"],
    }


def write_report(summary):
    lines = ["# SA → 双种群 → SA 恢复 → 返回竞争：实际结果", "",
             f"Project run：`{summary['project_run_id']}`。", "",
             f"- 状态：`{summary['status']}`；逻辑提交 `{summary['logical_steps']}` 步，实际求值 `{summary['evaluations']}` 次。",
             f"- 执行阶段：`{summary['executed_phases']}`。",
             f"- 每步求值：`{summary['evaluations_per_step']}`。",
             f"- 最终选择目标：`{summary['best_selection_objectives']}`。",
             f"- 最终候选：`{summary['best_candidate']}`。",
             f"- 两个独立种群：`{summary['population_sizes']}`。", "",
             "本例故意从真实目标的平坦最优区域附近开始，以很小预算复现停滞触发。目标等于零不表示 SA 跳出了局部最优，也不构成算法效果比较。", "",
             "## 已执行的核对", "", *[f"- {check}。" for check in summary["checks"]], "",
             "## 原始文件", "", "- [汇总](results/summary.json)",
             "- [每次提交及精确成员引用/来源](results/trace.json)",
             "- [紧凑 CSV 轨迹](results/trace.csv)", "- [正式 Project 返回值](results/project_result.json)", "",
             "轨迹文件是观察报告，不冒充权威 Snapshot 或 Artifact 收据；完整运行存储位于本地 `.blackbase/`。", ""]
    atomic_write_text(ROOT / "RESULTS.md", "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if not args.report_only:
        result = execute_project(ROOT)
        write_json(RESULTS / "project_result.json", result.as_dict())
        if not result.ok:
            return result.exit_code or 1
    project = json.loads((RESULTS / "project_result.json").read_text(encoding="utf-8"))
    trace = json.loads((RESULTS / "trace.json").read_text(encoding="utf-8"))
    summary = summarize(project, trace)
    write_json(RESULTS / "summary.json", summary)
    write_report(summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
