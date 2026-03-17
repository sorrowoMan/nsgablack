"""
Fix catalog summaries to proper bilingual (CN/EN) without shell-encoding issues.
"""

from __future__ import annotations

import os
import re


def _fix_registry(path: str) -> None:
    text = open(path, "rb").read().decode("utf-8", errors="replace")

    summaries = {
        "solver.nsga2": (
            "NSGA-II 标准底座求解器，稳定可用，建议用 suite/plugin/adapters 装配能力。",
            "Stable NSGA-II base solver; wire capabilities via suites/plugins/adapters.",
        ),
        "solver.blank": (
            "最小求解器底座，仅提供契约与生命周期，适合完全自定义流程。",
            "Minimal base solver providing contracts/lifecycle for custom workflows.",
        ),
        "solver.composable": (
            "可组合求解器，由 Adapter 驱动 propose/update，便于算法拆解与融合。",
            "Composable solver driven by Adapters (propose/update) for algorithm composition.",
        ),
        "adapter.vns": (
            "VNS 局部搜索内核，多邻域阶段式精修。",
            "VNS local search core with multi-neighborhood staged refinement.",
        ),
        "adapter.sa": (
            "模拟退火内核，温度调度 + Metropolis 接受准则。",
            "Simulated annealing core with temperature schedule and Metropolis acceptance.",
        ),
        "adapter.multi_strategy": (
            "多策略/多角色协同控制器，统一调度与共享状态/预算。",
            "Multi-strategy/role controller with unified scheduling and shared state/budgets.",
        ),
        "adapter.moead": (
            "MOEA/D 分解多目标内核，权重向量 + 邻域替换。",
            "MOEA/D decomposition core using weight vectors and neighborhood replacement.",
        ),
        "bias.tabu": (
            "禁忌搜索偏置，引入记忆/回避以引导搜索。",
            "Tabu-search bias using memory/avoidance to guide search.",
        ),
        "bias.robustness": (
            "鲁棒性偏置，利用 MC 统计惩罚不稳定解（需 MC 插件）。",
            "Robustness bias using MC statistics to penalize unstable solutions (requires MC plugin).",
        ),
        "plugin.monte_carlo_eval": (
            "Monte Carlo 评估插件，重复采样并注入统计信号。",
            "Monte Carlo evaluation plugin; repeated sampling with stats injection.",
        ),
        "plugin.pareto_archive": (
            "Pareto 归档插件，维护非支配解并写回求解器。",
            "Pareto archive plugin maintaining non-dominated solutions and writing back.",
        ),
        "plugin.benchmark_harness": (
            "基准输出插件，逐代 CSV + summary JSON 统一口径。",
            "Benchmark harness outputting per-gen CSV and summary JSON.",
        ),
        "plugin.module_report": (
            "模块审计插件，输出模块清单与偏置贡献报告。",
            "Module report plugin for audit; exports module/bias reports.",
        ),
        "plugin.profiler": (
            "性能剖析插件，记录 wall time 与评估吞吐。",
            "Profiler plugin recording wall time and eval throughput.",
        ),
        "plugin.surrogate_eval": (
            "代理评估插件，用 surrogate 过滤候选以减少真实评估。",
            "Surrogate evaluation plugin to reduce real evaluations.",
        ),
        "repr.context_gaussian": (
            "上下文高斯变异，依据 context 调整扰动尺度。",
            "Context Gaussian mutation; adjusts sigma via context.",
        ),
        "repr.context_switch": (
            "上下文切换变异器，在不同策略/子空间间切换算子。",
            "Context switch mutator for switching operators across strategies/spaces.",
        ),
        "suite.monte_carlo_robustness": (
            "权威装配：MC 评估 + 鲁棒偏置。",
            "Authority wiring: MC evaluation + robustness bias.",
        ),
        "suite.ray_parallel": (
            "权威装配：Ray 分布式评估后端。",
            "Authority wiring: Ray-based distributed evaluation backend.",
        ),
        "suite.moead": (
            "权威装配：MOEADAdapter + ParetoArchive。",
            "Authority wiring: MOEADAdapter + ParetoArchive.",
        ),
        "suite.sa": (
            "权威装配：SA 适配器 + 推荐算子。",
            "Authority wiring: SA adapter + recommended operators.",
        ),
        "suite.vns": (
            "权威装配：VNS 适配器 + 上下文变异算子。",
            "Authority wiring: VNS adapter + context mutators.",
        ),
        "suite.multi_strategy": (
            "权威装配：多策略协同控制器（角色/预算/共享状态）。",
            "Authority wiring: multi-strategy cooperation (roles/budgets/shared state).",
        ),
        "suite.benchmark_harness": (
            "权威装配：BenchmarkHarness 统一输出口径。",
            "Authority wiring: BenchmarkHarness output protocol.",
        ),
        "suite.module_report": (
            "权威装配：ModuleReport 审计与消融报告。",
            "Authority wiring: ModuleReport audit/ablation.",
        ),
        "suite.nsga2_engineering": (
            "权威装配：NSGA-II 工程插件组合（精英/监控/多样性）。",
            "Authority wiring: engineering plugin bundle for NSGA-II.",
        ),
        "bias.sa": (
            "模拟退火偏置，温度与接受准则引导探索。",
            "Simulated annealing bias guiding exploration.",
        ),
        "bias.de": (
            "差分进化偏置，差分扰动增强连续搜索。",
            "Differential evolution bias with differential perturbations.",
        ),
        "bias.pso": (
            "粒子群偏置，速度/惯性/群体引导。",
            "Particle swarm bias with velocity/inertia/social guidance.",
        ),
        "bias.cmaes": (
            "CMA-ES 偏置，协方差自适应提升方向性。",
            "CMA-ES bias with covariance adaptation.",
        ),
        "bias.levy": (
            "Levy flight 偏置，重尾步长增强探索。",
            "Levy flight bias with heavy-tailed steps.",
        ),
        "bias.pattern_search": (
            "模式搜索偏置，结构化无导数局部探测。",
            "Pattern search bias for structured derivative-free probing.",
        ),
        "bias.gradient_descent": (
            "梯度下降偏置，在可导/近似可导场景提供方向性。",
            "Gradient-descent bias for (approx.) differentiable settings.",
        ),
        "bias.convergence": (
            "收敛偏置，后期加强 exploitation。",
            "Convergence bias to increase late-stage exploitation.",
        ),
        "bias.diversity": (
            "多样性偏置，增强覆盖与分散。",
            "Diversity bias to increase spread/coverage.",
        ),
        "bias.nsga2_core": (
            "NSGA-II 核心信号偏置（非支配排序 + 拥挤度）。",
            "NSGA-II core bias (non-dominated sorting + crowding).",
        ),
        "bias.nsga3_core": (
            "NSGA-III 参考点偏置，用于 many-objective 覆盖。",
            "NSGA-III reference-point bias for many-objective coverage.",
        ),
        "bias.spea2_core": (
            "SPEA2 strength 偏置，强度/密度信号驱动选择。",
            "SPEA2 strength bias using strength/density signals.",
        ),
        "bias.moead_decomposition": (
            "MOEA/D 分解偏置，按权重/子问题提供选择信号。",
            "MOEA/D decomposition bias providing selection signals.",
        ),
        "plugin.elite": (
            "精英保留插件，提高稳定性与收敛可靠性。",
            "Elite retention plugin for stability and convergence.",
        ),
        "plugin.diversity_init": (
            "多样性初始化插件，提高初始覆盖。",
            "Diversity initialization plugin to improve initial coverage.",
        ),
        "plugin.memory": (
            "内存优化插件，对象复用降低开销。",
            "Memory optimization plugin with object reuse.",
        ),
        "repr.pipeline": (
            "表示管线入口：初始化/变异/修复三段式。",
            "Representation pipeline entry: init/mutate/repair.",
        ),
        "repr.continuous": (
            "连续变量初始化入口（UniformInitializer）。",
            "Continuous initializer (UniformInitializer).",
        ),
        "repr.integer": (
            "整数变量初始化入口（IntegerInitializer）。",
            "Integer initializer.",
        ),
        "repr.permutation": (
            "排列变量初始化入口（PermutationInitializer）。",
            "Permutation initializer.",
        ),
        "repr.binary": (
            "二进制初始化入口（BinaryInitializer）。",
            "Binary initializer.",
        ),
        "repr.graph": (
            "图结构初始化入口（GraphEdgeInitializer）。",
            "Graph edge initializer.",
        ),
        "repr.matrix": (
            "矩阵/网格初始化入口（IntegerMatrixInitializer）。",
            "Matrix/grid initializer.",
        ),
        "tool.parallel_evaluator": (
            "并行评估工具，支持 process/thread/joblib/ray。",
            "Parallel evaluator supporting process/thread/joblib/ray.",
        ),
        "tool.context_keys": (
            "上下文键名常量集合。",
            "Canonical context key set.",
        ),
        "tool.context_schema": (
            "最小评估上下文 schema（可序列化）。",
            "Minimal evaluation context schema (serializable).",
        ),
        "tool.logging": (
            "日志配置工具（支持 JSON）。",
            "Logging configuration helper (JSON supported).",
        ),
        "tool.metrics": (
            "分析指标工具：Pareto/超体积/IGD 等。",
            "Analysis metrics: Pareto/hypervolume/IGD etc.",
        ),
    }

    lines = text.splitlines()
    current_key = None
    out_lines = []
    key_re = re.compile(r'\\s*key=\"([^\"]+)\"')
    summary_re = re.compile(r'(\\s*summary=\")([^\"]*)(\".*)')

    for line in lines:
        m = key_re.search(line)
        if m:
            current_key = m.group(1)
        sm = summary_re.search(line)
        if sm and current_key in summaries:
            cn, en = summaries[current_key]
            new_summary = f"{cn} / {en}"
            line = f"{sm.group(1)}{new_summary}{sm.group(3)}"
        out_lines.append(line)

    open(path, "wb").write("\n".join(out_lines).encode("utf-8"))


def _fix_entries(path: str) -> None:
    text = open(path, "rb").read().decode("utf-8", errors="replace")

    cn_map = {
        "representation.parallel_repair": "并行修复包装器：为 repair_batch 提供线程/进程并行。",
        "adapter.role": "角色适配器：给策略附加角色元数据与候选限额。",
        "adapter.multi_role_controller": "多角色控制器：统一调度多个角色适配器并共享上下文。",
        "adapter.composite": "组合适配器：合并多个适配器候选输出。",
        "adapter.astar": "A* 适配器：自定义邻居/启发式/目标，走主管线评估。",
        "adapter.moa_star": "多目标 A* 适配器：状态级 Pareto 标签与支配剪枝。",
        "plugin.dynamic_switch": "动态切换插件基类：软/硬切换回调与阶段记录。",
        "suite.dynamic_switch": "动态切换装配：挂载动态切换插件。",
        "tool.dynamic_cli_signal": "命令行信号输入器：JSON 或 key=value。",

        "bias.diversity_adaptive": "自适应多样性偏置：动态调整分散权重。",
        "bias.diversity_niche": "小生境多样性偏置：鼓励解群分化。",
        "bias.diversity_crowding": "拥挤距离多样性偏置：保持覆盖。",
        "bias.diversity_sharing": "共享函数多样性偏置：降低相似解权重。",
        "bias.convergence_adaptive": "自适应收敛偏置：随阶段增强 exploitation。",
        "bias.convergence_precision": "精度导向收敛偏置：强调精细搜索。",
        "bias.convergence_late_stage": "后期收敛偏置：末段强化收敛。",
        "bias.convergence_multi_stage": "多阶段收敛偏置：分阶段调节收敛强度。",
        "bias.sa_adaptive": "自适应模拟退火偏置：温度/接受率自调。",
        "bias.sa_multiobjective": "多目标模拟退火偏置：面向多目标退火。",
        "bias.nsga2_adaptive": "自适应 NSGA-II 偏置：动态调整排序/拥挤信号。",
        "bias.nsga2_diversity_preserving": "NSGA-II 多样性保持偏置。",
        "bias.de_adaptive": "自适应差分进化偏置：参数随进度调整。",
        "bias.de_multiobjective": "多目标差分进化偏置。",
        "bias.pattern_search_adaptive": "自适应模式搜索偏置：步长/方向自调。",
        "bias.coordinate_descent": "坐标下降偏置：逐坐标微调。",
        "bias.gd_momentum": "动量梯度下降偏置。",
        "bias.gd_adaptive": "自适应梯度下降偏置。",
        "bias.gd_adam": "Adam 风格梯度偏置。",
        "bias.pso_adaptive": "自适应粒子群偏置。",
        "bias.cmaes_adaptive": "自适应 CMA-ES 偏置。",
        "bias.moead_adaptive": "自适应 MOEA/D 偏置。",
        "bias.nsga3_adaptive": "自适应 NSGA-III 偏置。",
        "bias.spea2_adaptive": "自适应 SPEA2 偏置。",
        "bias.spea2_hybrid": "SPEA2-NSGA2 混合偏置。",

        "bias.constraint": "约束偏置：对违背约束的解加惩罚。",
        "bias.feasibility": "可行性偏置：优先可行解。",
        "bias.preference": "偏好偏置：注入业务偏好规则。",
        "bias.rule_based": "规则驱动偏置：以规则函数计算惩罚/奖励。",
        "bias.callable": "函数式偏置：用可调用对象快速定义规则。",
        "bias.engineering_design": "工程设计偏置：面向设计指标的规则。",
        "bias.safety": "安全偏置：强调安全约束/风险惩罚。",
        "bias.manufacturing": "制造工艺偏置：考虑工艺可制造性。",
        "bias.scheduling": "调度偏置：面向排产/调度规则。",
        "bias.resource_constraint": "资源约束偏置：资源占用限制。",
        "bias.time_window": "时间窗偏置：满足时间窗约束。",

        "bias.bayesian_guidance": "贝叶斯引导偏置：EI/PI/UCB 等引导信号。",
        "bias.bayesian_exploration": "贝叶斯探索偏置：不确定性驱动探索。",
        "bias.bayesian_convergence": "贝叶斯收敛偏置：利用后验收敛引导。",

        "bias.engineering_precision": "工程精度偏置：强调精度/公差。",
        "bias.engineering_constraint": "工程约束偏置：复杂工程约束惩罚。",
        "bias.engineering_robustness": "工程鲁棒偏置：抗扰动与稳健性。",

        "bias.local_gd": "局部搜索偏置：梯度下降。",
        "bias.local_newton": "局部搜索偏置：牛顿法。",
        "bias.local_line_search": "局部搜索偏置：线搜索。",
        "bias.local_trust_region": "局部搜索偏置：信赖域。",
        "bias.local_nelder_mead": "局部搜索偏置：Nelder-Mead 单纯形。",
        "bias.local_quasi_newton": "局部搜索偏置：拟牛顿。",

        "bias.graph_connectivity": "图连通性偏置。",
        "bias.graph_sparsity": "图稀疏性偏置。",
        "bias.graph_degree_distribution": "图度分布偏置。",
        "bias.graph_shortest_path": "图最短路径偏置。",
        "bias.graph_max_flow": "图最大流偏置。",
        "bias.graph_coloring": "图着色偏置。",
        "bias.graph_community": "图社区发现偏置。",
        "bias.graph_constraint": "图约束偏置基类。",
        "bias.graph_tsp_constraint": "图 TSP 约束偏置。",
        "bias.graph_path_constraint": "图路径约束偏置。",
        "bias.graph_tree_constraint": "图树结构约束偏置。",
        "bias.graph_coloring_constraint": "图着色约束偏置。",
        "bias.graph_matching_constraint": "图匹配约束偏置。",
        "bias.graph_hamiltonian_constraint": "图哈密顿路径约束偏置。",
        "bias.graph_composite_constraint": "图复合约束偏置。",

        "bias.surrogate_control": "代理控制偏置：控制代理/真实评估比例。",
        "bias.surrogate_phase_schedule": "代理分阶段调度偏置。",
        "bias.surrogate_uncertainty_budget": "代理不确定性预算偏置。",

        "bias.production_constraint": "生产约束偏置。",
        "bias.production_diversity": "生产多样性偏置。",
        "bias.production_continuity": "生产连续性偏置。",
        "bias.production_scheduling": "生产调度偏置。",
    }

    lines = text.splitlines()
    cur_key = None
    out_lines = []
    for line in lines:
        if line.strip().startswith("key ="):
            cur_key = line.split("=", 1)[1].strip().strip("\"")
        if line.strip().startswith("summary =") and cur_key:
            summary = line.split("=", 1)[1].strip().strip("\"")
            parts = summary.split(" / ", 1)
            en = parts[-1]
            cn = cn_map.get(cur_key, "")
            if cn:
                line = f'summary = \"{cn} / {en}\"'
        out_lines.append(line)

    open(path, "wb").write("\n".join(out_lines).encode("utf-8"))


def main() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    reg_path = os.path.join(root, "catalog", "registry.py")
    toml_path = os.path.join(root, "catalog", "entries.toml")
    _fix_registry(reg_path)
    _fix_entries(toml_path)


if __name__ == "__main__":
    main()
