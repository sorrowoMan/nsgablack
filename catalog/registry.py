from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
import importlib
import os
from pathlib import Path
import pkgutil
import re


@dataclass(frozen=True)
class CatalogEntry:
    """A discoverability record for one framework component."""

    key: str
    title: str
    kind: str  # "bias" | "adapter" | "plugin" | "representation" | "suite" | "tool"
    import_path: str  # "pkg.mod:Symbol"
    tags: Tuple[str, ...] = ()
    summary: str = ""
    companions: Tuple[str, ...] = ()  # entry keys (soft links)

    def load(self):
        """Import and return the referenced symbol."""
        mod_path, _, sym = self.import_path.partition(":")
        if not mod_path or not sym:
            raise ValueError(f"Invalid import_path: {self.import_path!r}")
        mod = importlib.import_module(mod_path)
        return getattr(mod, sym)


class Catalog:
    def __init__(self, entries: Sequence[CatalogEntry]):
        self._entries = list(entries)
        self._by_key: Dict[str, CatalogEntry] = {e.key: e for e in self._entries}

    def get(self, key: str) -> Optional[CatalogEntry]:
        return self._by_key.get(key)

    def list(self, *, kind: Optional[str] = None, tag: Optional[str] = None) -> List[CatalogEntry]:
        out = list(self._entries)
        if kind is not None:
            k = str(kind).lower().strip()
            out = [e for e in out if e.kind == k]
        if tag is not None:
            t = str(tag).lower().strip()
            out = [e for e in out if t in (x.lower() for x in e.tags)]
        return out

    def search(
        self,
        query: str,
        *,
        kinds: Optional[Sequence[str]] = None,
        tags: Optional[Sequence[str]] = None,
        limit: int = 20,
    ) -> List[CatalogEntry]:
        q_raw = str(query).strip().lower()
        if not q_raw:
            return []
        tokens = [t for t in re.split(r"\s+", q_raw) if t]
        kind_set = {str(k).lower().strip() for k in (kinds or [])}
        tag_set = {str(t).lower().strip() for t in (tags or [])}

        def match(e: CatalogEntry) -> bool:
            if kind_set and e.kind not in kind_set:
                return False
            if tag_set:
                e_tags = {t.lower() for t in e.tags}
                if not tag_set.issubset(e_tags):
                    return False
            hay = " ".join([e.key, e.title, e.kind, e.summary, " ".join(e.tags)]).lower()
            return all(t in hay for t in tokens)

        out = [e for e in self._entries if match(e)]

        # UX: prefer "official recommended wiring" first.
        # Suites are the authoritative combinations and should surface before raw parts.
        def rank(e: CatalogEntry) -> Tuple[int, int, str]:
            is_suite = int(e.kind == "suite" or e.key.startswith("suite."))
            # smaller is better
            primary = 0 if is_suite else 1
            # keep stable-ish grouping by kind and key
            kind_order = {"suite": 0, "adapter": 1, "plugin": 2, "bias": 3, "representation": 4, "tool": 5}
            secondary = int(kind_order.get(e.kind, 99))
            return (primary, secondary, e.key)

        out.sort(key=rank)
        return out[: max(0, int(limit))]


def _default_entries() -> List[CatalogEntry]:
    # NOTE: keep this list small and "authoritative". Add entries only for modern components.
    return [
        # --- Solvers (bases) ---
        CatalogEntry(
            key="solver.nsga2",
            title="BlackBoxSolverNSGAII",
            kind="tool",
            import_path="nsgablack.core.solver:BlackBoxSolverNSGAII",
            tags=("solver", "nsga2", "evolutionary"),
            summary="可用的 NSGA-II 底座求解器（稳定底座，建议通过 suite/plugin/adapters 进行装配）。",
        ),
        CatalogEntry(
            key="solver.blank",
            title="BlankSolverBase",
            kind="tool",
            import_path="nsgablack.core.blank_solver:BlankSolverBase",
            tags=("solver", "blank", "base"),
            summary="最小底座：提供契约但不内置循环，适合完全自定义流程（配合 plugin/suite 装配）。",
        ),
        CatalogEntry(
            key="solver.composable",
            title="ComposableSolver",
            kind="tool",
            import_path="nsgablack.core.composable_solver:ComposableSolver",
            tags=("solver", "adapter", "composition"),
            summary="可组合求解器：由 Adapter 驱动 propose/update，适合算法解构与融合。",
        ),
        # --- Adapters ---
        CatalogEntry(
            key="adapter.vns",
            title="VNSAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:VNSAdapter",
            tags=("local_search", "vns", "stage", "refinement"),
            summary="VNS 局部搜索策略内核：多邻域/阶段式 refinement，适合在主循环后做精修。",
            companions=("repr.context_gaussian", "repr.context_switch", "suite.vns"),
        ),
        CatalogEntry(
            key="adapter.sa",
            title="SimulatedAnnealingAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:SimulatedAnnealingAdapter",
            tags=("local_search", "sa", "simulated_annealing"),
            summary="模拟退火（SA）策略内核：Metropolis 接受准则 + 温度调度（可选结合 mutation_sigma）。",
            companions=("repr.context_gaussian", "suite.sa"),
        ),
        CatalogEntry(
            key="adapter.multi_strategy",
            title="MultiStrategyControllerAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:MultiStrategyControllerAdapter",
            tags=("cooperation", "parallel", "multi_strategy", "controller", "roles"),
            summary="多策略/多角色协作控制器：统一 propose/update 调度，支持共享状态与动态预算分配。",
            companions=("suite.multi_strategy", "plugin.pareto_archive"),
        ),
        CatalogEntry(
            key="adapter.moead",
            title="MOEADAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:MOEADAdapter",
            tags=("multiobjective", "moead", "decomposition"),
            summary="MOEA/D 分解型多目标策略内核：权重向量 + 邻域替换，适合大规模多目标与可控分解。",
            companions=("plugin.pareto_archive", "suite.moead"),
        ),
        # --- Biases (algorithmic) ---
        CatalogEntry(
            key="bias.tabu",
            title="TabuSearchBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.tabu_search:TabuSearchBias",
            tags=("tabu", "memory", "bias", "strategy"),
            summary="禁忌搜索思想的偏置模块：通过记忆/回避机制引导搜索，适合注入任意底座。",
        ),
        CatalogEntry(
            key="bias.robustness",
            title="RobustnessBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.signal_driven.robustness:RobustnessBias",
            tags=("robustness", "signal_driven", "mc"),
            summary="信号驱动偏置：消费 mc_std 等统计惩罚不稳定解（需 MonteCarloEvaluationPlugin 注入信号）。",
            companions=("plugin.monte_carlo_eval", "suite.monte_carlo_robustness"),
        ),
        # --- Plugins ---
        CatalogEntry(
            key="plugin.monte_carlo_eval",
            title="MonteCarloEvaluationPlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:MonteCarloEvaluationPlugin",
            tags=("mc", "evaluation", "signal"),
            summary="能力层：重复评估并聚合，向 context.metrics 注入 mc_mean/mc_std 等统计。",
            companions=("bias.robustness", "suite.monte_carlo_robustness"),
        ),
        CatalogEntry(
            key="plugin.pareto_archive",
            title="ParetoArchivePlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:ParetoArchivePlugin",
            tags=("archive", "pareto", "multiobjective"),
            summary="能力层：维护非支配解 archive，并写回 solver.pareto_objectives/pareto_solutions。",
            companions=("adapter.moead", "suite.moead"),
        ),
        CatalogEntry(
            key="plugin.benchmark_harness",
            title="BenchmarkHarnessPlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:BenchmarkHarnessPlugin",
            tags=("benchmark", "logging", "protocol", "comparison"),
            summary="实验口径插件：输出逐代 CSV + summary JSON（seed/time/eval_count/best_score）。",
            companions=("suite.benchmark_harness",),
        ),
        CatalogEntry(
            key="plugin.module_report",
            title="ModuleReportPlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:ModuleReportPlugin",
            tags=("report", "bias", "ablation", "audit"),
            summary="模块清单 + 偏置贡献报告：输出 modules.json + bias.json（可选 bias.md），用于审计/消融。",
            companions=("suite.module_report", "plugin.benchmark_harness"),
        ),
        CatalogEntry(
            key="plugin.profiler",
            title="ProfilerPlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:ProfilerPlugin",
            tags=("profile", "performance", "throughput", "audit"),
            summary="性能剖析插件：按代记录 wall time + eval 吞吐，并输出 profile.json（便于批量汇总/对比）。",
            companions=("plugin.benchmark_harness", "plugin.module_report"),
        ),
        CatalogEntry(
            key="plugin.surrogate_eval",
            title="SurrogateEvaluationPlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:SurrogateEvaluationPlugin",
            tags=("surrogate", "evaluation", "optional"),
            summary="可选能力层：用 surrogate 筛选候选以减少真实评估次数（不属于核心路径承诺）。",
        ),
        # --- Representation helpers ---
        CatalogEntry(
            key="repr.context_gaussian",
            title="ContextGaussianMutation",
            kind="representation",
            import_path="nsgablack.representation.continuous:ContextGaussianMutation",
            tags=("continuous", "context", "mutation", "vns"),
            summary="上下文驱动的 Gaussian mutation：可从 context 读取尺度/阶段信息，常用于 VNS/分阶段搜索。",
            companions=("adapter.vns",),
        ),
        CatalogEntry(
            key="repr.context_switch",
            title="ContextSwitchMutator",
            kind="representation",
            import_path="nsgablack.representation:ContextSwitchMutator",
            tags=("context", "mutation", "switch", "vns", "discrete"),
            summary="上下文切换变异器：在不同子空间/策略间切换，用于 VNS/多策略协作。",
            companions=("adapter.vns",),
        ),
        # --- Suites (authority wiring) ---
        CatalogEntry(
            key="suite.monte_carlo_robustness",
            title="attach_monte_carlo_robustness",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_monte_carlo_robustness",
            tags=("suite", "mc", "robustness"),
            summary="权威装配：挂载 MonteCarloEvaluationPlugin + RobustnessBias，形成鲁棒性优化口径。",
            companions=("plugin.monte_carlo_eval", "bias.robustness"),
        ),
        CatalogEntry(
            key="suite.ray_parallel",
            title="attach_ray_parallel",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_ray_parallel",
            tags=("suite", "ray", "distributed", "parallel"),
            summary="权威装配：启用 Ray 分布式评估后端（建议提供 problem_factory）。",
            companions=("plugin.profiler", "plugin.benchmark_harness"),
        ),
        CatalogEntry(
            key="suite.moead",
            title="attach_moead",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_moead",
            tags=("suite", "moead", "multiobjective"),
            summary="权威装配：挂载 MOEADAdapter + ParetoArchivePlugin（分解多目标主路径）。",
            companions=("adapter.moead", "plugin.pareto_archive"),
        ),
        CatalogEntry(
            key="suite.sa",
            title="attach_simulated_annealing",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_simulated_annealing",
            tags=("suite", "sa", "simulated_annealing"),
            summary="权威装配：挂载 SimulatedAnnealingAdapter + 推荐表征算子，形成可运行的 SA 精修路径。",
            companions=("adapter.sa", "repr.context_gaussian"),
        ),
        CatalogEntry(
            key="suite.vns",
            title="attach_vns",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_vns",
            tags=("suite", "vns", "local_search"),
            summary="权威装配：挂载 VNSAdapter + 上下文变异算子，形成分阶段局部搜索精修路径。",
            companions=("adapter.vns", "repr.context_gaussian", "repr.context_switch"),
        ),
        CatalogEntry(
            key="suite.multi_strategy",
            title="attach_multi_strategy_coop",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_multi_strategy_coop",
            tags=("suite", "cooperation", "multi_strategy", "parallel"),
            summary="权威装配：挂载多策略协作控制器（roles/预算/共享状态），用于多智能体式协同搜索。",
            companions=("adapter.multi_strategy", "plugin.pareto_archive"),
        ),
        CatalogEntry(
            key="suite.benchmark_harness",
            title="attach_benchmark_harness",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_benchmark_harness",
            tags=("suite", "benchmark", "protocol", "comparison"),
            summary="权威装配：挂载 BenchmarkHarnessPlugin（逐代 CSV + summary JSON），统一实验口径。",
            companions=("plugin.benchmark_harness",),
        ),
        CatalogEntry(
            key="suite.module_report",
            title="attach_module_report",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_module_report",
            tags=("suite", "report", "ablation", "audit"),
            summary="权威装配：挂载 ModuleReportPlugin（modules/bias 报告），用于审计/消融与复现记录。",
            companions=("plugin.module_report", "plugin.benchmark_harness"),
        ),
        CatalogEntry(
            key="suite.nsga2_engineering",
            title="attach_nsga2_engineering",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_nsga2_engineering",
            tags=("suite", "nsga2", "engineering", "plugins"),
            summary="权威装配：给 NSGA-II 挂一组保守的工程插件（elite/监控/多样性等），保持 core 纯净。",
            companions=("plugin.elite", "plugin.convergence_monitor", "plugin.diversity_init", "plugin.benchmark_harness"),
        ),

        # --- Biases (more algorithmic building blocks; kept as "main class per module") ---
        CatalogEntry(
            key="bias.sa",
            title="SimulatedAnnealingBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.simulated_annealing:SimulatedAnnealingBias",
            tags=("sa", "simulated_annealing", "local_search", "strategy"),
            summary="模拟退火思想的偏置模块：温度调度 + 接受准则，用于引导探索/跳出局部最优。",
        ),
        CatalogEntry(
            key="bias.de",
            title="DifferentialEvolutionBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.differential_evolution:DifferentialEvolutionBias",
            tags=("de", "differential_evolution", "mutation", "strategy"),
            summary="差分进化思想的偏置模块：基于差分向量的变异/扰动，用于增强连续空间搜索能力。",
        ),
        CatalogEntry(
            key="bias.pso",
            title="ParticleSwarmBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.pso:ParticleSwarmBias",
            tags=("pso", "particle_swarm", "swarm", "strategy"),
            summary="粒子群思想的偏置模块：速度/惯性/群体引导，适合连续变量的群体式搜索。",
        ),
        CatalogEntry(
            key="bias.cmaes",
            title="CMAESBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.cma_es:CMAESBias",
            tags=("cmaes", "cma-es", "covariance", "strategy"),
            summary="CMA-ES 思想的偏置模块：协方差自适应（黑箱连续优化常用），用于提升搜索方向性。",
        ),
        CatalogEntry(
            key="bias.levy",
            title="LevyFlightBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.levy_flight:LevyFlightBias",
            tags=("levy", "random_walk", "exploration"),
            summary="Levy flight 探索偏置：重尾随机步长，增强全局探索与跳跃能力。",
        ),
        CatalogEntry(
            key="bias.pattern_search",
            title="PatternSearchBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.pattern_search:PatternSearchBias",
            tags=("pattern_search", "local_search", "derivative_free"),
            summary="Pattern Search 无导数局部搜索偏置：结构化探测方向，适合约束/不可导场景。",
        ),
        CatalogEntry(
            key="bias.gradient_descent",
            title="GradientDescentBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.gradient_descent:GradientDescentBias",
            tags=("gd", "gradient_descent", "continuous"),
            summary="梯度下降风格的偏置模块：在可导/近似可导场景提供方向性引导（工程上常与 surrogate/估计结合）。",
        ),
        CatalogEntry(
            key="bias.convergence",
            title="ConvergenceBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.convergence:ConvergenceBias",
            tags=("convergence", "exploitation", "schedule"),
            summary="收敛偏置：在后期提高 exploitation 权重/降低噪声，引导解向稳定区域收敛。",
        ),
        CatalogEntry(
            key="bias.diversity",
            title="DiversityBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.diversity:DiversityBias",
            tags=("diversity", "exploration", "niching"),
            summary="多样性偏置：鼓励分散/覆盖，避免早熟收敛（niching/crowding 等思想的抽象）。",
        ),
        CatalogEntry(
            key="bias.nsga2_core",
            title="NSGA2Bias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.nsga2:NSGA2Bias",
            tags=("nsga2", "multiobjective", "crowding"),
            summary="NSGA-II 核心思想偏置：非支配排序 + 拥挤度等信号，作为可组合模块对外暴露。",
        ),
        CatalogEntry(
            key="bias.nsga3_core",
            title="NSGA3ReferencePointBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.nsga3:NSGA3ReferencePointBias",
            tags=("nsga3", "reference_point", "multiobjective"),
            summary="NSGA-III 参考点/参考方向思想偏置：用于 many-objective 的覆盖控制。",
        ),
        CatalogEntry(
            key="bias.spea2_core",
            title="SPEA2StrengthBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.spea2:SPEA2StrengthBias",
            tags=("spea2", "strength", "multiobjective"),
            summary="SPEA2 strength 思想偏置：用强度/密度信号驱动选择与保留。",
        ),
        CatalogEntry(
            key="bias.moead_decomposition",
            title="MOEADDecompositionBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.moead:MOEADDecompositionBias",
            tags=("moead", "decomposition", "multiobjective"),
            summary="MOEA/D 分解信号偏置：按权重/子问题分解提供选择与比较信号，可与 MOEADAdapter 配合。",
        ),

        # --- Plugins (more capabilities) ---
        CatalogEntry(
            key="plugin.adaptive_parameters",
            title="AdaptiveParametersPlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:AdaptiveParametersPlugin",
            tags=("plugin", "adaptive", "parameters"),
            summary="能力层：根据进度/信号自适应调整参数（如 mutation/crossover 等），降低手工调参压力。",
        ),
        CatalogEntry(
            key="plugin.elite",
            title="BasicElitePlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:BasicElitePlugin",
            tags=("plugin", "elite", "archive"),
            summary="能力层：精英保留插件（保留比例/概率可调），提升稳定性与收敛可靠性。",
        ),
        CatalogEntry(
            key="plugin.convergence_monitor",
            title="ConvergencePlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:ConvergencePlugin",
            tags=("plugin", "monitor", "convergence"),
            summary="能力层：收敛监控插件（可选 early-stop），用于记录/判断收敛而不改核心生命周期。",
        ),
        CatalogEntry(
            key="plugin.diversity_init",
            title="DiversityInitPlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:DiversityInitPlugin",
            tags=("plugin", "init", "diversity"),
            summary="能力层：多样性初始化/扰动插件，提升初始覆盖与探索性（工程默认保守开启）。",
        ),
        CatalogEntry(
            key="plugin.memory",
            title="MemoryPlugin",
            kind="plugin",
            import_path="nsgablack.utils.plugins:MemoryPlugin",
            tags=("plugin", "memory", "engineering"),
            summary="能力层：内存/对象复用优化插件（工程用），逻辑上不改变算法结果。",
        ),

        # --- Representation (core presets) ---
        CatalogEntry(
            key="repr.pipeline",
            title="RepresentationPipeline",
            kind="representation",
            import_path="nsgablack.representation:RepresentationPipeline",
            tags=("pipeline", "representation", "core"),
            summary="表示管线总入口：initializer/mutator/repair 三段式，可被 solver/adapter/plugin 统一调用。",
        ),
        CatalogEntry(
            key="repr.continuous",
            title="UniformInitializer",
            kind="representation",
            import_path="nsgablack.representation.continuous:UniformInitializer",
            tags=("continuous", "real", "initializer"),
            summary="连续变量常用入口：UniformInitializer（配套 GaussianMutation/ClipRepair 等算子）。",
        ),
        CatalogEntry(
            key="repr.integer",
            title="IntegerInitializer",
            kind="representation",
            import_path="nsgablack.representation.integer:IntegerInitializer",
            tags=("integer", "discrete", "initializer"),
            summary="整数表示常用入口：IntegerInitializer（配套 IntegerMutation/IntegerRepair）。",
        ),
        CatalogEntry(
            key="repr.permutation",
            title="PermutationInitializer",
            kind="representation",
            import_path="nsgablack.representation.permutation:PermutationInitializer",
            tags=("permutation", "tsp", "discrete", "initializer"),
            summary="排列表示常用入口：PermutationInitializer（配套 swap/2-opt/repair 等算子）。",
        ),
        CatalogEntry(
            key="repr.binary",
            title="BinaryInitializer",
            kind="representation",
            import_path="nsgablack.representation.binary:BinaryInitializer",
            tags=("binary", "bit", "initializer"),
            summary="二进制表示常用入口：BinaryInitializer（配套 bit mutation/repair）。",
        ),
        CatalogEntry(
            key="repr.graph",
            title="GraphEdgeInitializer",
            kind="representation",
            import_path="nsgablack.representation.graph:GraphEdgeInitializer",
            tags=("graph", "network", "initializer"),
            summary="图结构表示入口：GraphEdgeInitializer（边集合/邻接结构初始化，配套图修复/约束）。",
        ),
        CatalogEntry(
            key="repr.matrix",
            title="IntegerMatrixInitializer",
            kind="representation",
            import_path="nsgablack.representation.matrix:IntegerMatrixInitializer",
            tags=("matrix", "grid", "initializer"),
            summary="矩阵/网格表示入口：IntegerMatrixInitializer（配套矩阵变异/修复）。",
        ),

        # --- Tools (utilities; discoverable but not part of the solver base) ---
        CatalogEntry(
            key="tool.parallel_evaluator",
            title="ParallelEvaluator",
            kind="tool",
            import_path="nsgablack.utils.parallel:ParallelEvaluator",
            tags=("parallel", "evaluation", "tool"),
            summary="并行评估工具：支持 process/thread/joblib/ray 后端，用于加速 problem.evaluate + constraints + bias。",
        ),
        CatalogEntry(
            key="tool.context_keys",
            title="Context Keys",
            kind="tool",
            import_path="nsgablack.utils.context:context_keys",
            tags=("context", "keys", "schema", "tool"),
            summary="Canonical context keys shared across adapters/plugins/biases (recommended import: `from nsgablack.utils.context import context_keys as CK`).",
        ),
        CatalogEntry(
            key="tool.context_schema",
            title="MinimalEvaluationContext",
            kind="tool",
            import_path="nsgablack.utils.context:MinimalEvaluationContext",
            tags=("context", "schema", "parallel", "tool"),
            summary="Minimal evaluation context schema (serializable) for parallel/engineering glue.",
            companions=("tool.context_keys",),
        ),
        CatalogEntry(
            key="tool.logging",
            title="configure_logging",
            kind="tool",
            import_path="nsgablack.utils.engineering:configure_logging",
            tags=("logging", "engineering", "tool"),
            summary="Logging configuration helper (JSON formatter supported).",
        ),
        CatalogEntry(
            key="tool.metrics",
            title="pareto_filter",
            kind="tool",
            import_path="nsgablack.utils.analysis:pareto_filter",
            tags=("metrics", "analysis", "pareto", "tool"),
            summary="Analysis helpers: Pareto filter / hypervolume / IGD / reference fronts (see `nsgablack.utils.analysis`).",
        ),
    ]


_CATALOG: Optional[Catalog] = None


def _load_entrypoint_entries() -> List[CatalogEntry]:
    """
    Load catalog entries from Python entrypoints (third-party extensions).

    Entry point group: `nsgablack.catalog`

    Each entry point should resolve to either:
    - a `CatalogEntry`
    - an iterable of `CatalogEntry`
    - a callable returning one of the above
    """
    try:
        from importlib.metadata import entry_points  # py>=3.10
    except Exception:  # pragma: no cover
        return []

    out: List[CatalogEntry] = []
    try:
        eps = entry_points(group="nsgablack.catalog")
    except Exception:  # pragma: no cover
        return []

    for ep in eps:
        try:
            obj = ep.load()
            if callable(obj):
                obj = obj()
            if isinstance(obj, CatalogEntry):
                out.append(obj)
            elif isinstance(obj, (list, tuple)):
                out.extend([x for x in obj if isinstance(x, CatalogEntry)])
        except Exception:
            continue
    return out


def _discover_python_entries() -> List[CatalogEntry]:
    """
    Auto-discover catalog entries from module-level `CATALOG_ENTRIES`.

    This avoids editing `catalog/registry.py` every time you add a new algorithm.
    Rule: put a `CATALOG_ENTRIES: list[CatalogEntry|dict]` in your module, and it
    will be picked up by catalog discovery.
    """
    flag = os.environ.get("NSGABLACK_CATALOG_DISCOVERY", "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return []

    def parse_items(items) -> List[CatalogEntry]:
        out: List[CatalogEntry] = []
        if not isinstance(items, (list, tuple)):
            return out
        for it in items:
            if isinstance(it, CatalogEntry):
                out.append(it)
                continue
            if isinstance(it, dict):
                try:
                    out.append(
                        CatalogEntry(
                            key=str(it.get("key", "")).strip(),
                            title=str(it.get("title", "")).strip(),
                            kind=str(it.get("kind", "")).strip().lower(),
                            import_path=str(it.get("import_path", "")).strip(),
                            tags=tuple(it.get("tags", []) or ()),
                            summary=str(it.get("summary", "")).strip(),
                            companions=tuple(it.get("companions", []) or ()),
                        )
                    )
                except Exception:
                    continue
        return [e for e in out if e.key and e.kind and e.import_path]

    packages = [
        "nsgablack.core.adapters",
        "nsgablack.bias",
        "nsgablack.representation",
        "nsgablack.utils.suites",
        "nsgablack.utils.plugins",
    ]

    out: List[CatalogEntry] = []
    for pkg_name in packages:
        try:
            pkg = importlib.import_module(pkg_name)
        except Exception:
            continue

        out.extend(parse_items(getattr(pkg, "CATALOG_ENTRIES", None)))

        pkg_path = getattr(pkg, "__path__", None)
        if not pkg_path:
            continue
        for modinfo in pkgutil.walk_packages(pkg_path, pkg.__name__ + "."):
            try:
                m = importlib.import_module(modinfo.name)
                out.extend(parse_items(getattr(m, "CATALOG_ENTRIES", None)))
            except Exception:
                continue
    return out


def _load_external_entries() -> List[CatalogEntry]:
    """
    Load user/project-defined catalog entries without touching source code.

    Supported sources (in order):
    - `catalog/entries.toml` (next to this file; recommended for repo-local extension)
    - `NSGABLACK_CATALOG_PATH` env var (os.pathsep-separated list of .toml files)

    TOML schema:

    [[entry]]
    key = "bias.my"
    title = "MyBias"
    kind = "bias"
    import_path = "nsgablack.bias.algorithmic.my:MyBias"
    tags = ["foo", "bar"]
    summary = "one line"
    companions = ["plugin.xxx", "suite.yyy"]
    """

    try:
        import tomllib  # py>=3.11
    except Exception:  # pragma: no cover
        tomllib = None

    def parse_file(path: Path) -> List[CatalogEntry]:
        if tomllib is None:
            return []
        if not path.exists():
            return []
        raw = path.read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
        items = data.get("entry", [])
        out: List[CatalogEntry] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            out.append(
                CatalogEntry(
                    key=str(item.get("key", "")).strip(),
                    title=str(item.get("title", "")).strip(),
                    kind=str(item.get("kind", "")).strip().lower(),
                    import_path=str(item.get("import_path", "")).strip(),
                    tags=tuple(item.get("tags", []) or ()),
                    summary=str(item.get("summary", "")).strip(),
                    companions=tuple(item.get("companions", []) or ()),
                )
            )
        return [e for e in out if e.key and e.kind and e.import_path]

    paths: List[Path] = []

    # repo-local extension: catalog/entries.toml
    paths.append(Path(__file__).with_name("entries.toml"))

    # env extension: NSGABLACK_CATALOG_PATH
    env = os.environ.get("NSGABLACK_CATALOG_PATH", "").strip()
    if env:
        for part in env.split(os.pathsep):
            p = part.strip().strip('"')
            if p:
                paths.append(Path(p))

    entries: List[CatalogEntry] = []
    for p in paths:
        try:
            entries.extend(parse_file(p))
        except Exception:
            # Catalog is discoverability layer; external files should never crash runtime.
            continue
    return entries


def get_catalog(*, refresh: bool = False) -> Catalog:
    global _CATALOG
    if refresh or _CATALOG is None:
        base = _default_entries()
        discovered = _discover_python_entries()
        extra = _load_external_entries()
        eps = _load_entrypoint_entries()

        # Let external entries override defaults by key (last write wins).
        merged: Dict[str, CatalogEntry] = {e.key: e for e in base}
        for e in discovered:
            merged[e.key] = e
        for e in extra:
            merged[e.key] = e
        for e in eps:
            merged[e.key] = e
        _CATALOG = Catalog(list(merged.values()))
    return _CATALOG
