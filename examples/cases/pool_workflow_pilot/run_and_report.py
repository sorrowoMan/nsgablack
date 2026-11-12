"""只调用正式 execute_project，再核对同次运行的只读输出。"""
import argparse
import json
import math
from pathlib import Path
from _bootstrap import bootstrap

bootstrap()
from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, value):
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def summarize(project):
    if project["exit_code"] or len(project["cases"]) != 3:
        raise RuntimeError("expected three successful standard Cases")
    summary = {"project_run_id": project["run_id"], "cases": {}}
    for case in project["cases"]:
        name = case["request"]["case_name"]
        trace = json.loads((RESULTS / f"{name}.json").read_text(encoding="utf-8"))
        if not case["ok"] or not trace["run_id"].startswith(case["identity"]["case_run_id"] + ":solver-run:"):
            raise RuntimeError("Case failed or trace belongs to another run")
        initial, final = trace["initial"], trace["final"]
        if any(initial[key] for key in ("unit_exists", "current_exists", "neighborhood_exists")):
            raise RuntimeError("source generation eagerly constructed an algorithm Unit")
        if [row["steps"] for row in trace["records"]] != list(range(1, trace["max_steps"] + 1)):
            raise RuntimeError("logical progress contains gaps")
        if len(initial["initial_refs"]) != (3 if name == "vns_search" else 8):
            raise RuntimeError("Pipeline source did not populate mother pool before search")
        result = trace["result"]
        if len(result["refs"]) != (1 if name == "vns_search" else 6):
            raise RuntimeError("result does not have the expected exact membership")
        if case["output"]["report"]["evaluation_count"] != final["evaluations"]:
            raise RuntimeError("formal and observed evaluation counts differ")
        for ref, x, f, v, provenance in zip(result["refs"], result["candidates"],
                result["raw_objectives"], result["raw_violations"], result["provenance"]):
            if provenance["candidate_token"] != ref["candidate_token"] or v != 0 or any(abs(t) > 2 for t in x):
                raise RuntimeError("result identity, raw constraints or bounds disagree")
            expected = ([sum((t - c)**2 for t, c in zip(x, [.5, -.5]))] if name == "vns_search"
                        else [sum((t - c)**2 for t, c in zip(x, [-1., 0.])),
                              sum((t - c)**2 for t, c in zip(x, [1., 0.]))])
            if len(f) != len(expected) or any(not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-14)
                                             for a, b in zip(f, expected)):
                raise RuntimeError("stored raw feedback differs from analytic Problem")
        binding = case["resource_usage"]["binding"]
        if not binding["current"]:
            raise RuntimeError("Case resource grant is not current")
        if name == "moead_search" and len(trace["views"]) != 6:
            raise RuntimeError("MOEA/D did not publish every direction view")
        source_tokens = {ref["candidate_token"] for ref in initial["initial_refs"]}
        selected_seeds = initial["initial_refs"][:1 if name == "vns_search" else 6]
        intake_sources = [record["metadata"]["solution_source_ref"]
                          for record in trace["intake"]["provenance"]]
        if intake_sources != selected_seeds:
            raise RuntimeError("input handoff lost the exact frozen mother-pool versions")
        if any(ref["candidate_token"] in source_tokens for ref in trace["intake"]["refs"]):
            raise RuntimeError("pool handoff did not derive a proposal identity")
        change_records = [record for record in result["provenance"]
                          if record.get("metadata", {}).get("change_input_refs")]
        if not change_records:
            raise RuntimeError("no selected result carries ordinary-change input lineage")
        output = trace["change_output"]
        accepted = trace["accepted"]
        raw_by_ref = {json.dumps(ref, sort_keys=True): (f, v) for ref, f, v in zip(
            accepted["refs"], accepted["raw_objectives"], accepted["raw_violations"], strict=True)}
        previous = initial
        for row in trace["records"]:
            old_elite = previous["elite"]
            # Each owning leaf update maintains the archive once, using only
            # previous members plus this batch's newly accepted exact versions.
            incoming = accepted["refs"][previous["accepted_count"]:row["accepted_count"]]
            candidates = old_elite["refs"] + incoming
            unique = {json.dumps(ref, sort_keys=True): ref for ref in candidates}
            def key(ref):
                f, v = raw_by_ref[json.dumps(ref, sort_keys=True)]
                return (v > 0., max(v, 0.), sum(f))
            expected_members = sorted(unique.values(), key=key)[:20]
            elite = row["elite"]
            if elite["refs"] != expected_members:
                raise RuntimeError("elite members differ from the current accepted-batch top20")
            if elite["descriptor"]["view_id"] != initial["elite"]["descriptor"]["view_id"]:
                raise RuntimeError("elite maintenance recreated its collection identity")
            changed = expected_members != old_elite["refs"]
            if elite["descriptor"]["revision"] != old_elite["descriptor"]["revision"] + int(changed):
                raise RuntimeError("elite revision changed without a membership change or changed repeatedly")
            previous = row
        if len(output["refs"]) != final["evaluations"] - trace["records"][0]["evaluations"]:
            raise RuntimeError("named output lost admitted change proposals or included bootstrap seeds")
        for ref, record in zip(output["refs"], output["provenance"], strict=True):
            command = record["metadata"]["change_outputs"]
            if command["proposal_token"] != ref["candidate_token"]:
                raise RuntimeError("named output replayed an ancestor instruction")
            if name != "ga_search" and not any(source in initial["initial_refs"]
                       for source in record["metadata"]["change_input_refs"]):
                raise RuntimeError("change did not retain exact additional reference-pool inputs")
            if name == "ga_search":
                sources = record["metadata"].get("change_source_refs", ())
                if len(sources) != 2 or any(source not in accepted["refs"] for source in sources):
                    raise RuntimeError("GA child lost its two exact evaluated parent sources")
        if len({ref["candidate_token"] for ref in output["refs"]}) != len(output["refs"]):
            raise RuntimeError("independent children do not have distinct proposal identities")
        if name == "moead_search":
            branches = {int(index) % 2 for row in trace["records"][1:]
                        for index in row["runtime"]["moead_subproblem"]}
            if branches != {0, 1}:
                raise RuntimeError("both composition orders were not exercised")
        first = trace["records"][0]
        summary["cases"][name] = {
            "solver_run_id": trace["run_id"], "steps": final["steps"],
            "evaluations": final["evaluations"], "first_step_evaluations": first["evaluations"],
            "mother_pool_seeds": len(source_tokens), "result_members": len(result["refs"]),
            "published_views": len(trace["views"]),
            "direction_views": sum(view["metadata"]["kind"] == "objective_projection" for view in trace["views"]),
            "population_views": sum(view["metadata"]["kind"] == "candidate_view" for view in trace["views"]),
            "raw_objective_columns": len(result["raw_objectives"][0]),
            "result_raw_objectives": result["raw_objectives"],
            "change_output_pool": output["name"], "change_output_members": len(output["refs"]),
            "elite_members": len(final["elite"]["refs"]),
            "elite_revision": final["elite"]["descriptor"]["revision"],
            "elite_ranking": "raw feasibility, violation, sum(objectives); current accepted batch",
            "resource_binding_current": True,
            "checks": ["母池先有种子且无算法 Unit", "提交计数连续且正式求值计数一致",
                       "初始化交接保留精确母池源引用并派生提案身份", "普通 change 输入来源可按精确版本读取",
                       "跨池输入与接纳后输出保留精确引用", "结果精确引用与候选身份一致",
                       "精英池每批纳入本批反馈后取前20并保持view_id，revision仅随成员改变",
                       "原始目标解析核对及边界通过", "Project L0 授权生效"],
        }
    return summary


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
    summary = summarize(project)
    write_json(RESULTS / "summary.json", summary)
    lines = ["# Pool 工作流试作运行结果", "", f"Project run：`{summary['project_run_id']}`。", ""]
    for name, case in summary["cases"].items():
        lines += [f"## {name}", "", f"- 母池初始种子：{case['mother_pool_seeds']}。",
                  f"- 逻辑提交：{case['steps']}；实际求值：{case['evaluations']}；首步求值：{case['first_step_evaluations']}。",
                  f"- 最终选择成员：{case['result_members']}；发布视图：{case['published_views']}（方向{case['direction_views']}、普通成员{case['population_views']}）；原始目标列：{case['raw_objective_columns']}。"]
        lines += [f"- 接纳提案输出池：`{case['change_output_pool']}`；成员：{case['change_output_members']}。"]
        lines += [f"- 精英池成员：{case['elite_members']}；最终 revision：{case['elite_revision']}；原 view_id 保持。"]
        lines += [f"- {check}。" for check in case["checks"]]
        lines += [""]
    lines += ["精英集合在每个真实叶更新后，用旧成员与本批硬接纳反馈稳定排序，最多保留20个精确版本。",
              "本批包含最后一批反馈；maintenance不重复求值，不因多个孩子重复调用。",
              "部分接纳只授权本批已接纳精确引用；零接纳不修改；失败与原步骤一并回滚。", "",
              "这是装配与数据交付核对，不是算法优越性 benchmark。解析核对不计入 Solver 求值。", "",
              "观察 JSON 不替代 Authority Snapshot、Artifact 收据或可传输 checkpoint。", ""]
    atomic_write_text(ROOT / "RESULTS.md", "\n".join(lines))
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
