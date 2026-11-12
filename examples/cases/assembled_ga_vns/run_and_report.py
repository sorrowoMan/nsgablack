"""调用正式 Project runner；只对返回值与提交轨迹整理教学报告。"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

from _bootstrap import bootstrap

bootstrap()
from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text
from cases.hybrid_search.config import DemoConfig
from cases.hybrid_search.problem import build_problem

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, value):
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def unit(record, class_name):
    return next(item for item in record["units"] if item["type"] == class_name)


def summarize(project, trace, *, settings=None):
    """交叉核对正式结果与本例观测；不据观察值改写框架状态。"""
    settings = DemoConfig() if settings is None else settings
    if project["exit_code"] != 0 or len(project["cases"]) != 1:
        raise RuntimeError("Project did not produce one successful Case")
    case = project["cases"][0]
    if not case["ok"]:
        raise RuntimeError(f"Case failed: {case['failure']}")
    case_id = case["identity"]["case_run_id"]
    if not trace["run_id"].startswith(case_id + ":solver-run:"):
        raise RuntimeError("trace belongs to another run; refusing a stale report")
    initial, records, final = trace["initial"], trace["records"], trace["final_summary"]
    expected = (["ga"] * settings.ga_steps
                + ["vns"] * (settings.refinement_count * settings.local_steps) + ["return"])
    if [item["phase"] for item in records] != expected:
        raise RuntimeError("committed phase order differs from the assembled schedule")
    if [item["logical_steps"] for item in records] != list(range(1, settings.max_steps + 1)):
        raise RuntimeError("committed progress contains a gap or duplicate")
    if any(item["structure_exists"] or item["current_exists"] or item["neighborhood_exists"]
           for item in initial["units"]):
        raise RuntimeError("a Unit was created before the first search operation")
    if any(unit(item, "VNSAdapter")["current_exists"]
           or unit(item, "VNSAdapter")["neighborhood_exists"]
           for item in records[:settings.ga_steps]):
        raise RuntimeError("inactive VNS created a Unit during the GA phase")
    first_vns = unit(records[settings.ga_steps], "VNSAdapter")
    if not first_vns["current_exists"] or not first_vns["neighborhood_exists"]:
        raise RuntimeError("VNS did not create its required Units on first activation")
    ga, vns = unit(final, "NSGA2Adapter"), unit(final, "VNSAdapter")
    if ga["population_members"] != settings.population_size or len(ga["member_age"]) != settings.population_size:
        raise RuntimeError("final GA member fields are misaligned")
    if vns["published_views"] != settings.refinement_count or vns["published_view_members"] != settings.refinement_count:
        raise RuntimeError("not every VNS member task published its selected result")
    formal, best = case["output"], trace["final_incumbent"]
    if formal["best_candidate_token"] != best["candidate_token"]:
        raise RuntimeError("formal result and observed incumbent have different identities")
    if formal["best_objectives"] != best["selection_objectives"]:
        raise RuntimeError("formal result and observed selection feedback disagree")
    if formal["report"]["evaluation_count"] != final["evaluations"]:
        raise RuntimeError("formal result and committed evaluation counter disagree")
    # 仅独立核对解析函数；不是从记录里恢复 raw evidence，也不计入求解求值次数。
    raw_recomputed = float(build_problem().evaluate(best["candidate"]))
    penalty = 0.1 * max(0.0, -best["candidate"][0])
    if not math.isclose(raw_recomputed + penalty, best["selection_score"], rel_tol=1e-12, abs_tol=1e-14):
        raise RuntimeError("analytical objective plus declared preference disagrees with selection score")
    if not all(-4.0 <= value <= 4.0 for value in best["candidate"]):
        raise RuntimeError("final candidate violates the declared problem bounds")
    binding = case["resource_usage"]["binding"]
    if not binding["current"]:
        raise RuntimeError("Case did not acknowledge the effective Project resource grant")
    phases, previous_evaluations = [], 0
    for name in ("ga", "vns", "return"):
        rows = [item for item in records if item["phase"] == name]
        last = rows[-1]
        phases.append({"phase": name, "committed_steps": len(rows),
                       "evaluations": last["evaluations"] - previous_evaluations,
                       "best_selection_score": last["best_score"]})
        previous_evaluations = last["evaluations"]
    return {
        "project_run_id": project["run_id"], "case_run_id": case_id,
        "solver_run_id": trace["run_id"], "status": case["status"],
        "config": asdict(settings), "logical_steps": final["logical_steps"],
        "evaluations": final["evaluations"], "phases": phases, "best": best,
        "raw_objective_recomputed": raw_recomputed,
        "raw_recomputation_note": "Independent analytical check, not persisted raw evidence or another solver evaluation.",
        "known_optimum": [2.0, -1.0], "known_optimal_objective": 0.0,
        "distance_to_known_optimum": math.dist(best["candidate"], [2.0, -1.0]),
        "final_ga_members": ga["population_members"], "final_member_age": ga["member_age"],
        "ga_phase_end_member_age": unit(records[settings.ga_steps - 1], "NSGA2Adapter")["member_age"],
        "vns_result_views": vns["published_views"],
        "pool_batch_records": final["pool_records"],
        "resource_binding_current": binding["current"],
        "resource_grant": case["resource_usage"]["authorized_grant"],
        "case_elapsed_seconds": case["elapsed_seconds"],
        "checks": ["正式结果与轨迹属于同一次运行", f"{settings.max_steps} 步阶段顺序与提交计数一致",
                   "VNS 未启用时无 Unit，首次启用时创建所需 Unit", f"{settings.population_size} 个成员年龄字段仍与种群对齐",
                   f"{settings.refinement_count} 个 VNS 任务发布最终选择视图", "正式结果与轨迹的候选 token 和选择目标一致",
                   "解析目标加软偏好与选择分数一致", "最终候选符合问题边界", "Project L0 授权绑定已生效"],
    }


def write_report(summary):
    lines = ["# GA → VNS → GA 实际运行结果", "",
             f"Project run：`{summary['project_run_id']}`。固定随机种子为 7。", "",
             f"- 最终候选：`{summary['best']['candidate']}`。",
             f"- 选择目标：`{summary['best']['selection_score']:.12g}`。",
             f"- 独立重算原始目标：`{summary['raw_objective_recomputed']:.12g}`。",
             f"- 已知最优点：`[2, -1]`，最优目标：`0`；距离最优点 `{summary['distance_to_known_optimum']:.8g}`。",
             f"- 共 `{summary['logical_steps']}` 次逻辑提交、`{summary['evaluations']}` 次实际求值。", "",
             "原始目标重算是报告阶段的解析核对，不冒充持久证据，也不计入求解求值预算。", "",
             "## 分阶段对账", ""]
    for phase in summary["phases"]:
        lines.append(f"- `{phase['phase']}`：{phase['committed_steps']} 步，{phase['evaluations']} 次求值，阶段末最好选择分数 `{phase['best_selection_score']:.12g}`。")
    lines += ["", "VNS 的 252 次求值包含 12 个起点和 240 个邻域提案；返回 GA 时再评估 252 个接纳提案。",
              "`refined` 保存途中接纳提案，不等同于 12 个任务最终选择；最终选择另发布为 12 个 VNS 结果视图。", "",
              "## Unit 与交接核对", ""]
    lines += [f"- {check}。" for check in summary["checks"]]
    lines += [f"- GA 阶段结束的成员年龄：`{summary['ga_phase_end_member_age']}`。",
              f"- 最终 GA 成员年龄：`{summary['final_member_age']}`。", "",
              "GA 阶段已有成员连续存活 5 次环境选择；最终成员年龄全部为 0 是本次返回竞争的结果，不代表字段未被维护。", "",
              "## 原始文件", "",
              "- [精简结果与核对项](results/summary.json)",
              "- [每个提交步骤的 CSV](results/trace.csv)",
              "- [Unit、来源路径与实际算子绑定](results/trace.json)",
              "- [正式 Project 返回值与 Artifact 收据](results/project_result.json)", "",
              "轨迹是观察报告，不替代权威快照或 Artifact 发布收据。`.blackbase/` 保存本次 Project 执行记录与归档；报告没有内联完整求值证据，跨机器复制还需搬运各引用对应的数据。",
              "单次简单问题运行用于核对装配与数据交接，不构成算法性能比较。", ""]
    atomic_write_text(ROOT / "RESULTS.md", "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true", help="仅核对并整理上次正式运行的文件")
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
    print(json.dumps({"status": summary["status"], "steps": summary["logical_steps"],
                      "evaluations": summary["evaluations"], "best": summary["best"]["candidate"],
                      "selection_score": summary["best"]["selection_score"],
                      "report": str(ROOT / "RESULTS.md")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
