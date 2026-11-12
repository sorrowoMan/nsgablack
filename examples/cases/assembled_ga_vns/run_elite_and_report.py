"""正式Project elite分组：GA选择副池 → VNS精修 → 聚合提案返回竞争。"""
import argparse
import json

from run_and_report import ROOT, RESULTS, DemoConfig, execute_project, summarize, write_json
from project_config import ELITE_DEMO_CONFIG
from nsgablack.utils.engineering.file_io import atomic_write_text


DESTINATION = RESULTS / "elite"


def summarize_elite(project, trace):
    settings = DemoConfig(**ELITE_DEMO_CONFIG)
    summary = summarize(project, trace, settings=settings)
    records = trace["records"]
    source = records[settings.ga_steps - 1]
    first_vns = records[settings.ga_steps]
    final = records[-1]
    if (len(source["elite"]["refs"]) != settings.elite_count
            or first_vns["frozen_refinement_refs"] != source["elite"]["refs"]):
        raise ValueError("VNS did not freeze exactly the GA-selected elite versions")
    source_members = {json.dumps(ref, sort_keys=True) for ref in source["ga_member_refs"]}
    if not all(json.dumps(ref, sort_keys=True) in source_members for ref in source["elite"]["refs"]):
        raise ValueError("GA elite is not a subset of its selected members")
    aggregate_count = settings.refinement_count * (1 + (settings.local_steps - 1) * settings.local_batch)
    expected = settings.ga_steps * settings.population_size + 2 * aggregate_count
    if (summary["evaluations"] != expected or expected != settings.evaluation_budget
            or len(final["aggregate_return"]["refs"]) != aggregate_count
            or not final["source_raw_unchanged"]):
        raise ValueError("aggregate handoff, raw evidence or evaluation budget disagrees")
    if [row["evaluations"] for row in summary["phases"]] != [
            settings.ga_steps * settings.population_size, aggregate_count, aggregate_count]:
        raise ValueError("reading the elite source added evaluations or return intake was incomplete")
    return {**summary, "source_pool": source["elite"]["name"],
        "frozen_elite_refs": source["elite"]["refs"], "elite_count": settings.elite_count,
        "frozen_elite_consumed": True, "source_raw_unchanged": True,
        "aggregate_return_count": aggregate_count,
        "return_semantics": "all_admitted_refinement_proposals_not_only_final_selected",
        "evaluation_limit": settings.evaluation_budget, "source_read_added_evaluations": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if not args.report_only:
        result = execute_project(ROOT, group="elite")
        write_json(DESTINATION / "project_result.json", result.as_dict())
        if not result.ok:
            return result.exit_code or 1
    project = json.loads((DESTINATION / "project_result.json").read_text(encoding="utf-8"))
    trace = json.loads((DESTINATION / "trace.json").read_text(encoding="utf-8"))
    summary = summarize_elite(project, trace)
    write_json(DESTINATION / "summary.json", summary)
    lines = ["# GA精英20 → VNS → GA：正式运行", "",
        f"Project run：`{summary['project_run_id']}`。", "",
        "- 同一个标准hybrid_search Case，Project elite分组显式配置，L0为1 thread / 1 worker。",
        "- GA种群24，运行2步；choose保留约束支配/拥挤度选择，从最终成员发布20个ga_elite。",
        "- VNS按准确公共池名读取并冻结20个SolutionRef，每个执行起点与邻域共2步。",
        "- 聚合refined保存40个硬接纳提案，返回GA重新求值竞争；不是20个最终精选结果的别名。",
        "- 20个任务分别发布最终选择视图；该结果与聚合提案保留不同含义。",
        "- 43次逻辑提交，GA48 + VNS40 + 返回40 = 128次求值，恰好用完128预算。",
        "- 读取精英来源不求值；冻结引用逐项一致，原始反馈未被改写，成员年龄字段仍对齐。",
        "- 默认population模式的81步/600次示例与原结果不覆盖；本轮文件独立保存到results/elite。", "",
        "完整证据：results/elite/trace.json、summary.json、project_result.json。",
        "解析最优点核对属于报告阶段独立计算，不冒充运行内持久证据。", ""]
    atomic_write_text(ROOT / "ELITE_RESULTS.md", "\n".join(lines))
    print(json.dumps({key: summary[key] for key in ("project_run_id", "logical_steps", "evaluations",
        "elite_count", "aggregate_return_count", "frozen_elite_consumed", "source_raw_unchanged")},
        ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
