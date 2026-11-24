"""离线导出已发布成本实验的紧凑结果，不重新运行求解。"""
import json
from pathlib import Path
import statistics

from benchmarks.transparency_report import read_report


def export(manifest_path, destination):
    manifest_path, destination = Path(manifest_path), Path(destination)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "ok":
        raise ValueError("cost Project did not finish successfully")
    report = read_report(manifest["cases"][0])
    if report["mode"] != "costs" or report["validation"]["status"] != "passed" or not report["fixtures"]:
        raise ValueError("no passed cost experiment")
    summary = []
    for fixture in report["fixtures"]:
        if any(fixture["qualification"][s]["status"] != "passed" for s in ("semantics", "quality", "recovery")):
            raise ValueError("unqualified cost fixture")
        if any(row["status"] != "passed" for row in fixture["measurements"]):
            raise ValueError("failed cost measurement")
        modes = {}
        for mode in ("full", "no_step_trace", "lean"):
            rows = [r for r in fixture["measurements"] if r["mode"] == mode]
            if not rows or len({r["seed"] for r in rows}) != len(rows):
                raise ValueError("cost report requires unique seed measurements in each trace mode")
            def median(fn):
                return statistics.median(fn(r) for r in rows)
            modes[mode] = {"samples": len(rows),
                "step_callback_self_ms_per_evaluation_all_commits": median(
                    lambda r:1000*r["observer_self_time"]["wall_s"]/r["evaluations"]),
                "normal_evaluations_per_run": rows[0]["normal"]["evaluations"],
                "normal_commits_per_run": rows[0]["normal"]["commits"],
                **{clock: {"framework_s": median(lambda r:r["normal"][clock]["framework"]),
                    "reference_s": median(lambda r:r["normal"][clock]["reference"]),
                    "ratio": median(lambda r:r["normal"][clock]["ratio"]),
                    "extra_ms_per_evaluation": median(lambda r:r["normal"][clock]["difference_ms_per_evaluation"]),
                    "actual_problem_ms": median(lambda r:1000*r["normal"][clock]["framework_problem"]/r["normal"]["evaluations"]),
                    "actual_repair_ms": median(lambda r:1000*r["normal"][clock]["framework_repair"]/r["normal"]["evaluations"]),
                    "extra_nonproblem_nonrepair_ms": median(lambda r:1000*r["normal"][clock]["extra_nonproblem_nonrepair"]/r["normal"]["evaluations"])}
                    for clock in ("wall_s", "cpu_s")}}
        n = modes["lean"]["normal_evaluations_per_run"]
        seeds = sorted({r["seed"] for r in fixture["measurements"]})
        if any({r["seed"] for r in fixture["measurements"] if r["mode"] == mode} != set(seeds)
               for mode in ("full", "no_step_trace", "lean")):
            raise ValueError("cost trace modes must share the same seeds")
        normalized = {}
        for clock in ("wall_s", "cpu_s"):
            samples = []
            for seed in seeds:
                by_mode = {r["mode"]: r for r in fixture["measurements"] if r["seed"] == seed}
                samples.append(1000*(by_mode["full"]["normal"][clock]["framework_remainder"]
                    - by_mode["lean"]["normal"][clock]["framework_remainder"])/n)
            normalized[clock] = {"samples":samples, "median":statistics.median(samples),
                "scope":"full-minus-lean after removing each run's actual Problem and repair; signed estimate, not exact attribution"}
        summary.append({"name":fixture["name"], "metadata":fixture["metadata"], "modes":modes,
            "normalized_trace_effect_ms_per_evaluation":normalized,
            "trace_effect_ms_per_normal_evaluation": {
                clock:{part:1000*statistics.median(r[clock][part] for r in fixture["paired_trace_effects"])/n
                       for part in ("step_trace_delta_s", "call_trace_delta_s", "all_trace_delta_s")}
                for clock in ("wall_s", "cpu_s")}})
    result = {"schema":"nsgablack.cost_ladder_summary/v1", "manifest":str(manifest_path.resolve()),
        "artifact_ref":manifest["cases"][0]["artifact_refs"]["report"], "fixtures":summary,
        "limits":["two seeds, signed paired differences; not confidence intervals",
            "lean retains small phase timers/counters and all normal evidence/transactions/control",
            "remainder includes algorithm operations and runtime, not exclusively framework code",
            "CPU injected work and simulated I/O wait are separate; actual cost can differ from target",
            "production is original 682-variable domain with matched NSGA-II, not complete nested supply optimization"]}
    destination.mkdir(parents=True,exist_ok=True)
    (destination/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines = ["# 不同评估成本、trace 与原排程模型对照", "",
        "全部数字只取初始化之后的正常提交；下面是两个种子的中位数。trace 差值保留符号，负值视为噪声而非加速结论。", ""]
    for row in summary:
        lean, full = row["modes"]["lean"]["wall_s"], row["modes"]["full"]["wall_s"]
        delta = row["trace_effect_ms_per_normal_evaluation"]["wall_s"]
        lines.extend([f"## {row['name']}", "",
            f"- 实测 Problem：{lean['actual_problem_ms']:.3f} ms/次；repair：{lean['actual_repair_ms']:.3f} ms/次。",
            f"- lean 正常迭代：框架 {lean['framework_s']:.4f} s，裸路径 {lean['reference_s']:.4f} s；比值 {lean['ratio']:.2f}。",
            f"- lean 额外耗时 {lean['extra_ms_per_evaluation']:.3f} ms/次；扣除双方评估与 repair 差异后，剩余差值 {lean['extra_nonproblem_nonrepair_ms']:.3f} ms/次。",
            f"- full 额外耗时 {full['extra_ms_per_evaluation']:.3f} ms/次；trace 合计差值 {delta['all_trace_delta_s']:.3f} ms/次（逐步记录 {delta['step_trace_delta_s']:.3f}，调用记录 {delta['call_trace_delta_s']:.3f}）。", ""])
        lines.extend([f"- 扣除各次评估与 repair 实测波动后的 full−lean 差值：{row['normalized_trace_effect_ms_per_evaluation']['wall_s']['median']:.3f} ms/次，原始样本 {row['normalized_trace_effect_ms_per_evaluation']['wall_s']['samples']}。",
            f"- full 的逐步观察回调自身计时：{row['modes']['full']['step_callback_self_ms_per_evaluation_all_commits']:.4f} ms/次（含 bootstrap 的全程均摊，不含逐次调用记录）。", ""])
    lines.extend(["## 语义与边界", "",
        "每个 fixture 先通过完整逐步/逐次调用对照与正式 checkpoint 恢复；计时的三种模式均核对最终状态、实际评估数与提交数，开启调用 trace 时还核对完整调用序列。关闭的只有验收用观察，不关闭 Pool、身份、事务、证据、预算或父 Case 取消检查。",
        "", "排程读取原 BOM/SUPPLY，禁止合成 fallback，不修改今天库存或任何到料日期。具体源文件与数据摘要保存在 summary.json。此实验比较同一 NSGA-II 在原 Problem/供料修复下的两条路径，不代表原多算法/外层供应调整方案的完整性能或求解质量。",
        "", "只用两种子诊断，full−lean 既受观察成本影响，也受 GC/缓存/系统调度影响。直接回调自身计时仅覆盖逐步观察；调用记录用受控开关差值估计。负差值和跨样本变号表示尚未分辨出稳定的微小 trace 成本，不能声称 trace 加速，也不能将全部剩余时间归因于审计。不同规模要重新测量，不能与此前 population=30 的数字直接比较。",
        "", "复现：在仓库根目录执行 `.benchmark-venv/Scripts/python.exe examples/cases/algorithm_transparency/run_project.py --group costs`。", ""])
    (destination/"RESULTS_CN.md").write_text("\n".join(lines),encoding="utf-8")
    return result


def plot(summary_path, destination):
    """Optional static scientific figure; no dependency on a live browser."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data = json.loads(Path(summary_path).read_text(encoding="utf-8"))["fixtures"]
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    cpu = [r for r in data if r["name"].startswith("cpu_")]
    def x(row):
        t = row["modes"]["lean"]["wall_s"]
        return t["actual_problem_ms"] + t["actual_repair_ms"]
    axes[0].plot([x(r) for r in cpu], [r["modes"]["lean"]["wall_s"]["ratio"] for r in cpu],
                 "o-", label="CPU load", color="#305f8c")
    for r, marker in ((r, "s" if r["name"].startswith("wait") else "^") for r in data if r not in cpu):
        axes[0].scatter(x(r), r["modes"]["lean"]["wall_s"]["ratio"], marker=marker,
                        s=70, label="Production" if r["name"].startswith("production") else "Simulated I/O wait")
    axes[0].set(xscale="log", yscale="log", xlabel="Actual Problem + repair time (ms/evaluation)",
                ylabel="Framework / bare normal-iteration wall time", title="Cost ratio with validation traces disabled")
    axes[0].legend(fontsize=8)
    labels = [r["name"].replace("_", "\n") for r in data]
    axes[1].bar(labels, [r["modes"]["lean"]["wall_s"]["extra_nonproblem_nonrepair_ms"] for r in data],color="#305f8c")
    axes[1].set(ylabel="Extra time (ms/evaluation)", xlabel="Evaluation workload",
                title="Extra time after subtracting Problem and repair")
    for ax in axes:
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
    figure.suptitle("Normal iterations: 8 members, 7 measured commits, median of 2 seeds", fontsize=12)
    figure.text(.02,.015,"Source: sealed Project cost_ladder artifact, 2026-11-02. Remainder includes algorithm work and runtime; this is a small diagnostic.",fontsize=8)
    figure.tight_layout(rect=(0,.05,1,.94))
    figure.savefig(destination,dpi=160)
    plt.close(figure)
