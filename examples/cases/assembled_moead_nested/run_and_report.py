"""运行正式 Project 并核对嵌套视图；不另造求解循环。"""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
from _bootstrap import bootstrap

bootstrap()
from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text
from cases.direction_refinement.config import DemoConfig
from cases.direction_refinement.problem import build_problem

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, value):
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def close(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-11, abs_tol=1e-12)


def summarize(project, trace):
    settings = DemoConfig()
    if project["exit_code"] != 0 or len(project["cases"]) != 1 or not project["cases"][0]["ok"]:
        raise RuntimeError("Project did not complete one successful Case")
    case = project["cases"][0]
    if not trace["run_id"].startswith(case["identity"]["case_run_id"] + ":solver-run:"):
        raise RuntimeError("trace does not belong to the formal Case run")
    rows = trace["records"]
    expected = (["bootstrap"] * settings.bootstrap_steps
                + ["coarse"] * (settings.directions * settings.local_steps)
                + ["fine"] * (settings.directions * settings.local_steps)
                + ["return"] * settings.return_steps)
    if [row["phase"] for row in rows] != expected:
        raise RuntimeError("actual committed phase order differs from task barriers")
    if [row["logical_steps"] for row in rows] != list(range(1, settings.max_steps + 1)):
        raise RuntimeError("logical step counters are not consecutive")
    evaluation_deltas = [rows[0]["evaluations"]] + [b["evaluations"] - a["evaluations"] for a, b in zip(rows, rows[1:])]
    expected_deltas = ([settings.directions] + [min(3, settings.directions)] * (settings.bootstrap_steps - 1)
        + ([1] + [settings.neighborhood_batch] * (settings.local_steps - 1)) * (2 * settings.directions)
        + [min(settings.router_budget, settings.local_evaluations - i * settings.router_budget)
           for i in range(settings.return_steps)])
    if evaluation_deltas != expected_deltas:
        raise RuntimeError("baseline/neighborhood/return evaluation increments differ from the assembled plan")
    initial = trace["initial"]["roles"]
    if any(r["unit_exists"] or r["current_unit_exists"] or r["neighborhood_unit_exists"] for r in initial):
        raise RuntimeError("a Unit was constructed before algorithm activation")
    for role_name, forbidden in (("coarse", {"bootstrap"}), ("fine", {"bootstrap", "coarse"})):
        for row in rows:
            role = next(r for r in row["roles"] if r["role"] == role_name)
            if row["phase"] in forbidden and (role["unit_exists"] or role["current_unit_exists"] or role["neighborhood_unit_exists"]):
                raise RuntimeError("inactive refiner constructed a Unit")
    views = trace["views"]
    if any(len(views[name]) != settings.directions for name in ("moead", "coarse", "fine")):
        raise RuntimeError("each algorithm must publish exactly one view per direction/task")
    coarse_by_id = {v["metadata"]["view_id"]: v for v in views["coarse"]}
    problem = build_problem()
    scores = []
    for fine in views["fine"]:
        metadata = fine["metadata"]
        coarse = coarse_by_id[metadata["parent"]["view_id"]]
        projection = metadata["projection"]
        if projection != coarse["metadata"]["projection"] or len(metadata["parent"]["ancestors"]) != 1:
            raise RuntimeError("fine result lost its frozen projection or two-level ancestry")
        if metadata["parent"]["revision"] != coarse["metadata"]["revision"]:
            raise RuntimeError("fine result references the wrong coarse revision")
        for view in (coarse, fine):
            if len(view["refs"]) != 1 or view["raw_violations"] != [0.0]:
                raise RuntimeError("a selected result has invalid identity or feasibility")
            actual = problem.evaluate(view["candidates"][0])
            if not all(close(a, b) for a, b in zip(actual, view["raw_objectives"][0])):
                raise RuntimeError("stored raw two-objective evidence disagrees with the analytic problem")
        weights = projection["weights"]
        coarse_score = sum(w*f for w, f in zip(weights, coarse["raw_objectives"][0]))
        fine_score = sum(w*f for w, f in zip(weights, fine["raw_objectives"][0]))
        if fine_score > coarse_score + 1e-11:
            raise RuntimeError("fine VNS selected a worse result in the same frozen comparison frame")
        optimum = (weights[0] - weights[1]) / sum(weights)
        scores.append({"slot": metadata["slot"], "weights": weights,
            "coarse_x": coarse["candidates"][0][0], "fine_x": fine["candidates"][0][0],
            "coarse_projected_score": coarse_score, "fine_projected_score": fine_score,
            "analytic_direction_optimum_x": optimum,
            "fine_distance_to_direction_optimum": abs(fine["candidates"][0][0] - optimum),
            "coarse_view_id": coarse["metadata"]["view_id"], "fine_view_id": metadata["view_id"]})
    population = trace["final_population"]
    if len(population["refs"]) != settings.directions or population["adapter_objectives"] != population["raw_objectives"]:
        raise RuntimeError("MOEA/D population identity/raw objective alignment is invalid")
    if any(not all(close(a, b) for a, b in zip(problem.evaluate(x), f))
           for x, f in zip(population["candidates"], population["raw_objectives"])):
        raise RuntimeError("MOEA/D raw objectives were changed by a projection")
    final = trace["final"]
    if any(role["task"]["status"] != "done" for role in final["roles"]):
        raise RuntimeError("not all nested tasks and return competition completed")
    if case["output"]["report"]["evaluation_count"] != final["evaluations"]:
        raise RuntimeError("formal evaluation count disagrees with committed observations")
    if not case["resource_usage"]["binding"]["current"]:
        raise RuntimeError("effective Project L0 grant is not bound")
    phases, previous = [], 0
    for name in ("bootstrap", "coarse", "fine", "return"):
        stage = [row for row in rows if row["phase"] == name]
        phases.append({"phase": name, "steps": len(stage), "evaluations": stage[-1]["evaluations"] - previous})
        previous = stage[-1]["evaluations"]
    return {"project_run_id": project["run_id"], "solver_run_id": trace["run_id"],
        "case_run_id": case["identity"]["case_run_id"], "status": case["status"],
        "config": asdict(settings), "logical_steps": final["logical_steps"], "evaluations": final["evaluations"],
        "phases": phases, "per_step_evaluation_deltas": evaluation_deltas,
        "directions": sorted(scores, key=lambda row: row["slot"]),
        "aggregates": trace["aggregates"], "final_population": population,
        "resource_binding_current": True, "resource_grant": case["resource_usage"]["authorized_grant"],
        "case_elapsed_seconds": case["elapsed_seconds"],
        "checks": ["同一次 Project/Case/轨迹运行", "真实阶段屏障与连续提交计数",
            "各层每个任务都真实求值基准和邻域，返回每批也重新求值",
            "未激活的粗细 VNS 均未创建 Unit", "六方向各有粗搜和细搜最终选择视图",
            "冻结父视图身份、revision、祖先和投影保持一致", "细搜同方向分数不劣于粗搜起点",
            "存储 raw feedback 与解析双目标一致", "返回 MOEA/D 后仍是原始双目标而非标量",
            "粗搜、细搜和返回池任务均已完成", "正式求值计数与 Project L0 授权对账"]}


def write_report(summary):
    lines = ["# MOEA/D → 粗 VNS → 细 VNS → MOEA/D：真实运行结果", "",
        f"Project run：`{summary['project_run_id']}`。", "",
        f"完成 **{summary['logical_steps']} 次逻辑提交、{summary['evaluations']} 次实际求值**。", "",
        "本例是双目标问题，没有唯一的‘全局最优 x’。下列标量只在各自方向的固定权重下比较。", "", "## 分阶段对账", ""]
    lines += [f"- `{p['phase']}`：{p['steps']} 步、{p['evaluations']} 次求值。" for p in summary["phases"]]
    lines += ["", "## 每方向的两层结果", ""]
    for d in summary["directions"]:
        lines.append(f"- 方向 {d['slot']}，权重 `{d['weights']}`：粗搜 x=`{d['coarse_x']:.9g}`、投影分数 `{d['coarse_projected_score']:.9g}`；细搜 x=`{d['fine_x']:.9g}`、分数 `{d['fine_projected_score']:.9g}`；该方向解析最优 x=`{d['analytic_direction_optimum_x']:.9g}`。")
    lines += ["", "## 核对", ""] + [f"- {check}。" for check in summary["checks"]]
    lines += ["", "## 数据文件", "", "- [精简结果](results/summary.json)",
        "- [逐步观测、精确 SolutionRef、视图元数据和 raw 反馈](results/trace.json)",
        "- [正式 Project 返回值](results/project_result.json)", "",
        "解析重算和方向分数计算发生在报告阶段，不计入求解器求值预算，不冒充新发布的权威证据。轨迹文件是观察文件；正式 Artifact 收据和执行记录仍以 Project 返回与 `.blackbase/` 为准。",
        "该运行只验证装配和语义交接，不证明嵌套精修优于其他算法。", ""]
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
    print(json.dumps({"status": summary["status"], "steps": summary["logical_steps"],
        "evaluations": summary["evaluations"], "report": str(ROOT / "RESULTS.md")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
