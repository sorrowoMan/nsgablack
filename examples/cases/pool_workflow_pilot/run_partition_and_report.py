"""调用正式Project分组，只读核对partition与真实GA成员应用。"""
import argparse
import json
from pathlib import Path
from _bootstrap import bootstrap

bootstrap()
from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, value):
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def summarize_partition(project):
    if project["exit_code"] or len(project["cases"]) != 1:
        raise ValueError("expected one successful partition Case")
    case = project["cases"][0]
    if not case["ok"] or case["request"]["case_name"] != "ga_partition":
        raise ValueError("unexpected partition Case result")
    trace_path = RESULTS / "ga_partition.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    if not trace["run_id"].startswith(case["identity"]["case_run_id"] + ":solver-run:"):
        # A later named-output demonstration preserves the original partition
        # observation rather than making its historical report unreadable.
        archived = RESULTS / "ga_partition_baseline.json"
        if archived.exists():
            trace_path = archived
            trace = json.loads(archived.read_text(encoding="utf-8"))
    if not trace["run_id"].startswith(case["identity"]["case_run_id"] + ":solver-run:"):
        raise ValueError("partition trace belongs to another Case run")
    if trace["final"]["steps"] != 3 or trace["final"]["evaluations"] != 260:
        raise ValueError("expected three commits and exactly 100+80+80 evaluations")
    if case["output"]["report"]["evaluation_count"] != 260:
        raise ValueError("formal evaluation count differs from observations")
    if len(trace["result"]["refs"]) != 100 or len(trace["change_output"]["refs"]) != 160:
        raise ValueError("GA capacity or admitted offspring count differs")
    if not case["resource_usage"]["binding"]["current"]:
        raise ValueError("formal Project L0 grant is not current")
    rows = trace["partitions"]
    if len(rows) != 3:
        raise ValueError("missing partition observations")
    for row, input_count, evaluations in zip(rows, (100, 180, 180), (100, 180, 260), strict=True):
        selected, remaining = row["selected_positions"], row["remaining_positions"]
        if (row["input_count"] != input_count or row["selected_count"] != 20
                or row["remaining_count"] != input_count - 20
                or len(set(selected)) != 20
                or remaining != [index for index in range(input_count) if index not in selected]):
            raise ValueError("partition is not a complete disjoint positional split")
        source = row["source_refs"]
        if (row["selected_refs"] != [source[index] for index in selected]
                or row["remaining_refs"] != [source[index] for index in remaining]
                or row["applied_refs"] != row["selected_refs"] + row["remaining_refs"][:80]):
            raise ValueError("exact source versions or GA survivor positions disagree")
        if (not row["source_unchanged"] or row["partition_added_evaluations"] != 0
                or row["evaluation_count"] != evaluations or row["evaluation_budget_reserved"] != 0):
            raise ValueError("partition changed data, evaluation counts or left a budget reservation")
    return {"project_run_id": project["run_id"], "case_run_id": case["identity"]["case_run_id"],
        "steps": 3, "evaluations": 260, "evaluation_limit": 260,
        "population_members": 100, "offspring_members": 160,
        "splits": [{key: row[key] for key in ("step", "input_count", "selected_count",
            "remaining_count", "source_unchanged", "partition_added_evaluations")} for row in rows],
        "exact_positions_applied": True, "resource_binding_current": True,
        "observation_file": trace_path.name}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if not args.report_only:
        result = execute_project(ROOT, group="partition")
        write_json(RESULTS / "project_partition_result.json", result.as_dict())
        if not result.ok:
            return result.exit_code or 1
    project = json.loads((RESULTS / "project_partition_result.json").read_text(encoding="utf-8"))
    summary = summarize_partition(project)
    write_json(RESULTS / "partition_summary.json", summary)
    lines = ["# Pool partition 正式运行", "", f"Project run：`{summary['project_run_id']}`。", "",
        "- 标准ga_partition Case，正式Project partition分组，CPU 1 thread / 1 worker。",
        "- 3次逻辑提交；求值预算260，实际100+80+80=260；partition新增求值0。",
        "- 首次真实GA选择输入100，分为20精英与80剩余；后两次输入180，分为20与160。",
        "- 普通choose每次调用partition一次，返回精英20与剩余前80，共100个生存成员。",
        "- 精确位置与SolutionRef逐项对齐；selected/remaining互斥完备，source引用与候选值不变。",
        "- 本例明确按raw可行性、违反量、目标和挑20；不是宣称等价于默认NSGA-II Pareto选择。",
        "- 只读观察在提交后复核同一确定性分区，不额外调用Problem、不改变RNG或算法成员。", "",
        f"完整引用证据见results/{summary['observation_file']}；观察文件不替代Authority或Artifact发布收据。", ""]
    atomic_write_text(ROOT / "PARTITION_RESULTS.md", "\n".join(lines))
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
