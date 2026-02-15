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
    # Optional context contracts (component-level read/write semantics).
    context_requires: Tuple[str, ...] = ()
    context_provides: Tuple[str, ...] = ()
    context_mutates: Tuple[str, ...] = ()
    context_cache: Tuple[str, ...] = ()
    context_notes: Tuple[str, ...] = ()
    # Optional usage contracts (how to apply component without reading source).
    use_when: Tuple[str, ...] = ()
    minimal_wiring: Tuple[str, ...] = ()
    required_companions: Tuple[str, ...] = ()
    config_keys: Tuple[str, ...] = ()
    example_entry: str = ""

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
        self._context_blob_cache: Dict[str, str] = {}

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
        fields: str = "all",
        limit: int = 20,
    ) -> List[CatalogEntry]:
        q_raw = str(query).strip().lower()
        if not q_raw:
            return []
        tokens = [t for t in re.split(r"\s+", q_raw) if t]
        token_groups = _expand_token_groups(tokens)
        kind_set = {str(k).lower().strip() for k in (kinds or [])}
        tag_set = {str(t).lower().strip() for t in (tags or [])}
        field = (fields or "all").strip().lower()
        use_context_in_all = field == "all" and any(
            ("context" in t) or (t in {"requires", "provides", "mutates", "cache", "contract", "contracts"})
            for t in tokens
        )
        use_usage_in_all = field == "all" and any(
            (t in {"use", "usage", "wiring", "wire", "companion", "companions", "config", "example"})
            for t in tokens
        )

        def match(e: CatalogEntry) -> bool:
            if kind_set and e.kind not in kind_set:
                return False
            if tag_set:
                e_tags = {t.lower() for t in e.tags}
                if not tag_set.issubset(e_tags):
                    return False
            if field == "name":
                hay = " ".join([e.key, e.title]).lower()
            elif field == "tag":
                hay = " ".join(e.tags).lower()
            elif field == "context":
                hay = self._entry_context_blob(e)
            elif field == "usage":
                hay = self._entry_usage_blob(e)
            else:
                hay = " ".join([e.key, e.title, e.kind, e.summary, " ".join(e.tags)]).lower()
                if use_context_in_all:
                    hay = f"{hay} {self._entry_context_blob(e)}"
                if use_usage_in_all:
                    hay = f"{hay} {self._entry_usage_blob(e)}"
            return all(any(t in hay for t in group) for group in token_groups)

        out = [e for e in self._entries if match(e)]

        # UX: prefer "official recommended wiring" first.
        # Suites are the authoritative combinations and should surface before raw parts.
        def rank(e: CatalogEntry) -> Tuple[int, int, str]:
            is_suite = int(e.kind == "suite" or e.key.startswith("suite."))
            # smaller is better
            primary = 0 if is_suite else 1
            # keep stable-ish grouping by kind and key
            kind_order = {"suite": 0, "adapter": 1, "plugin": 2, "bias": 3, "representation": 4, "tool": 5, "example": 6}
            secondary = int(kind_order.get(e.kind, 99))
            return (primary, secondary, e.key)

        out.sort(key=rank)
        return out[: max(0, int(limit))]

    def _entry_context_blob(self, e: CatalogEntry) -> str:
        cached = self._context_blob_cache.get(e.key)
        if cached is not None:
            return cached

        parts: List[str] = []

        def add_field(label: str, values: object, *, include_label: bool) -> None:
            if include_label:
                parts.append(label)
            parts.extend(_coerce_str_tuple(values))

        add_field("context_requires", e.context_requires, include_label=bool(e.context_requires))
        add_field("context_provides", e.context_provides, include_label=bool(e.context_provides))
        add_field("context_mutates", e.context_mutates, include_label=bool(e.context_mutates))
        add_field("context_cache", e.context_cache, include_label=bool(e.context_cache))
        add_field("context_notes", e.context_notes, include_label=bool(e.context_notes))

        # If contracts are not attached on CatalogEntry, try reading class-level declarations.
        if not parts:
            try:
                symbol = e.load()
            except Exception:
                symbol = None
            if symbol is not None:
                add_field(
                    "context_requires",
                    getattr(symbol, "context_requires", ()),
                    include_label=hasattr(symbol, "context_requires"),
                )
                add_field(
                    "context_provides",
                    getattr(symbol, "context_provides", ()),
                    include_label=hasattr(symbol, "context_provides"),
                )
                add_field(
                    "context_mutates",
                    getattr(symbol, "context_mutates", ()),
                    include_label=hasattr(symbol, "context_mutates"),
                )
                add_field(
                    "context_cache",
                    getattr(symbol, "context_cache", ()),
                    include_label=hasattr(symbol, "context_cache"),
                )
                add_field(
                    "context_notes",
                    getattr(symbol, "context_notes", ()),
                    include_label=hasattr(symbol, "context_notes"),
                )

        blob = " ".join(parts).lower()
        self._context_blob_cache[e.key] = blob
        return blob

    def _entry_usage_blob(self, e: CatalogEntry) -> str:
        parts: List[str] = []
        parts.extend(_coerce_str_tuple(getattr(e, "use_when", ())))
        parts.extend(_coerce_str_tuple(getattr(e, "minimal_wiring", ())))
        parts.extend(_coerce_str_tuple(getattr(e, "required_companions", ())))
        parts.extend(_coerce_str_tuple(getattr(e, "config_keys", ())))
        parts.extend(_coerce_str_tuple(getattr(e, "example_entry", "")))
        if not parts:
            parts.extend(_coerce_str_tuple(getattr(e, "companions", ())))
        return " ".join(parts).lower()


def _coerce_str_tuple(value: object) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, dict):
        # Keep deterministic order on dict-like configs.
        return tuple(
            str(k).strip()
            for k in value.keys()
            if str(k).strip()
        )
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                out.append(text)
        return tuple(out)
    text = str(value).strip()
    return (text,) if text else ()


def _expand_token_groups(tokens: List[str]) -> List[List[str]]:
    """Expand search tokens with simple Chinese <-> English alias mapping."""
    alias_map = {
        "\u52a8\u6001": ['dynamic'],
        "\u5207\u6362": ['switch', 'dynamic_switch'],
        "\u63d2\u4ef6": ['plugin'],
        "\u5957\u4ef6": ['suite'],
        "\u504f\u7f6e": ['bias'],
        "\u9002\u914d\u5668": ['adapter'],
        "\u8868\u793a": ['representation', 'repr'],
        "\u7ba1\u7ebf": ['pipeline'],
        "\u793a\u4f8b": ['example', 'demo', 'template'],
        "\u6a21\u677f": ['template', 'example'],
        "\u5e76\u884c": ['parallel'],
        "\u591a\u76ee\u6807": ['multiobjective', 'mo'],
        "\u7ea6\u675f": ['constraint'],
        "\u56fe": ['graph'],
        "\u53ef\u89c6\u5316": ['viz', 'visual', 'visualization', 'run_inspector'],
        "\u53ef\u89c6\u5316\u5148\u9a8c": ['visualization', 'prior', 'structure_prior', 'run_inspector'],
        "\u5148\u9a8c": ['prior', 'structure_prior'],
        "\u8def\u5f84": ['path'],
        "\u542f\u53d1": ['heuristic'],
        "\u8bc4\u4f30": ['evaluation', 'evaluate'],
        "\u641c\u7d22": ['search'],
        "\u534f\u540c": ['cooperation', 'multi_strategy', 'multi-strategy'],
        "\u591a\u7b56\u7565": ['multi_strategy', 'multi-strategy'],
        "\u89d2\u8272": ['role'],
        "\u9000\u706b": ['simulated_annealing', 'sa'],
        "\u7981\u5fcc": ['tabu'],
        "\u5dee\u5206\u8fdb\u5316": ['differential_evolution', 'de'],
        "\u7c92\u5b50\u7fa4": ['pso'],
        "\u53d8\u5f02": ['mutation', 'mutator'],
        "\u521d\u59cb\u5316": ['initializer', 'init'],
        "\u4fee\u590d": ['repair'],
        "\u7f16\u7801": ['encode'],
        "\u89e3\u7801": ['decode'],
        "\u57fa\u51c6": ['benchmark'],
        "\u76d1\u63a7": ['monitor'],
        "\u6536\u655b": ['convergence'],
        "\u7cbe\u82f1": ['elite'],
        "\u591a\u6837\u6027": ['diversity'],
        "\u4ee3\u7406": ['surrogate'],
        "\u7edf\u8ba1": ['metrics'],
        "\u65e5\u5fd7": ['logging', 'log', 'report'],
        "\u62a5\u544a": ['report'],
        "\u5206\u5e03\u5f0f": ['distributed', 'ray'],
        "\u4e3b\u52a8\u5b66\u4e60": ['active_learning', 'active'],
        "\u524d\u6cbf": ['frontier'],
        "\u7ed3\u6784\u5148\u9a8c": ['structure', 'prior'],
        "\u5bf9\u79f0": ['symmetry'],
        "\u591a\u4fdd\u771f": ['multi_fidelity'],
        "\u98ce\u9669": ['risk', 'cvar', 'worst_case'],
        "\u9c81\u68d2": ['robust', 'robustness'],
        "\u4fe1\u8d56\u57df": ['trust_region', 'tr'],
        "\u5b50\u7a7a\u95f4": ['subspace', 'low_rank'],
        "\u975e\u5149\u6ed1": ['nonsmooth', 'non_smooth'],
        "\u6a21\u578b": ['model', 'surrogate'],
        "\u8499\u7279\u5361\u6d1b": ['monte_carlo', 'mc'],
    }
    out: List[List[str]] = []
    for t in tokens:
        group = [t]
        group.extend(alias_map.get(t, []))
        seen = set()
        uniq = []
        for item in group:
            if item in seen:
                continue
            seen.add(item)
            uniq.append(item)
        out.append(uniq)
    return out


def _default_entries() -> List[CatalogEntry]:
    # NOTE: keep this list small and "authoritative". Add entries only for modern components.
    return [
        # --- Solvers (bases) ---
        CatalogEntry(
            key="solver.nsga2",
            title="BlackBoxSolverNSGAII",
            kind="tool",
            import_path="nsgablack.core.solver:BlackBoxSolverNSGAII",
            tags=('evolutionary', 'nsga2', 'solver'),
            summary="\u5de5\u5177\uff1aBlackBoxSolverNSGAII\u3002 / Tool: BlackBoxSolverNSGAII.",
        ),
        CatalogEntry(
            key="solver.blank",
            title="BlankSolverBase",
            kind="tool",
            import_path="nsgablack.core.blank_solver:BlankSolverBase",
            tags=('base', 'blank', 'solver'),
            summary="\u5de5\u5177\uff1aBlankSolverBase\u3002 / Tool: BlankSolverBase.",
        ),
        CatalogEntry(
            key="solver.composable",
            title="ComposableSolver",
            kind="tool",
            import_path="nsgablack.core.composable_solver:ComposableSolver",
            tags=('adapter', 'composition', 'solver'),
            summary="\u5de5\u5177\uff1aComposableSolver\u3002 / Tool: ComposableSolver.",
        ),
        # --- Adapters ---
        CatalogEntry(
            key="adapter.vns",
            title="VNSAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:VNSAdapter",
            tags=('adapter', 'core', 'local_search', 'refinement', 'stage', 'strategy', 'vns'),
            summary="VNS局部搜索内核：多邻域分阶段精修。 / Adapter: VNS local search core with multi-neighborhood refinement.",
            companions=("repr.context_gaussian", "repr.context_switch", "suite.vns"),
        ),
        CatalogEntry(
            key="adapter.sa",
            title="SimulatedAnnealingAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:SimulatedAnnealingAdapter",
            tags=('adapter', 'core', 'local_search', 'sa', 'simulated_annealing', 'strategy'),
            summary="模拟退火内核：温度调度 + Metropolis接受。 / Adapter: SA core with temperature schedule and Metropolis acceptance.",
            companions=("repr.context_gaussian", "suite.sa"),
        ),
        CatalogEntry(
            key="adapter.multi_strategy",
            title="MultiStrategyControllerAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:MultiStrategyControllerAdapter",
            tags=('adapter', 'controller', 'cooperation', 'core', 'multi_strategy', 'parallel', 'roles', 'strategy'),
            summary="多策略协同控制器：统一调度、共享状态与动态预算。 / Adapter: multi-strategy controller with unified scheduling/shared state/dynamic budgets.",
            companions=("suite.multi_strategy", "plugin.pareto_archive"),
        ),
        CatalogEntry(
            key="adapter.moead",
            title="MOEADAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:MOEADAdapter",
            tags=('adapter', 'core', 'decomposition', 'moead', 'multiobjective', 'strategy'),
            summary="MOEA/D分解内核：权重向量 + 邻域替换。 / Adapter: MOEA/D decomposition core with weight vectors and neighborhood replacement.",
            companions=("plugin.pareto_archive", "suite.moead"),
        ),
        CatalogEntry(
            key="adapter.trust_region_dfo",
            title="TrustRegionDFOAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:TrustRegionDFOAdapter",
            tags=('adapter', 'core', 'dfo', 'local_search', 'strategy', 'trust_region'),
            summary="信赖域DFO内核：无梯度局部搜索。 / Adapter: trust-region derivative-free local search.",
        ),
        CatalogEntry(
            key="adapter.trust_region_subspace",
            title="TrustRegionSubspaceAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:TrustRegionSubspaceAdapter",
            tags=('adapter', 'core', 'dfo', 'strategy', 'subspace', 'trust_region'),
            summary="子空间/低秩信赖域：适用高维局部搜索。 / Adapter: subspace/low-rank trust-region search for high-D.",
        ),
        CatalogEntry(
            key="adapter.trust_region_nonsmooth",
            title="TrustRegionNonSmoothAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:TrustRegionNonSmoothAdapter",
            tags=('adapter', 'core', 'local_search', 'nonsmooth', 'strategy', 'trust_region'),
            summary="非光滑信赖域：支持Linf聚合等非光滑目标。 / Adapter: non-smooth trust-region with Linf aggregation.",
        ),
        CatalogEntry(
            key="adapter.mas",
            title="MASAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:MASAdapter",
            tags=('adapter', 'core', 'local_search', 'mas', 'strategy', 'surrogate'),
            summary="Model-and-Search：交替建模与搜索。 / Adapter: model-and-search alternating model update + search.",
        ),
        # --- Biases (algorithmic) ---
        CatalogEntry(
            key="bias.tabu",
            title="TabuSearchBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.tabu_search:TabuSearchBias",
            tags=('bias', 'memory', 'strategy', 'tabu', 'algorithmic'),
            summary="禁忌搜索偏置：记忆路\u7ebf\u9632\u6b62\u8fd4\u56de\u3002 / Algorithmic bias: tabu memory to avoid cycling.",
        ),
        CatalogEntry(
            key="bias.robustness",
            title="RobustnessBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.signal_driven.robustness:RobustnessBias",
            tags=('bias', 'mc', 'robustness', 'signal_driven', 'algorithmic'),
            summary="鲁棒性偏置：针\u5bf9\u6270\u52a8\u7684\u7a33\u5b9a\u6027\u8bc4\u4f30\u3002 / Algorithmic bias: robustness-oriented scoring under perturbations.",
            companions=("plugin.monte_carlo_eval", "suite.monte_carlo_robustness"),
        ),
        CatalogEntry(
            key="bias.dynamic_penalty",
            title="DynamicPenaltyBias",
            kind="bias",
            import_path="nsgablack.bias.domain.dynamic_penalty:DynamicPenaltyBias",
            tags=('bias', 'constraint', 'domain', 'dynamic', 'penalty', 'schedule'),
            summary="动态惩罚偏置：随违反程度调节惩罚强度。 / Domain bias: dynamic penalty for constraint violation.",
        ),
        
        CatalogEntry(
            key="adapter.trust_region_mo_dfo",
            title="TrustRegionMODFOAdapter",
            kind="adapter",
            import_path="nsgablack.core.adapters:TrustRegionMODFOAdapter",
            tags=('adapter', 'core', 'dfo', 'multiobjective', 'strategy', 'trust_region'),
            summary="多目标信赖域DFO：权重标度/帕累托精修。 / Adapter: MO trust-region DFO with scalarization.",
        ),
        
        CatalogEntry(
            key="bias.structure_prior",
            title="StructurePriorBias",
            kind="bias",
            import_path="nsgablack.bias.domain.structure_prior:StructurePriorBias",
            tags=('bias', 'domain', 'prior', 'structure', 'symmetry'),
            summary="结构先验偏置：注入结构/对称偏好。 / Domain bias: structure/symmetry prior.",
        ),
        
        CatalogEntry(
            key="bias.uncertainty_exploration",
            title="UncertaintyExplorationBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.signal_driven.uncertainty_exploration:UncertaintyExplorationBias",
            tags=('bias', 'exploration', 'signal_driven', 'uncertainty', 'algorithmic'),
            summary="不确\u5b9a\u63a2\u7d22\u504f\u7f6e\uff1a\u4f18\u5148\u9ad8\u4e0d\u786e\u5b9a\u533a\u57df\u3002 / Algorithmic bias: explore high-uncertainty regions.",
        ),
        
        CatalogEntry(
            key="bias.risk",
            title="RiskBias",
            kind="bias",
            import_path="nsgablack.bias.domain.risk_bias:RiskBias",
            tags=('bias', 'cvar', 'domain', 'risk', 'worst_case'),
            summary="风险偏置：支持CVaR/最坏情况风险控制。 / Domain bias: risk-aware scoring (CVaR/worst-case).",
        ),
        # --- Plugins ---
        CatalogEntry(
            key="plugin.monte_carlo_eval",
            title="MonteCarloEvaluationPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.evaluation.monte_carlo_evaluation:MonteCarloEvaluationPlugin",
            tags=('evaluation', 'mc', 'signal'),
            summary="\u63d2\u4ef6\uff1aMonteCarloEvaluationPlugin\u3002 / Plugin: MonteCarloEvaluationPlugin.",
            companions=("bias.robustness", "suite.monte_carlo_robustness"),
        ),
        CatalogEntry(
            key="plugin.pareto_archive",
            title="ParetoArchivePlugin",
            kind="plugin",
            import_path="nsgablack.plugins.runtime.pareto_archive:ParetoArchivePlugin",
            tags=('archive', 'multiobjective', 'pareto'),
            summary="\u63d2\u4ef6\uff1aParetoArchivePlugin\u3002 / Plugin: ParetoArchivePlugin.",
            companions=("adapter.moead", "suite.moead"),
        ),
        CatalogEntry(
            key="plugin.benchmark_harness",
            title="BenchmarkHarnessPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.ops.benchmark_harness:BenchmarkHarnessPlugin",
            tags=('benchmark', 'comparison', 'logging', 'protocol'),
            summary="\u63d2\u4ef6\uff1aBenchmarkHarnessPlugin\u3002 / Plugin: BenchmarkHarnessPlugin.",
            companions=("suite.benchmark_harness",),
        ),
        CatalogEntry(
            key="plugin.module_report",
            title="ModuleReportPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.ops.module_report:ModuleReportPlugin",
            tags=('ablation', 'audit', 'bias', 'report'),
            summary="\u63d2\u4ef6\uff1aModuleReportPlugin\u3002 / Plugin: ModuleReportPlugin.",
            companions=("suite.module_report", "plugin.benchmark_harness"),
        ),
        CatalogEntry(
            key="plugin.profiler",
            title="ProfilerPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.ops.profiler:ProfilerPlugin",
            tags=('audit', 'performance', 'profile', 'throughput'),
            summary="\u63d2\u4ef6\uff1aProfilerPlugin\u3002 / Plugin: ProfilerPlugin.",
            companions=("plugin.benchmark_harness", "plugin.module_report"),
        ),
        CatalogEntry(
            key="plugin.surrogate_eval",
            title="SurrogateEvaluationPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.evaluation.surrogate_evaluation:SurrogateEvaluationPlugin",
            tags=('evaluation', 'optional', 'surrogate'),
            summary="\u63d2\u4ef6\uff1aSurrogateEvaluationPlugin\u3002 / Plugin: SurrogateEvaluationPlugin.",
        ),
        
        CatalogEntry(
            key="plugin.multi_fidelity_eval",
            title="MultiFidelityEvaluationPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.evaluation.multi_fidelity_evaluation:MultiFidelityEvaluationPlugin",
            tags=('evaluation', 'frontier', 'multi_fidelity', 'plugin'),
            summary="\u63d2\u4ef6\uff1aMultiFidelityEvaluationPlugin\u3002 / Plugin: MultiFidelityEvaluationPlugin.",
        ),
        # --- Representation helpers ---
        CatalogEntry(
            key="plugin.mas_model",
            title="MASModelPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.models.mas_model:MASModelPlugin",
            tags=('mas', 'surrogate'),
            summary="\u63d2\u4ef6\uff1aMASModelPlugin\u3002 / Plugin: MASModelPlugin.",
        ),
        CatalogEntry(
            key="plugin.subspace_basis",
            title="SubspaceBasisPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.models.subspace_basis:SubspaceBasisPlugin",
            tags=('cluster', 'dfo', 'pca', 'random', 'sparse_pca', 'subspace', 'svd'),
            summary="\u63d2\u4ef6\uff1aSubspaceBasisPlugin\u3002 / Plugin: SubspaceBasisPlugin.",
        ),
        CatalogEntry(
            key="repr.context_gaussian",
            title="ContextGaussianMutation",
            kind="representation",
            import_path="nsgablack.representation.continuous:ContextGaussianMutation",
            tags=('context', 'continuous', 'mutation', 'vns'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aContextGaussianMutation\u3002 / Representation: ContextGaussianMutation.",
            companions=("adapter.vns",),
        ),
        CatalogEntry(
            key="repr.context_switch",
            title="ContextSwitchMutator",
            kind="representation",
            import_path="nsgablack.representation:ContextSwitchMutator",
            tags=('context', 'discrete', 'mutation', 'switch', 'vns'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aContextSwitchMutator\u3002 / Representation: ContextSwitchMutator.",
            companions=("adapter.vns",),
        ),
        CatalogEntry(
            key="repr.projection_repair",
            title="ProjectionRepair",
            kind="representation",
            import_path="nsgablack.representation.continuous:ProjectionRepair",
            tags=('bounds', 'pipeline', 'projection', 'repair', 'simplex'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aProjectionRepair\u3002 / Representation: ProjectionRepair.",
        ),
        
        CatalogEntry(
            key="repr.dynamic_repair",
            title="DynamicRepair",
            kind="representation",
            import_path="nsgablack.representation.dynamic:DynamicRepair",
            tags=('dynamic', 'pipeline', 'repair'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aDynamicRepair\u3002 / Representation: DynamicRepair.",
        ),
        # --- Suites (authority wiring) ---
        CatalogEntry(
            key="suite.monte_carlo_robustness",
            title="attach_monte_carlo_robustness",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_monte_carlo_robustness",
            tags=('authority', 'bundle', 'mc', 'robustness', 'suite'),
            summary="权威装配：Monte Carlo评估 + 鲁棒性偏置。 / Authority wiring: MC evaluation + robustness bias.",
            companions=("plugin.monte_carlo_eval", "bias.robustness"),
        ),
        CatalogEntry(
            key="suite.ray_parallel",
            title="attach_ray_parallel",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_ray_parallel",
            tags=('authority', 'bundle', 'distributed', 'parallel', 'ray', 'suite'),
            summary="权威装配：Ray并行评估/调度。 / Authority wiring: Ray parallel evaluation/scheduling.",
            companions=("plugin.profiler", "plugin.benchmark_harness"),
        ),
        CatalogEntry(
            key="suite.moead",
            title="attach_moead",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_moead",
            tags=('authority', 'bundle', 'moead', 'multiobjective', 'suite'),
            summary="权威装配：MOEA/D适配器 + Pareto归档。 / Authority wiring: MOEA/D adapter + Pareto archive.",
            companions=("adapter.moead", "plugin.pareto_archive"),
        ),
        CatalogEntry(
            key="suite.sa",
            title="attach_simulated_annealing",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_simulated_annealing",
            tags=('authority', 'bundle', 'sa', 'simulated_annealing', 'suite'),
            summary="权威装配：SA适配器 + 推荐算子。 / Authority wiring: SA adapter + recommended operators.",
            companions=("adapter.sa", "repr.context_gaussian"),
        ),
        CatalogEntry(
            key="suite.vns",
            title="attach_vns",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_vns",
            tags=('authority', 'bundle', 'local_search', 'suite', 'vns'),
            summary="权威装配：VNS适配器 + 多邻域算子。 / Authority wiring: VNS adapter + multi-neighborhood operators.",
            companions=("adapter.vns", "repr.context_gaussian", "repr.context_switch"),
        ),
        CatalogEntry(
            key="suite.trust_region_dfo",
            title="attach_trust_region_dfo",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_trust_region_dfo",
            tags=('authority', 'bundle', 'dfo', 'local_search', 'suite', 'trust_region'),
            summary="权威装配：信赖域DFO + 报告插件。 / Authority wiring: trust-region DFO + reporting.",
            companions=("adapter.trust_region_dfo", "plugin.benchmark_harness", "plugin.module_report"),
        ),
        CatalogEntry(
            key="suite.trust_region_subspace",
            title="attach_trust_region_subspace",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_trust_region_subspace",
            tags=('authority', 'bundle', 'local_search', 'subspace', 'suite', 'trust_region'),
            summary="权威装配：子空间信赖域 + 报告插件。 / Authority wiring: subspace trust-region + reporting.",
            companions=("adapter.trust_region_subspace", "plugin.benchmark_harness", "plugin.module_report"),
        ),
        CatalogEntry(
            key="suite.trust_region_subspace_learned",
            title="attach_trust_region_subspace_learned",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_trust_region_subspace_learned",
            tags=('authority', 'bundle', 'learned', 'subspace', 'suite', 'trust_region'),
            summary="权威装配：子空间信赖域 + 学习基底(PCA/SVD)。 / Authority wiring: subspace trust-region + learned basis (PCA/SVD).",
            companions=("adapter.trust_region_subspace", "plugin.subspace_basis", "plugin.benchmark_harness", "plugin.module_report"),
        ),
        CatalogEntry(
            key="suite.trust_region_nonsmooth",
            title="attach_trust_region_nonsmooth",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_trust_region_nonsmooth",
            tags=('authority', 'bundle', 'local_search', 'nonsmooth', 'suite', 'trust_region'),
            summary="权威装配：非光滑信赖域 + 报告插件。 / Authority wiring: nonsmooth trust-region + reporting.",
            companions=("adapter.trust_region_nonsmooth", "plugin.benchmark_harness", "plugin.module_report"),
        ),
        CatalogEntry(
            key="suite.mas",
            title="attach_mas",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_mas",
            tags=('authority', 'bundle', 'local_search', 'mas', 'suite', 'surrogate'),
            summary="权威装配：MAS + 模型插件 + 报告。 / Authority wiring: MAS + model plugin + reporting.",
            companions=("adapter.mas", "plugin.mas_model", "plugin.benchmark_harness", "plugin.module_report"),
        ),
        CatalogEntry(
            key="suite.multi_strategy",
            title="attach_multi_strategy_coop",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_multi_strategy_coop",
            tags=('authority', 'bundle', 'cooperation', 'multi_strategy', 'parallel', 'suite'),
            summary="权威装配：多策略协同（角色/预算/共享状态）。 / Authority wiring: multi-strategy cooperation with roles/budgets/shared state.",
            companions=("adapter.multi_strategy", "plugin.pareto_archive"),
        ),
        CatalogEntry(
            key="suite.benchmark_harness",
            title="attach_benchmark_harness",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_benchmark_harness",
            tags=('authority', 'benchmark', 'bundle', 'comparison', 'protocol', 'suite'),
            summary="权威装配：BenchmarkHarness统一输出口径。 / Authority wiring: BenchmarkHarness output protocol.",
            companions=("plugin.benchmark_harness",),
        ),
        CatalogEntry(
            key="suite.module_report",
            title="attach_module_report",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_module_report",
            tags=('ablation', 'audit', 'authority', 'bundle', 'report', 'suite'),
            summary="权威装配：ModuleReport审计/消融。 / Authority wiring: ModuleReport audit/ablation.",
            companions=("plugin.module_report", "plugin.benchmark_harness"),
        ),
        CatalogEntry(
            key="suite.nsga2_engineering",
            title="attach_nsga2_engineering",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_nsga2_engineering",
            tags=('authority', 'bundle', 'engineering', 'nsga2', 'plugins', 'suite'),
            summary="权威装配：NSGA-II工程化插件集（日志/精英/多样性）。 / Authority wiring: NSGA-II engineering bundle (logging/elite/diversity).",
            companions=("plugin.elite", "plugin.convergence_monitor", "plugin.diversity_init", "plugin.benchmark_harness"),
        ),

        # --- Biases (more algorithmic building blocks; kept as "main class per module") ---
        CatalogEntry(
            key="bias.sa",
            title="SimulatedAnnealingBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.simulated_annealing:SimulatedAnnealingBias",
            tags=('algorithmic', 'bias', 'local_search', 'sa', 'simulated_annealing', 'strategy'),
            summary="退火偏置：温度/接受准则引导探索。 / Algorithmic bias: SA temperature/acceptance guidance.",
        ),
        CatalogEntry(
            key="bias.de",
            title="DifferentialEvolutionBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.differential_evolution:DifferentialEvolutionBias",
            tags=('algorithmic', 'bias', 'de', 'differential_evolution', 'mutation', 'strategy'),
            summary="差分进化偏置：差分变异/交叉倾向。 / Algorithmic bias: DE mutation/crossover guidance.",
        ),
        CatalogEntry(
            key="bias.pso",
            title="ParticleSwarmBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.pso:ParticleSwarmBias",
            tags=('algorithmic', 'bias', 'particle_swarm', 'pso', 'strategy', 'swarm'),
            summary="粒子群偏置：惯性/群体吸引引导。 / Algorithmic bias: PSO inertia/social guidance.",
        ),
        CatalogEntry(
            key="bias.cmaes",
            title="CMAESBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.cma_es:CMAESBias",
            tags=('algorithmic', 'bias', 'cma-es', 'cmaes', 'covariance', 'strategy'),
            summary="CMA-ES偏置：协方差自适应搜索。 / Algorithmic bias: CMA-ES covariance adaptation.",
        ),
        CatalogEntry(
            key="bias.levy",
            title="LevyFlightBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.levy_flight:LevyFlightBias",
            tags=('algorithmic', 'bias', 'exploration', 'levy', 'random_walk'),
            summary="Levy飞行偏置：长跳跃探索。 / Algorithmic bias: Levy-flight exploration.",
        ),
        CatalogEntry(
            key="bias.pattern_search",
            title="PatternSearchBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.pattern_search:PatternSearchBias",
            tags=('algorithmic', 'bias', 'derivative_free', 'local_search', 'pattern_search'),
            summary="模式搜索偏置：步长/网格模式探索。 / Algorithmic bias: pattern search steps.",
        ),
        CatalogEntry(
            key="bias.gradient_descent",
            title="GradientDescentBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.gradient_descent:GradientDescentBias",
            tags=('algorithmic', 'bias', 'continuous', 'gd', 'gradient_descent'),
            summary="梯度下降偏置：沿负梯度精修。 / Algorithmic bias: gradient descent refinement.",
        ),
        CatalogEntry(
            key="bias.convergence",
            title="ConvergenceBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.convergence:ConvergenceBias",
            tags=('algorithmic', 'bias', 'convergence', 'exploitation', 'schedule'),
            summary="收敛偏置：优先收敛与精修。 / Algorithmic bias: convergence acceleration.",
        ),
        CatalogEntry(
            key="bias.diversity",
            title="DiversityBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.diversity:DiversityBias",
            tags=('algorithmic', 'bias', 'diversity', 'exploration', 'niching'),
            summary="多样性偏置：维持解集分散。 / Algorithmic bias: diversity maintenance.",
        ),
        CatalogEntry(
            key="bias.nsga2_core",
            title="NSGA2Bias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.nsga2:NSGA2Bias",
            tags=('algorithmic', 'bias', 'crowding', 'multiobjective', 'nsga2'),
            summary="NSGA-II核心偏置：非支配排序 + 拥挤度。 / Algorithmic bias: NSGA-II ranking/crowding.",
        ),
        CatalogEntry(
            key="bias.nsga3_core",
            title="NSGA3ReferencePointBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.nsga3:NSGA3ReferencePointBias",
            tags=('algorithmic', 'bias', 'multiobjective', 'nsga3', 'reference_point'),
            summary="NSGA-III参考点偏置：参考点驱动排序。 / Algorithmic bias: NSGA-III reference points.",
        ),
        CatalogEntry(
            key="bias.spea2_core",
            title="SPEA2StrengthBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.spea2:SPEA2StrengthBias",
            tags=('algorithmic', 'bias', 'multiobjective', 'spea2', 'strength'),
            summary="SPEA2强度偏置：强度/密度评估。 / Algorithmic bias: SPEA2 strength/density.",
        ),
        CatalogEntry(
            key="bias.moead_decomposition",
            title="MOEADDecompositionBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.moead:MOEADDecompositionBias",
            tags=('algorithmic', 'bias', 'decomposition', 'moead', 'multiobjective'),
            summary="MOEA/D分解偏置：权重与邻域分解信号。 / Algorithmic bias: MOEA/D decomposition signals.",
        ),

        
        CatalogEntry(
            key="suite.trust_region_mo_dfo",
            title="attach_trust_region_mo_dfo",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_trust_region_mo_dfo",
            tags=(', ', 'authority', 'bundle', 'frontier', 'multiobjective', 'suite', 'trust_region'),
            summary="权威装配：多目标DFO + Pareto + 报告。 / Authority wiring: MO DFO + Pareto + reporting.",
            companions=("adapter.trust_region_mo_dfo", "plugin.pareto_archive"),
        ),
        CatalogEntry(
            key="suite.trust_region_subspace_frontier",
            title="attach_trust_region_subspace_frontier",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_trust_region_subspace_frontier",
            tags=(', ', 'authority', 'bundle', 'frontier', 'subspace', 'suite', 'trust_region'),
            summary="权威装配：子空间信赖域前沿组合 + 报告。 / Authority wiring: subspace trust-region frontier bundle.",
            companions=("adapter.trust_region_subspace", "plugin.subspace_basis"),
        ),
        CatalogEntry(
            key="suite.active_learning_surrogate",
            title="attach_active_learning_surrogate",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_active_learning_surrogate",
            tags=('active_learning', 'authority', 'bundle', 'frontier', 'suite', 'surrogate'),
            summary="权威装配：主动学习代理评估 + 报告。 / Authority wiring: active-learning surrogate evaluation + reporting.",
            companions=("plugin.surrogate_eval",),
        ),
        CatalogEntry(
            key="suite.robust_dfo",
            title="attach_robust_dfo",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_robust_dfo",
            tags=('authority', 'bundle', 'dfo', 'frontier', 'mc', 'robustness', 'suite'),
            summary="权威装配：DFO + MC评估 + 鲁棒偏置。 / Authority wiring: DFO + MC eval + robustness bias.",
            companions=("adapter.trust_region_dfo", "plugin.monte_carlo_eval", "bias.robustness"),
        ),
        CatalogEntry(
            key="suite.surrogate_assisted_ea",
            title="attach_surrogate_assisted_ea",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_surrogate_assisted_ea",
            tags=('authority', 'bundle', 'evolutionary', 'frontier', 'suite', 'surrogate'),
            summary="权威装配：代理辅助进化搜索。 / Authority wiring: surrogate-assisted evolutionary search.",
            companions=("plugin.surrogate_eval",),
        ),
        CatalogEntry(
            key="suite.surrogate_model_lab",
            title="attach_surrogate_model_lab",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_surrogate_model_lab",
            tags=('authority', 'bundle', 'frontier', 'model_type', 'suite', 'surrogate'),
            summary="权威装配：代理模型家族实验室。 / Authority wiring: surrogate model family lab bundle.",
            companions=("plugin.surrogate_eval",),
        ),
        CatalogEntry(
            key="suite.structure_prior_mo",
            title="attach_structure_prior_mo",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_structure_prior_mo",
            tags=('authority', 'bundle', 'frontier', 'multiobjective', 'structure', 'suite'),
            summary="权威装配：结构先验 + 多目标组合。 / Authority wiring: structure-prior + multi-objective bundle.",
            companions=("bias.structure_prior", "adapter.moead"),
        ),
        
        CatalogEntry(
            key="suite.multi_fidelity_eval",
            title="attach_multi_fidelity_eval",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_multi_fidelity_eval",
            tags=('authority', 'bundle', 'evaluation', 'frontier', 'multi_fidelity', 'suite'),
            summary="权威装配：多保真评估 + 报告。 / Authority wiring: multi-fidelity evaluation + reporting.",
            companions=("plugin.multi_fidelity_eval",),
        ),
        CatalogEntry(
            key="suite.risk_cvar",
            title="attach_risk_cvar",
            kind="suite",
            import_path="nsgablack.utils.suites:attach_risk_cvar",
            tags=('authority', 'bundle', 'cvar', 'frontier', 'risk', 'suite'),
            summary="权威装配：MC评估 + CVaR风险偏置。 / Authority wiring: MC evaluation + CVaR risk bias.",
            companions=("plugin.monte_carlo_eval", "bias.risk"),
        ),
        # --- Plugins (more capabilities) ---
        CatalogEntry(
            key="plugin.adaptive_parameters",
            title="AdaptiveParametersPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.runtime.adaptive_parameters:AdaptiveParametersPlugin",
            tags=('adaptive', 'parameters', 'plugin'),
            summary="\u63d2\u4ef6\uff1aAdaptiveParametersPlugin\u3002 / Plugin: AdaptiveParametersPlugin.",
        ),
        CatalogEntry(
            key="plugin.elite",
            title="BasicElitePlugin",
            kind="plugin",
            import_path="nsgablack.plugins.runtime.elite_retention:BasicElitePlugin",
            tags=('archive', 'elite', 'plugin'),
            summary="\u63d2\u4ef6\uff1aBasicElitePlugin\u3002 / Plugin: BasicElitePlugin.",
        ),
        CatalogEntry(
            key="plugin.convergence_monitor",
            title="ConvergencePlugin",
            kind="plugin",
            import_path="nsgablack.plugins.runtime.convergence:ConvergencePlugin",
            tags=('convergence', 'monitor', 'plugin'),
            summary="\u63d2\u4ef6\uff1aConvergencePlugin\u3002 / Plugin: ConvergencePlugin.",
        ),
        CatalogEntry(
            key="plugin.diversity_init",
            title="DiversityInitPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.runtime.diversity_init:DiversityInitPlugin",
            tags=('diversity', 'init', 'plugin'),
            summary="\u63d2\u4ef6\uff1aDiversityInitPlugin\u3002 / Plugin: DiversityInitPlugin.",
        ),
        CatalogEntry(
            key="plugin.memory",
            title="MemoryPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.system.memory_optimize:MemoryPlugin",
            tags=('engineering', 'memory', 'plugin'),
            summary="\u63d2\u4ef6\uff1aMemoryPlugin\u3002 / Plugin: MemoryPlugin.",
        ),

        # --- Representation (core presets) ---
        CatalogEntry(
            key="repr.pipeline",
            title="RepresentationPipeline",
            kind="representation",
            import_path="nsgablack.representation:RepresentationPipeline",
            tags=('core', 'pipeline', 'representation'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aRepresentationPipeline\u3002 / Representation: RepresentationPipeline.",
        ),
        CatalogEntry(
            key="repr.continuous",
            title="UniformInitializer",
            kind="representation",
            import_path="nsgablack.representation.continuous:UniformInitializer",
            tags=('continuous', 'initializer', 'real'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aUniformInitializer\u3002 / Representation: UniformInitializer.",
        ),
        CatalogEntry(
            key="repr.integer",
            title="IntegerInitializer",
            kind="representation",
            import_path="nsgablack.representation.integer:IntegerInitializer",
            tags=('discrete', 'initializer', 'integer'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aIntegerInitializer\u3002 / Representation: IntegerInitializer.",
        ),
        CatalogEntry(
            key="repr.permutation",
            title="PermutationInitializer",
            kind="representation",
            import_path="nsgablack.representation.permutation:PermutationInitializer",
            tags=('discrete', 'initializer', 'permutation', 'tsp'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aPermutationInitializer\u3002 / Representation: PermutationInitializer.",
        ),
        CatalogEntry(
            key="repr.binary",
            title="BinaryInitializer",
            kind="representation",
            import_path="nsgablack.representation.binary:BinaryInitializer",
            tags=('binary', 'bit', 'initializer'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aBinaryInitializer\u3002 / Representation: BinaryInitializer.",
        ),
        CatalogEntry(
            key="repr.graph",
            title="GraphEdgeInitializer",
            kind="representation",
            import_path="nsgablack.representation.graph:GraphEdgeInitializer",
            tags=('graph', 'initializer', 'network'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aGraphEdgeInitializer\u3002 / Representation: GraphEdgeInitializer.",
        ),
        CatalogEntry(
            key="repr.matrix",
            title="IntegerMatrixInitializer",
            kind="representation",
            import_path="nsgablack.representation.matrix:IntegerMatrixInitializer",
            tags=('grid', 'initializer', 'matrix'),
            summary="\u8868\u793a\u7ec4\u4ef6\uff1aIntegerMatrixInitializer\u3002 / Representation: IntegerMatrixInitializer.",
        ),

        # --- Tools (utilities; discoverable but not part of the solver base) ---
        CatalogEntry(
            key="tool.parallel_evaluator",
            title="ParallelEvaluator",
            kind="tool",
            import_path="nsgablack.utils.parallel:ParallelEvaluator",
            tags=('evaluation', 'parallel', 'tool'),
            summary="\u5de5\u5177\uff1aParallelEvaluator\u3002 / Tool: ParallelEvaluator.",
        ),
        CatalogEntry(
            key="tool.context_keys",
            title="Context Keys",
            kind="tool",
            import_path="nsgablack.utils.context:context_keys",
            tags=('context', 'keys', 'schema', 'tool'),
            summary="\u5de5\u5177\uff1aContext Keys\u3002 / Tool: Context Keys.",
        ),
        CatalogEntry(
            key="tool.context_schema",
            title="MinimalEvaluationContext",
            kind="tool",
            import_path="nsgablack.utils.context:MinimalEvaluationContext",
            tags=('context', 'parallel', 'schema', 'tool'),
            summary="\u5de5\u5177\uff1aMinimalEvaluationContext\u3002 / Tool: MinimalEvaluationContext.",
            companions=("tool.context_keys",),
        ),
        CatalogEntry(
            key="tool.logging",
            title="configure_logging",
            kind="tool",
            import_path="nsgablack.utils.engineering:configure_logging",
            tags=('engineering', 'logging', 'tool'),
            summary="\u5de5\u5177\uff1aconfigure_logging\u3002 / Tool: configure_logging.",
        ),
        CatalogEntry(
            key="tool.metrics",
            title="pareto_filter",
            kind="tool",
            import_path="nsgablack.utils.analysis:pareto_filter",
            tags=('analysis', 'metrics', 'pareto', 'tool'),
            summary="\u5de5\u5177\uff1apareto_filter\u3002 / Tool: pareto_filter.",
        ),
        # --- Examples (templates / demos) ---
        CatalogEntry(
            key="example.template_continuous",
            title="template_continuous_constrained",
            kind="example",
            import_path="nsgablack.examples_registry:template_continuous_constrained",
            tags=('bias', 'constraint', 'continuous', 'example', 'pipeline', 'template'),
            summary="\u793a\u4f8b\uff1atemplate_continuous_constrained\u3002 / Example: template_continuous_constrained.",
        ),
        CatalogEntry(
            key="example.template_knapsack",
            title="template_knapsack_binary",
            kind="example",
            import_path="nsgablack.examples_registry:template_knapsack_binary",
            tags=('binary', 'example', 'knapsack', 'repair', 'template'),
            summary="\u793a\u4f8b\uff1atemplate_knapsack_binary\u3002 / Example: template_knapsack_binary.",
        ),
        CatalogEntry(
            key="example.template_tsp",
            title="template_tsp_permutation",
            kind="example",
            import_path="nsgablack.examples_registry:template_tsp_permutation",
            tags=('2opt', 'example', 'permutation', 'template', 'tsp'),
            summary="\u793a\u4f8b\uff1atemplate_tsp_permutation\u3002 / Example: template_tsp_permutation.",
        ),
        CatalogEntry(
            key="example.template_graph_path",
            title="template_graph_path",
            kind="example",
            import_path="nsgablack.examples_registry:template_graph_path",
            tags=('example', 'graph', 'path', 'repair', 'template'),
            summary="\u793a\u4f8b\uff1atemplate_graph_path\u3002 / Example: template_graph_path.",
        ),
        CatalogEntry(
            key="example.template_assignment",
            title="template_assignment_matrix",
            kind="example",
            import_path="nsgablack.examples_registry:template_assignment_matrix",
            tags=('assignment', 'example', 'matrix', 'repair', 'template'),
            summary="\u793a\u4f8b\uff1atemplate_assignment_matrix\u3002 / Example: template_assignment_matrix.",
        ),
        CatalogEntry(
            key="example.template_production_simple",
            title="template_production_schedule_simple",
            kind="example",
            import_path="nsgablack.examples_registry:template_production_schedule_simple",
            tags=('example', 'matrix', 'production', 'schedule', 'template'),
            summary="\u793a\u4f8b\uff1atemplate_production_schedule_simple\u3002 / Example: template_production_schedule_simple.",
        ),
        CatalogEntry(
            key="example.template_portfolio",
            title="template_portfolio_pareto",
            kind="example",
            import_path="nsgablack.examples_registry:template_portfolio_pareto",
            tags=('example', 'mo', 'pareto', 'portfolio', 'template'),
            summary="\u793a\u4f8b\uff1atemplate_portfolio_pareto\u3002 / Example: template_portfolio_pareto.",
        ),
        CatalogEntry(
            key="example.template_mo_pareto",
            title="template_multiobjective_pareto",
            kind="example",
            import_path="nsgablack.examples_registry:template_multiobjective_pareto",
            tags=('example', 'moead', 'multiobjective', 'pareto', 'template'),
            summary="\u793a\u4f8b\uff1atemplate_multiobjective_pareto\u3002 / Example: template_multiobjective_pareto.",
        ),
        CatalogEntry(
            key="example.dynamic_multi_strategy",
            title="dynamic_multi_strategy_demo",
            kind="example",
            import_path="nsgablack.examples_registry:dynamic_multi_strategy_demo",
            tags=('demo', 'dynamic', 'example', 'multi_strategy', 'switch'),
            summary="\u793a\u4f8b\uff1adynamic_multi_strategy_demo\u3002 / Example: dynamic_multi_strategy_demo.",
        ),
        CatalogEntry(
            key="example.trust_region_dfo",
            title="trust_region_dfo_demo",
            kind="example",
            import_path="nsgablack.examples_registry:trust_region_dfo_demo",
            tags=('demo', 'dfo', 'example', 'trust_region'),
            summary="\u793a\u4f8b\uff1atrust_region_dfo_demo\u3002 / Example: trust_region_dfo_demo.",
        ),
        CatalogEntry(
            key="example.trust_region_subspace",
            title="trust_region_subspace_demo",
            kind="example",
            import_path="nsgablack.examples_registry:trust_region_subspace_demo",
            tags=('demo', 'example', 'subspace', 'trust_region'),
            summary="\u793a\u4f8b\uff1atrust_region_subspace_demo\u3002 / Example: trust_region_subspace_demo.",
        ),
        CatalogEntry(
            key="example.monte_carlo_robust",
            title="monte_carlo_dp_robust_demo",
            kind="example",
            import_path="nsgablack.examples_registry:monte_carlo_dp_robust_demo",
            tags=('demo', 'example', 'monte_carlo', 'robust'),
            summary="\u793a\u4f8b\uff1amonte_carlo_dp_robust_demo\u3002 / Example: monte_carlo_dp_robust_demo.",
        ),
        CatalogEntry(
            key="example.surrogate_plugin",
            title="surrogate_plugin_demo",
            kind="example",
            import_path="nsgablack.examples_registry:surrogate_plugin_demo",
            tags=('demo', 'example', 'plugin', 'surrogate'),
            summary="\u793a\u4f8b\uff1asurrogate_plugin_demo\u3002 / Example: surrogate_plugin_demo.",
        ),
        CatalogEntry(
            key="example.multi_fidelity",
            title="multi_fidelity_demo",
            kind="example",
            import_path="nsgablack.examples_registry:multi_fidelity_demo",
            tags=('demo', 'example', 'multi_fidelity'),
            summary="\u793a\u4f8b\uff1amulti_fidelity_demo\u3002 / Example: multi_fidelity_demo.",
        ),
        CatalogEntry(
            key="example.risk_bias",
            title="risk_bias_demo",
            kind="example",
            import_path="nsgablack.examples_registry:risk_bias_demo",
            tags=('bias', 'demo', 'example', 'risk'),
            summary="\u793a\u4f8b\uff1arisk_bias_demo\u3002 / Example: risk_bias_demo.",
        ),
        CatalogEntry(
            key="example.bias_gallery",
            title="bias_gallery_demo",
            kind="example",
            import_path="nsgablack.examples_registry:bias_gallery_demo",
            tags=('bias', 'demo', 'example', 'gallery'),
            summary="\u793a\u4f8b\uff1abias_gallery_demo\u3002 / Example: bias_gallery_demo.",
        ),
        CatalogEntry(
            key="example.plugin_gallery",
            title="plugin_gallery_demo",
            kind="example",
            import_path="nsgablack.examples_registry:plugin_gallery_demo",
            tags=('demo', 'example', 'gallery', 'plugin'),
            summary="\u793a\u4f8b\uff1aplugin_gallery_demo\u3002 / Example: plugin_gallery_demo.",
        ),
        CatalogEntry(
            key="example.role_adapters",
            title="role_adapters_demo",
            kind="example",
            import_path="nsgablack.examples_registry:role_adapters_demo",
            tags=('adapter', 'demo', 'example', 'multi_role', 'role'),
            summary="\u793a\u4f8b\uff1arole_adapters_demo\u3002 / Example: role_adapters_demo.",
        ),
        CatalogEntry(
            key="example.astar",
            title="astar_demo",
            kind="example",
            import_path="nsgablack.examples_registry:astar_demo",
            tags=('astar', 'demo', 'example', 'graph', 'search'),
            summary="\u793a\u4f8b\uff1aastar_demo\u3002 / Example: astar_demo.",
        ),
        CatalogEntry(
            key="example.moa_star",
            title="moa_star_demo",
            kind="example",
            import_path="nsgablack.examples_registry:moa_star_demo",
            tags=('demo', 'example', 'moa_star', 'pareto', 'search'),
            summary="\u793a\u4f8b\uff1amoa_star_demo\u3002 / Example: moa_star_demo.",
        ),
        CatalogEntry(
            key="example.parallel_repair",
            title="parallel_repair_demo",
            kind="example",
            import_path="nsgablack.examples_registry:parallel_repair_demo",
            tags=('demo', 'example', 'parallel', 'pipeline', 'repair'),
            summary="\u793a\u4f8b\uff1aparallel_repair_demo\u3002 / Example: parallel_repair_demo.",
        ),
        CatalogEntry(
            key="example.nsga2_solver",
            title="nsga2_solver_demo",
            kind="example",
            import_path="nsgablack.examples_registry:nsga2_solver_demo",
            tags=('demo', 'example', 'nsga2', 'solver', 'suite'),
            summary="\u793a\u4f8b\uff1ansga2_solver_demo\u3002 / Example: nsga2_solver_demo.",
        ),
        CatalogEntry(
            key="example.parallel_evaluator",
            title="parallel_evaluator_demo",
            kind="example",
            import_path="nsgablack.examples_registry:parallel_evaluator_demo",
            tags=('demo', 'evaluation', 'example', 'parallel'),
            summary="\u793a\u4f8b\uff1aparallel_evaluator_demo\u3002 / Example: parallel_evaluator_demo.",
        ),
        CatalogEntry(
            key="example.context_keys",
            title="context_keys_demo",
            kind="example",
            import_path="nsgablack.examples_registry:context_keys_demo",
            tags=('context', 'demo', 'example', 'keys'),
            summary="\u793a\u4f8b\uff1acontext_keys_demo\u3002 / Example: context_keys_demo.",
        ),
        CatalogEntry(
            key="example.context_schema",
            title="context_schema_demo",
            kind="example",
            import_path="nsgablack.examples_registry:context_schema_demo",
            tags=('context', 'demo', 'example', 'schema'),
            summary="\u793a\u4f8b\uff1acontext_schema_demo\u3002 / Example: context_schema_demo.",
        ),
        CatalogEntry(
            key="example.logging",
            title="logging_demo",
            kind="example",
            import_path="nsgablack.examples_registry:logging_demo",
            tags=('demo', 'example', 'logging', 'tool'),
            summary="\u793a\u4f8b\uff1alogging_demo\u3002 / Example: logging_demo.",
        ),
        CatalogEntry(
            key="example.metrics",
            title="metrics_demo",
            kind="example",
            import_path="nsgablack.examples_registry:metrics_demo",
            tags=('demo', 'example', 'metrics', 'pareto'),
            summary="\u793a\u4f8b\uff1ametrics_demo\u3002 / Example: metrics_demo.",
        ),
        CatalogEntry(
            key="example.dynamic_cli_signal",
            title="dynamic_cli_signal_demo",
            kind="example",
            import_path="nsgablack.examples_registry:dynamic_cli_signal_demo",
            tags=('cli', 'demo', 'dynamic', 'example', 'signal'),
            summary="\u793a\u4f8b\uff1adynamic_cli_signal_demo\u3002 / Example: dynamic_cli_signal_demo.",
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
                            tags=_coerce_str_tuple(it.get("tags", ())),
                            summary=str(it.get("summary", "")).strip(),
                            companions=_coerce_str_tuple(it.get("companions", ())),
                            context_requires=_coerce_str_tuple(it.get("context_requires", ())),
                            context_provides=_coerce_str_tuple(it.get("context_provides", ())),
                            context_mutates=_coerce_str_tuple(it.get("context_mutates", ())),
                            context_cache=_coerce_str_tuple(it.get("context_cache", ())),
                            context_notes=_coerce_str_tuple(it.get("context_notes", ())),
                            use_when=_coerce_str_tuple(it.get("use_when", ())),
                            minimal_wiring=_coerce_str_tuple(it.get("minimal_wiring", ())),
                            required_companions=_coerce_str_tuple(it.get("required_companions", ())),
                            config_keys=_coerce_str_tuple(it.get("config_keys", ())),
                            example_entry=str(it.get("example_entry", "")).strip(),
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
        "nsgablack.plugins",
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
    context_requires = ["context.population"]
    context_provides = ["context.report.meta"]
    context_mutates = ["context.cache.memo"]
    context_cache = ["context.cache.memo"]
    context_notes = ["One-line contract notes"]
    use_when = ["When to use this component"]
    minimal_wiring = ["from ... import ...", "solver.add_plugin(...)"]
    required_companions = ["suite.xxx"]
    config_keys = ["weight", "threshold"]
    example_entry = "examples/demo.py:build_solver"
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
                    tags=_coerce_str_tuple(item.get("tags", ())),
                    summary=str(item.get("summary", "")).strip(),
                    companions=_coerce_str_tuple(item.get("companions", ())),
                    context_requires=_coerce_str_tuple(item.get("context_requires", ())),
                    context_provides=_coerce_str_tuple(item.get("context_provides", ())),
                    context_mutates=_coerce_str_tuple(item.get("context_mutates", ())),
                    context_cache=_coerce_str_tuple(item.get("context_cache", ())),
                    context_notes=_coerce_str_tuple(item.get("context_notes", ())),
                    use_when=_coerce_str_tuple(item.get("use_when", ())),
                    minimal_wiring=_coerce_str_tuple(item.get("minimal_wiring", ())),
                    required_companions=_coerce_str_tuple(item.get("required_companions", ())),
                    config_keys=_coerce_str_tuple(item.get("config_keys", ())),
                    example_entry=str(item.get("example_entry", "")).strip(),
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
        from .usage import enrich_context_contracts, enrich_usage_contracts

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
        enriched = enrich_context_contracts(list(merged.values()), kinds=("plugin",))
        enriched = enrich_usage_contracts(enriched)
        _CATALOG = Catalog(enriched)
    return _CATALOG
