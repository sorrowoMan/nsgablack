"""正式Project plan分组；核对两轮局部编排与当前请求最终结果交还。"""
import argparse
import json

from run_and_report import ROOT, RESULTS, execute_project, write_json
from project_config import PLAN_DEMO_CONFIG


DESTINATION = RESULTS / "plan"


def summarize_plan(project, trace):
    options = PLAN_DEMO_CONFIG
    if project["exit_code"] != 0 or len(project["cases"]) != 1:
        raise RuntimeError("plan Project did not return one successful Case")
    case = project["cases"][0]
    if not trace["run_id"].startswith(case["identity"]["case_run_id"] + ":solver-run:"):
        raise ValueError("plan trace belongs to another run")
    records = trace["records"]
    per_round = (["ga"] * options["ga_steps"]
        + ["vns"] * (options["elite_count"] * options["local_steps"]) + ["return"])
    if [row["phase"] for row in records] != per_round * options["rounds"]:
        raise ValueError("local phase order disagrees with the nested plan")
    if [row["logical_steps"] for row in records] != list(range(1, len(records) + 1)):
        raise ValueError("control transitions manufactured or lost a logical step")
    evidence = []
    previous_requests = set()
    for iteration in range(options["rounds"]):
        rows = records[iteration * len(per_round):(iteration + 1) * len(per_round)]
        ga_end, first_vns, returned = rows[options["ga_steps"] - 1], rows[options["ga_steps"]], rows[-1]
        request = first_vns["refinement_request"]
        if request in previous_requests:
            raise ValueError("a new round reused a completed refinement request")
        previous_requests.add(request)
        if first_vns["frozen_refinement_refs"] != ga_end["elite"]["refs"]:
            raise ValueError("VNS did not freeze this round's current GA elite")
        selected = returned["selected_return"]
        if len(selected) != options["elite_count"] or not returned["source_raw_unchanged"]:
            raise ValueError("current final results or source raw evidence disagree")
        aggregate = returned["aggregate_return"]["refs"]
        if len(aggregate) <= len(selected):
            raise ValueError("the example must distinguish accepted history from selected results")
        evidence.append({"iteration": iteration, "request": request,
            "frozen_elite_refs": first_vns["frozen_refinement_refs"],
            "selected_return_refs": selected, "accepted_history_count": len(aggregate),
            "source_raw_unchanged": True})
    expected_evaluations = options["rounds"] * (
        options["ga_steps"] * options["population_size"]
        + options["elite_count"] * (1 + (options["local_steps"] - 1) * options["local_batch"])
        + options["elite_count"])
    final = trace["final_summary"]
    if (not final["execution_plan"]["completed"]
            or final["evaluations"] != expected_evaluations
            or case["output"]["report"]["evaluation_count"] != expected_evaluations):
        raise ValueError("plan completion and actual evaluation accounting disagree")
    return {"project_run_id": project["run_id"], "case_run_id": case["identity"]["case_run_id"],
        "solver_run_id": trace["run_id"], "logical_steps": len(records),
        "evaluations": final["evaluations"], "rounds": options["rounds"],
        "completed": True, "phase_order": [row["phase"] for row in records],
        "return_semantics": "current_request_final_selected_results",
        "resource_binding_current": case["resource_usage"]["binding"]["current"],
        "round_evidence": evidence, "config": options}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if not args.report_only:
        result = execute_project(ROOT, group="plan")
        write_json(DESTINATION / "project_result.json", result.as_dict())
        if not result.ok:
            return result.exit_code or 1
    project = json.loads((DESTINATION / "project_result.json").read_text(encoding="utf-8"))
    trace = json.loads((DESTINATION / "trace.json").read_text(encoding="utf-8"))
    summary = summarize_plan(project, trace)
    write_json(DESTINATION / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in (
        "project_run_id", "logical_steps", "evaluations", "rounds", "completed",
        "return_semantics", "resource_binding_current")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
