"""调用正式 Project runner，校验运行身份后整理教学报告；不实现搜索或调度。"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from nsgablack.project.project_runner import execute_project
from nsgablack.utils.engineering.file_io import atomic_write_text


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def write_json(path, payload):
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))


def summarize(project, *, wall_seconds):
    if project["exit_code"] or project["status"] != "ok":
        raise RuntimeError("Project failed; inspect results/project_result.json")
    cases = {}
    for case in project["cases"]:
        name, identity = case["request"]["case_name"], case["identity"]
        if not case["ok"] or identity["project_run_id"] != project["run_id"]:
            raise ValueError(f"{name}: Case did not succeed in this Project run")
        resources = case["resource_usage"]
        if not resources["binding"]["current"]:
            raise ValueError(f"{name}: effective L0 resource binding is stale")
        if "summary" not in case["artifact_publications"]:
            raise ValueError(f"{name}: no authoritative summary publication")
        output = case["output"]
        runtime_state = case["metadata"].get("runtime_state", {})
        assembled = {key: runtime_state[key] for key in (
            "case_class", "problem", "pipeline", "adapter", "initializer", "mutator", "repair",
            "providers", "provider_names", "plugin_names", "adapter_components") if key in runtime_state}
        trace_path = RESULTS / name / "trace.json"
        trace = None
        if trace_path.is_file():
            trace = json.loads(trace_path.read_text(encoding="utf-8-sig"))
            if not trace["run_id"].startswith(identity["case_run_id"] + ":solver-run:"):
                raise ValueError(f"{name}: trace belongs to an older/different run")
        cases[name] = {
            "case_run_id": identity["case_run_id"], "status": case["status"],
            "logical_steps": output["report"]["steps"],
            "evaluations": output["report"]["evaluation_count"],
            "best_solution": output.get("best_solution"),
            "best_objectives": output.get("best_objectives"),
            "best_candidate_token": output.get("best_candidate_token"),
            "assembled": assembled,
            "grant": resources["authorized_grant"],
            "namespace": resources["effective_context"]["namespace"],
            "resource_binding_current": True,
            "started_at": case["started_at"], "finished_at": case["finished_at"],
            "artifact_refs": case["artifact_refs"],
            "artifact_publications": case["artifact_publications"],
            "input_bindings": case["request"]["input_artifact_bindings"],
            "trace_file": None if trace is None else str(trace_path.relative_to(ROOT)),
        }
    topology = {"project_group": project["group"], "top_level_cases": list(cases)}
    if {"hybrid_search", "directions", "outer_nested"}.issubset(cases):
        first = [cases["hybrid_search"], cases["directions"]]
        overlap = max(0., min(row["finished_at"] for row in first)
                      - max(row["started_at"] for row in first))
        outer = cases["outer_nested"]
        if outer["started_at"] < max(row["finished_at"] for row in first):
            raise ValueError("outer Case started before its upstream publications completed")
        bindings = outer["input_bindings"]
        expected = {"hybrid_summary": "hybrid_search.summary", "directions_summary": "directions.summary"}
        if set(bindings) != set(expected):
            raise ValueError("outer Case is missing one declared authoritative input")
        for name, key in expected.items():
            if bindings[name] != project["artifact_bindings"][key]:
                raise ValueError("downstream ArtifactBinding differs from the producer publication")
        topology.update(lifecycle_overlap_seconds=overlap,
                        observed_parallel_lifecycles=overlap > 0.,
                        upstream_artifacts_verified=True, downstream_after_both=True)
    return {"project_run_id": project["run_id"], "group": project["group"],
            "status": project["status"], "wall_seconds": wall_seconds,
            "manifest_path": project["manifest_path"], "cases": cases,
            "topology": topology,
            "artifact_names": sorted(project["artifact_registry"]),
            "scope": "装配、交接、授权与运行身份验证；不比较不同问题上的算法性能"}


def write_report(summary):
    lines = ["# 综合装配 Project：本次实际结果", "",
             f"Project run：`{summary['project_run_id']}`；group：`{summary['group']}`。", "",
             f"正式 manifest：`{summary['manifest_path']}`。", ""]
    for name, case in summary["cases"].items():
        assembled = case["assembled"]
        component_line = ", ".join(f"{key}={assembled[key]}" for key in (
            "case_class", "problem", "pipeline", "adapter") if key in assembled)
        best = case["best_solution"]
        candidate = best.get("values") if isinstance(best, dict) else best
        grant = {key: case["grant"][key] for key in ("threads", "workers", "gpus", "backend")}
        published = sorted(case["artifact_publications"])
        archives = sum(name.startswith("evaluation-evidence-archive-") for name in published)
        named = [name for name in published if not name.startswith("evaluation-evidence-archive-")]
        lines += [f"## {name}", "",
                  f"- `{case['logical_steps']}` 次逻辑提交，`{case['evaluations']}` 次本层求值。",
                  f"- 最终候选：`{candidate}`；选择目标：`{case['best_objectives']}`。",
                  f"- 实际装配：`{component_line}`。",
                  f"- Plugins：`{assembled.get('plugin_names', [])}`；Providers：`{assembled.get('provider_names', [])}`。",
                  f"- L0 grant：`{grant}`，binding.current=`true`。",
                  f"- namespace：`{case['namespace']}`。",
                  f"- 权威发布：`{named}`，另有 `{archives}` 份求值证据归档。", ""]
    topology = summary["topology"]
    if "lifecycle_overlap_seconds" in topology:
        lines += ["## Project 交接", "",
                  f"- 两个上游 Case 生命周期重叠 `{topology['lifecycle_overlap_seconds']:.6f}` 秒。",
                  "- outer_nested 在两个上游发布完成后启动，输入绑定与生产者权威发布一致。",
                  "- 生命周期重叠不是 CPU 利用率或性能加速比测量。", ""]
    lines += ["## 如何读这些结果", "",
              "hybrid_search 的 raw 与 selection 不同：Bias 改软评分，原始约束接纳单独判断。",
              "directions 不加 Bias，保留多目标原始反馈，投影只用于任务比较。",
              "outer_nested 的本层求值次数是外层候选数；内层求解的开销与收据在 nested 报告中单独列出。",
              "各 Case 的目标含义不同，不用一个 best 分数对它们排优劣。", "",
              "- [结构化汇总](results/summary.json)",
              "- [完整正式返回值](results/project_result.json)",
              "- [主 Case 提交轨迹](results/hybrid_search/trace.json)",
              "- [方向与投影轨迹](results/directions/trace.json)",
              "- [装配教程](README.md)", "",
              "trace 是观察报告；跨 Case 使用 ArtifactBinding，不能把 JSON 文件名当权威引用。", ""]
    atomic_write_text(ROOT / "RESULTS_CN.md", "\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", default="default")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    if args.report_only:
        project = json.loads((RESULTS / "project_result.json").read_text(encoding="utf-8"))
        timing = json.loads((RESULTS / "timing.json").read_text(encoding="utf-8"))
        if timing["project_run_id"] != project["run_id"]:
            raise ValueError("timing and Project result are from different runs")
        wall_seconds = timing["wall_seconds"]
    else:
        started = time.perf_counter()
        result = execute_project(ROOT, group=args.group)
        project = result.as_dict()
        wall_seconds = time.perf_counter() - started
        write_json(RESULTS / "project_result.json", project)
        write_json(RESULTS / "timing.json", {"project_run_id": project["run_id"],
                                           "wall_seconds": wall_seconds})
        if not result.ok:
            return result.exit_code or 1
    summary = summarize(project, wall_seconds=wall_seconds)
    write_json(RESULTS / "summary.json", summary)
    write_report(summary)
    print(json.dumps({"project_run_id": project["run_id"], "group": project["group"],
                      "cases": {name: {key: case[key] for key in ("logical_steps", "evaluations")}
                                for name, case in summary["cases"].items()},
                      "report": str(ROOT / "RESULTS_CN.md")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
