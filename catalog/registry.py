from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
import importlib
import os
from pathlib import Path
import pkgutil
import re
import ast

try:  # py>=3.11
    import tomllib as _toml
except Exception:  # pragma: no cover - import fallback
    try:  # py<3.11
        import tomli as _toml
    except Exception:  # pragma: no cover - optional dependency missing
        _toml = None


@dataclass(frozen=True)
class CatalogEntry:
    """A discoverability record for one framework component."""

    key: str
    title: str
    kind: str  # "bias" | "adapter" | "plugin" | "representation" | "suite" | "tool" | "example" | "doc"
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
    # Optional detail sidecar file (index/detail split).
    detail_ref: str = ""

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
        self._detail_entry_cache: Dict[str, CatalogEntry] = {}
        self._detail_file_cache: Dict[str, Dict[str, object]] = {}

    def get(self, key: str) -> Optional[CatalogEntry]:
        entry = self._by_key.get(key)
        if entry is None:
            return None
        return self._hydrate_entry(entry)

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
            target = e
            if field in ("context", "usage") or use_context_in_all or use_usage_in_all:
                target = self._hydrate_entry(e)
            if field == "name":
                hay = " ".join([target.key, target.title]).lower()
            elif field == "tag":
                hay = " ".join(target.tags).lower()
            elif field == "context":
                hay = self._entry_context_blob(target)
            elif field == "usage":
                hay = self._entry_usage_blob(target)
            else:
                hay = " ".join([target.key, target.title, target.kind, target.summary, " ".join(target.tags)]).lower()
                if use_context_in_all:
                    hay = f"{hay} {self._entry_context_blob(target)}"
                if use_usage_in_all:
                    hay = f"{hay} {self._entry_usage_blob(target)}"
            return all(any(t in hay for t in group) for group in token_groups)

        out = [e for e in self._entries if match(e)]

        # keep stable-ish grouping by kind and key
        def rank(e: CatalogEntry) -> Tuple[int, str]:
            kind_order = {
                "adapter": 0,
                "plugin": 1,
                "bias": 2,
                "representation": 3,
                "tool": 4,
                "doc": 5,
                "example": 6,
            }
            return (int(kind_order.get(e.kind, 99)), e.key)

        out.sort(key=rank)
        return out[: max(0, int(limit))]

    def _hydrate_entry(self, entry: CatalogEntry) -> CatalogEntry:
        if not entry.detail_ref:
            return entry
        cached = self._detail_entry_cache.get(entry.key)
        if cached is not None:
            return cached
        payload = self._load_detail_payload(entry.detail_ref)
        if not payload:
            self._detail_entry_cache[entry.key] = entry
            return entry
        merged = replace(
            entry,
            summary=str(payload.get("summary", entry.summary) or entry.summary),
            companions=_coerce_str_tuple(payload.get("companions", entry.companions)),
            context_requires=_coerce_str_tuple(payload.get("context_requires", entry.context_requires)),
            context_provides=_coerce_str_tuple(payload.get("context_provides", entry.context_provides)),
            context_mutates=_coerce_str_tuple(payload.get("context_mutates", entry.context_mutates)),
            context_cache=_coerce_str_tuple(payload.get("context_cache", entry.context_cache)),
            context_notes=_coerce_str_tuple(payload.get("context_notes", entry.context_notes)),
            use_when=_coerce_str_tuple(payload.get("use_when", entry.use_when)),
            minimal_wiring=_coerce_str_tuple(payload.get("minimal_wiring", entry.minimal_wiring)),
            required_companions=_coerce_str_tuple(payload.get("required_companions", entry.required_companions)),
            config_keys=_coerce_str_tuple(payload.get("config_keys", entry.config_keys)),
            example_entry=str(payload.get("example_entry", entry.example_entry) or entry.example_entry),
        )
        self._detail_entry_cache[entry.key] = merged
        self._by_key[entry.key] = merged
        return merged

    def _load_detail_payload(self, detail_ref: str) -> Dict[str, object]:
        ref = str(detail_ref or "").strip()
        if not ref:
            return {}
        cached = self._detail_file_cache.get(ref)
        if cached is not None:
            return cached
        path = Path(ref)
        if not path.exists() or not path.is_file():
            self._detail_file_cache[ref] = {}
            return {}
        payload: Dict[str, object] = {}
        if path.suffix.lower() == ".toml" and _toml is not None:
            try:
                data = _toml.loads(path.read_text(encoding="utf-8", errors="replace"))
                if isinstance(data, dict):
                    detail_block = data.get("detail")
                    if isinstance(detail_block, dict):
                        payload = detail_block
                    else:
                        payload = data
            except Exception:
                payload = {}
        self._detail_file_cache[ref] = payload if isinstance(payload, dict) else {}
        return self._detail_file_cache[ref]

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


def _parse_literal_fallback(raw: str) -> object:
    text = str(raw).strip()
    if not text:
        return ""
    try:
        return ast.literal_eval(text)
    except Exception:
        pass
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    return text


def _parse_entry_block_fallback(block: str) -> Dict[str, object]:
    out: Dict[str, object] = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value.startswith("["):
            bracket = value.count("[") - value.count("]")
            while bracket > 0 and i < len(lines):
                nxt = lines[i].strip()
                i += 1
                value = f"{value}\n{nxt}"
                bracket += nxt.count("[") - nxt.count("]")
        out[key] = _parse_literal_fallback(value)
    return out


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
            title="EvolutionSolver",
            kind="tool",
            import_path="nsgablack.core.evolution_solver:EvolutionSolver",
            tags=('evolutionary', 'nsga2', 'solver'),
            summary="进化求解器：进化范式的求解器实现。 / Tool: EvolutionSolver.",
            use_when=(
                '需要在流程装配或诊断中用到该工具时 / Need this utility/tool in workflow assembly or diagnostics.',
            ),
            minimal_wiring=(
                'from nsgablack.core.evolution_solver import EvolutionSolver',
                'EvolutionSolver()',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search nsga2 --kind example',
        ),
        CatalogEntry(
            key="solver.blank",
            title="SolverBase",
            kind="tool",
            import_path="nsgablack.core.blank_solver:SolverBase",
            tags=('base', 'blank', 'solver'),
            summary="求解器基类：生命周期与插件调度控制平面。 / Tool: SolverBase.",
            use_when=(
                '需要在流程装配或诊断中用到该工具时 / Need this utility/tool in workflow assembly or diagnostics.',
            ),
            minimal_wiring=(
                'from nsgablack.core.blank_solver import SolverBase',
                'SolverBase()',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search blank --kind example',
        ),
        CatalogEntry(
            key="solver.composable",
            title="ComposableSolver",
            kind="tool",
            import_path="nsgablack.core.composable_solver:ComposableSolver",
            tags=('adapter', 'composition', 'solver'),
            summary="可组合求解器：将策略适配器与表示管线解耦组合。 / Tool: ComposableSolver.",
            use_when=(
                '需要在流程装配或诊断中用到该工具时 / Need this utility/tool in workflow assembly or diagnostics.',
            ),
            minimal_wiring=(
                'from nsgablack.core.composable_solver import ComposableSolver',
                'ComposableSolver()',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search composable --kind example',
        ),
        # --- Adapters ---
        CatalogEntry(
            key="adapter.vns",
            title="VNSAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:VNSAdapter",
            tags=('adapter', 'core', 'local_search', 'refinement', 'stage', 'strategy', 'vns'),
            summary="VNS局部搜索内核：多邻域分阶段精修。 / Adapter: VNS local search core with multi-neighborhood refinement.",
            companions=("repr.context_gaussian", "repr.context_switch"),
            use_when=(
                "需要以局部精修为主，并可逐步扩大/切换邻域时",
                "希望用少量评估预算做稳定改进时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import VNSAdapter",
                "solver.set_adapter(VNSAdapter())",
            ),
            required_companions=("repr.context_gaussian",),
            config_keys=("batch_size", "sigma", "k_max", "n_iter"),
            example_entry="examples/trust_region_subspace_frontier_demo.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.sa",
            title="SimulatedAnnealingAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:SimulatedAnnealingAdapter",
            tags=('adapter', 'core', 'local_search', 'sa', 'simulated_annealing', 'strategy'),
            summary="模拟退火内核：温度调度 + Metropolis接受。 / Adapter: SA core with temperature schedule and Metropolis acceptance.",
            companions=("repr.context_gaussian",),
            use_when=(
                "需要允许小概率接受劣解以跳出局部最优时",
                "希望通过温度控制探索-收敛节奏时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import SimulatedAnnealingAdapter",
                "solver.set_adapter(SimulatedAnnealingAdapter())",
            ),
            required_companions=("repr.context_gaussian",),
            config_keys=("batch_size", "initial_temperature", "cooling_rate", "min_temperature"),
            example_entry="examples/trust_region_subspace_frontier_demo.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.multi_strategy",
            title="StrategyRouterAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:StrategyRouterAdapter",
            tags=('adapter', 'controller', 'cooperation', 'core', 'multi_strategy', 'parallel', 'roles', 'strategy'),
            summary="多策略控制器：在一次优化循环中组合多个策略单元。 / Adapter: multi-strategy controller for composing multiple strategy units in one optimization loop.",
            companions=("plugin.pareto_archive",),
            use_when=(
                "需要编排多个策略单元并共享状态、支持自适应权重时",
                "需要将多个 adapter 组合为同一运行回路时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import StrategyRouterAdapter",
                "solver.set_adapter(StrategyRouterAdapter(...))",
            ),
            required_companions=("plugin.pareto_archive",),
            config_keys=("roles", "total_batch_size", "phase_schedule", "seed"),
            example_entry="examples/dynamic_multi_strategy_demo.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.moead",
            title="MOEADAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:MOEADAdapter",
            tags=('adapter', 'core', 'decomposition', 'moead', 'multiobjective', 'strategy'),
            summary="MOEA/D分解内核：权重向量 + 邻域替换。 / Adapter: MOEA/D decomposition core with weight vectors and neighborhood replacement.",
            companions=("plugin.pareto_archive",),
            use_when=(
                "多目标问题希望用分解子问题并行推进时",
                "需要稳定的邻域协同更新而非全局排序时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import MOEADAdapter",
                "solver.set_adapter(MOEADAdapter())",
            ),
            required_companions=("plugin.pareto_archive",),
            config_keys=("n_subproblems", "neighbor_size", "decomposition", "seed"),
            example_entry="examples/moead_demo.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.nsga2",
            title="NSGA2Adapter",
            kind="adapter",
            import_path="nsgablack.adapters:NSGA2Adapter",
            tags=('adapter', 'core', 'evolutionary', 'multiobjective', 'nsga2', 'strategy'),
            summary="适配器：NSGA-II 非支配排序与拥挤度选择。 / Adapter: NSGA-II with non-dominated sorting and crowding selection.",
            use_when=(
                "标准多目标演化基线，需要稳健 Pareto 前沿维护时",
                "希望在收敛与多样性之间取得平衡时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import NSGA2Adapter",
                "solver.set_adapter(NSGA2Adapter())",
            ),
            required_companions=(),
            config_keys=("batch_size", "crossover_rate", "mutation_rate"),
            example_entry="examples/nsga2_solver_demo.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.nsga3",
            title="NSGA3Adapter",
            kind="adapter",
            import_path="nsgablack.adapters:NSGA3Adapter",
            tags=('adapter', 'core', 'evolutionary', 'multiobjective', 'nsga3', 'strategy'),
            summary="适配器：NSGA-III 参考点引导小生境。 / Adapter: NSGA-III with reference-point niching.",
            use_when=(
                "高维多目标（>=3 目标）需要参考点引导覆盖时",
                "希望提升前沿分布均匀性时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import NSGA3Adapter",
                "solver.set_adapter(NSGA3Adapter())",
            ),
            required_companions=(),
            config_keys=("batch_size", "n_reference_points", "crossover_rate", "mutation_rate"),
            example_entry="examples/template_multiobjective_pareto.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.spea2",
            title="SPEA2Adapter",
            kind="adapter",
            import_path="nsgablack.adapters:SPEA2Adapter",
            tags=('adapter', 'core', 'evolutionary', 'multiobjective', 'spea2', 'strategy'),
            summary="适配器：SPEA2 强度+密度适应度。 / Adapter: SPEA2 with strength and density fitness.",
            use_when=(
                "需要精英保留 + 强度密度联合选择时",
                "希望作为 NSGA 系列的对照方法时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import SPEA2Adapter",
                "solver.set_adapter(SPEA2Adapter())",
            ),
            required_companions=(),
            config_keys=("batch_size", "archive_size", "k_neighbor"),
            example_entry="examples/template_multiobjective_pareto.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.de",
            title="DifferentialEvolutionAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:DifferentialEvolutionAdapter",
            tags=('adapter', 'core', 'de', 'differential_evolution', 'evolutionary', 'strategy'),
            summary="适配器：Differential Evolution 贪婪替换。 / Adapter: Differential Evolution with greedy replacement.",
            use_when=(
                "连续变量优化且希望简单稳定的差分变异时",
                "需要快速基线而非复杂控制逻辑时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import DifferentialEvolutionAdapter",
                "solver.set_adapter(DifferentialEvolutionAdapter())",
            ),
            required_companions=(),
            config_keys=("batch_size", "f", "cr", "strategy", "seed"),
            example_entry="examples/template_continuous_constrained.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.pattern_search",
            title="PatternSearchAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:PatternSearchAdapter",
            tags=('adapter', 'core', 'local_search', 'pattern_search', 'strategy'),
            summary="适配器：坐标模式搜索（自适应步长）。 / Adapter: coordinate pattern search with adaptive step size.",
            use_when=(
                "目标不可导或噪声较大，梯度不可用时",
                "需要轻量坐标方向搜索作为局部改进器时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import PatternSearchAdapter",
                "solver.set_adapter(PatternSearchAdapter())",
            ),
            required_companions=(),
            config_keys=("batch_size", "initial_step", "expand_factor", "shrink_factor"),
            example_entry="examples/template_continuous_constrained.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.gradient_descent",
            title="GradientDescentAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:GradientDescentAdapter",
            tags=('adapter', 'core', 'gradient', 'gradient_descent', 'local_search', 'strategy'),
            summary="适配器：有限差分梯度下降局部精修。 / Adapter: finite-difference gradient descent local refinement.",
            use_when=(
                "需要在候选附近做快速局部下降精修时",
                "可以接受有限差分带来的额外评估开销时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import GradientDescentAdapter",
                "solver.set_adapter(GradientDescentAdapter())",
            ),
            required_companions=(),
            config_keys=("batch_size", "learning_rate", "gradient_eps", "max_inner_steps"),
            example_entry="examples/template_continuous_constrained.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.trust_region_dfo",
            title="TrustRegionDFOAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:TrustRegionDFOAdapter",
            tags=('adapter', 'core', 'dfo', 'local_search', 'strategy', 'trust_region'),
            summary="信赖域DFO内核：无梯度局部搜索。 / Adapter: trust-region derivative-free local search.",
            use_when=(
                "目标不可导且需要稳定局部改进时",
                "希望在受控半径内做无梯度精修时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import TrustRegionDFOAdapter",
                "solver.set_adapter(TrustRegionDFOAdapter())",
            ),
            required_companions=(),
            config_keys=("batch_size", "initial_radius", "min_radius", "max_radius"),
            example_entry="examples/trust_region_dfo_demo.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.trust_region_subspace",
            title="TrustRegionSubspaceAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:TrustRegionSubspaceAdapter",
            tags=('adapter', 'core', 'dfo', 'strategy', 'subspace', 'trust_region'),
            summary="子空间/低秩信赖域：适用高维局部搜索。 / Adapter: subspace/low-rank trust-region search for high-D.",
            use_when=(
                "高维变量空间需要降维后再做局部精修时",
                "希望把评估预算聚焦到主导子空间时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import TrustRegionSubspaceAdapter",
                "solver.set_adapter(TrustRegionSubspaceAdapter())",
            ),
            required_companions=(),
            config_keys=(
                "batch_size",
                "subspace_dim",
                "basis_method",
                "min_samples",
                "initial_radius",
                "resample_every",
            ),
            example_entry="examples/trust_region_subspace_demo.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.trust_region_nonsmooth",
            title="TrustRegionNonSmoothAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:TrustRegionNonSmoothAdapter",
            tags=('adapter', 'core', 'local_search', 'nonsmooth', 'strategy', 'trust_region'),
            summary="非光滑信赖域：支持Linf聚合等非光滑目标。 / Adapter: non-smooth trust-region with Linf aggregation.",
            use_when=(
                "目标非光滑或带 max/Linf 类聚合项时",
                "需要比纯随机局部扰动更稳的非光滑精修时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import TrustRegionNonSmoothAdapter",
                "solver.set_adapter(TrustRegionNonSmoothAdapter())",
            ),
            required_companions=(),
            config_keys=("batch_size", "initial_radius", "min_radius", "aggregation"),
            example_entry="examples/trust_region_nonsmooth_demo.py:build_solver",
        ),
        CatalogEntry(
            key="adapter.mas",
            title="MASAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:MASAdapter",
            tags=('adapter', 'core', 'local_search', 'mas', 'strategy', 'surrogate'),
            summary="Model-and-Search：交替建模与搜索。 / Adapter: model-and-search alternating model update + search.",
            use_when=(
                "希望在线更新轻量模型并引导局部搜索时",
                "评估昂贵，想优先在模型建议区域探索时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import MASAdapter",
                "solver.set_adapter(MASAdapter())",
            ),
            required_companions=(),
            config_keys=(
                "batch_size",
                "exploration_ratio",
                "enable_surrogate",
                "surrogate_model_type",
                "surrogate_min_train_samples",
                "surrogate_max_train_samples",
                "surrogate_retrain_every_call",
                "random_seed",
            ),
            example_entry="examples/mas_demo.py:build_solver",
        ),
        # --- Biases (algorithmic) ---
        CatalogEntry(
            key="bias.tabu",
            title="TabuSearchBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.tabu_search:TabuSearchBias",
            tags=('bias', 'memory', 'strategy', 'tabu', 'algorithmic'),
            summary="禁忌搜索偏置：记忆路\u7ebf\u9632\u6b62\u8fd4\u56de\u3002 / Algorithmic bias: tabu memory to avoid cycling.",
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.algorithmic.tabu_search import TabuSearchBias',
                'bias_module.add(TabuSearchBias())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search tabu --kind example',
        ),
        CatalogEntry(
            key="bias.robustness",
            title="RobustnessBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.signal_driven.robustness:RobustnessBias",
            tags=('bias', 'mc', 'robustness', 'signal_driven', 'algorithmic'),
            summary="鲁棒性偏置：针\u5bf9\u6270\u52a8\u7684\u7a33\u5b9a\u6027\u8bc4\u4f30\u3002 / Algorithmic bias: robustness-oriented scoring under perturbations.",
            companions=("plugin.monte_carlo_eval",),
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.algorithmic.signal_driven.robustness import RobustnessBias',
                'bias_module.add(RobustnessBias())',
            ),
            required_companions=(
                'plugin.monte_carlo_eval',
                
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search robustness --kind example',
        ),
        CatalogEntry(
            key="bias.dynamic_penalty",
            title="DynamicPenaltyBias",
            kind="bias",
            import_path="nsgablack.bias.domain.dynamic_penalty:DynamicPenaltyBias",
            tags=('bias', 'constraint', 'domain', 'dynamic', 'penalty', 'schedule'),
            summary="动态惩罚偏置：随违反程度调节惩罚强度。 / Domain bias: dynamic penalty for constraint violation.",
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.domain.dynamic_penalty import DynamicPenaltyBias',
                'bias_module.add(DynamicPenaltyBias())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search dynamic_penalty --kind example',
        ),
        
        CatalogEntry(
            key="adapter.trust_region_mo_dfo",
            title="TrustRegionMODFOAdapter",
            kind="adapter",
            import_path="nsgablack.adapters:TrustRegionMODFOAdapter",
            tags=('adapter', 'core', 'dfo', 'multiobjective', 'strategy', 'trust_region'),
            summary="多目标信赖域DFO：权重标度/帕累托精修。 / Adapter: MO trust-region DFO with scalarization.",
            use_when=(
                "多目标问题需要局部信赖域精修并保持 Pareto 导向时",
                "希望把多目标优化与局部 DFO 结合时",
            ),
            minimal_wiring=(
                "from nsgablack.adapters import TrustRegionMODFOAdapter",
                "solver.set_adapter(TrustRegionMODFOAdapter())",
            ),
            required_companions=("plugin.pareto_archive",),
            config_keys=("batch_size", "initial_radius", "scalarization", "weights"),
            example_entry="examples/trust_region_mo_dfo_demo.py:build_solver",
        ),
        
        CatalogEntry(
            key="bias.structure_prior",
            title="StructurePriorBias",
            kind="bias",
            import_path="nsgablack.bias.domain.structure_prior:StructurePriorBias",
            tags=('bias', 'domain', 'prior', 'structure', 'symmetry'),
            summary="结构先验偏置：注入结构/对称偏好。 / Domain bias: structure/symmetry prior.",
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.domain.structure_prior import StructurePriorBias',
                'bias_module.add(StructurePriorBias())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search structure_prior --kind example',
        ),
        
        CatalogEntry(
            key="bias.uncertainty_exploration",
            title="UncertaintyExplorationBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.signal_driven.uncertainty_exploration:UncertaintyExplorationBias",
            tags=('bias', 'exploration', 'signal_driven', 'uncertainty', 'algorithmic'),
            summary="不确\u5b9a\u63a2\u7d22\u504f\u7f6e\uff1a\u4f18\u5148\u9ad8\u4e0d\u786e\u5b9a\u533a\u57df\u3002 / Algorithmic bias: explore high-uncertainty regions.",
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.algorithmic.signal_driven.uncertainty_exploration import UncertaintyExplorationBias',
                'bias_module.add(UncertaintyExplorationBias())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search uncertainty_exploration --kind example',
        ),
        
        CatalogEntry(
            key="bias.risk",
            title="RiskBias",
            kind="bias",
            import_path="nsgablack.bias.domain.risk_bias:RiskBias",
            tags=('bias', 'cvar', 'domain', 'risk', 'worst_case'),
            summary="风险偏置：支持CVaR/最坏情况风险控制。 / Domain bias: risk-aware scoring (CVaR/worst-case).",
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.domain.risk_bias import RiskBias',
                'bias_module.add(RiskBias())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search risk --kind example',
        ),
        # --- Plugins ---
        CatalogEntry(
            key="plugin.monte_carlo_eval",
            title="MonteCarloEvaluationPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.evaluation.monte_carlo_evaluation:MonteCarloEvaluationPlugin",
            tags=('evaluation', 'mc', 'signal'),
            summary="Monte Carlo 评估插件：对候选解做扰动采样评估并写入统计指标。 / Plugin: perturbation-based Monte Carlo evaluation with metrics.",
            companions=("bias.robustness",),
            use_when=(
                '需要记录/审查/并行/评估增强等工程能力时',
            ),
            minimal_wiring=(
                'from nsgablack.plugins.evaluation.monte_carlo_evaluation import MonteCarloEvaluationPlugin',
                'solver.add_plugin(MonteCarloEvaluationPlugin())',
            ),
            required_companions=(
                'bias.robustness',
                
            ),
            config_keys=(
                'name',
                'config',
            ),
            example_entry='python -m nsgablack catalog search monte_carlo_eval --kind example',
        ),
        CatalogEntry(
            key="plugin.pareto_archive",
            title="ParetoArchivePlugin",
            kind="plugin",
            import_path="nsgablack.plugins.runtime.pareto_archive:ParetoArchivePlugin",
            tags=('archive', 'multiobjective', 'pareto'),
            summary="Pareto 归档插件：维护非支配解集并提供共享前沿状态。 / Plugin: maintain non-dominated archive and shared frontier state.",
            companions=("adapter.moead",),
            use_when=(
                '需要记录/审查/并行/评估增强等工程能力时',
            ),
            minimal_wiring=(
                'from nsgablack.plugins.runtime.pareto_archive import ParetoArchivePlugin',
                'solver.add_plugin(ParetoArchivePlugin())',
            ),
            required_companions=(
                'adapter.moead',
                
            ),
            config_keys=(
                'name',
                'config',
            ),
            example_entry='python -m nsgablack catalog search pareto_archive --kind example',
        ),
        CatalogEntry(
            key="plugin.benchmark_harness",
            title="BenchmarkHarnessPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.ops.benchmark_harness:BenchmarkHarnessPlugin",
            tags=('benchmark', 'comparison', 'logging', 'protocol'),
            summary="基准输出插件：统一记录 run 产物与指标口径。 / Plugin: standardized benchmark artifacts and metric protocol.",
            companions=("plugin.module_report",),
            use_when=(
                '需要记录/审查/并行/评估增强等工程能力时',
            ),
            minimal_wiring=(
                'from nsgablack.plugins.ops.benchmark_harness import BenchmarkHarnessPlugin',
                'solver.add_plugin(BenchmarkHarnessPlugin())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                'name',
                'config',
                'priority',
            ),
            example_entry='python -m nsgablack catalog search benchmark_harness --kind example',
        ),
        CatalogEntry(
            key="plugin.module_report",
            title="ModuleReportPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.ops.module_report:ModuleReportPlugin",
            tags=('ablation', 'audit', 'bias', 'report'),
            summary="模块审计插件：记录组件组合、参数与贡献摘要。 / Plugin: module-level audit and contribution report.",
            companions=("plugin.benchmark_harness",),
            use_when=(
                '需要记录/审查/并行/评估增强等工程能力时',
            ),
            minimal_wiring=(
                'from nsgablack.plugins.ops.module_report import ModuleReportPlugin',
                'solver.add_plugin(ModuleReportPlugin())',
            ),
            required_companions=(
                'plugin.benchmark_harness',
            ),
            config_keys=(
                'name',
                'config',
                'priority',
            ),
            example_entry='python -m nsgablack catalog search module_report --kind example',
        ),
        CatalogEntry(
            key="plugin.profiler",
            title="ProfilerPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.ops.profiler:ProfilerPlugin",
            tags=('audit', 'performance', 'profile', 'throughput'),
            summary="性能剖析插件：统计阶段耗时与吞吐。 / Plugin: runtime profiling for stage latency and throughput.",
            companions=("plugin.benchmark_harness", "plugin.module_report"),
            use_when=(
                '需要记录/审查/并行/评估增强等工程能力时',
            ),
            minimal_wiring=(
                'from nsgablack.plugins.ops.profiler import ProfilerPlugin',
                'solver.add_plugin(ProfilerPlugin())',
            ),
            required_companions=(
                'plugin.benchmark_harness',
                'plugin.module_report',
            ),
            config_keys=(
                'name',
                'config',
                'priority',
            ),
            example_entry='python -m nsgablack catalog search profiler --kind example',
        ),
        CatalogEntry(
            key="plugin.surrogate_eval",
            title="SurrogateEvaluationPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.evaluation.surrogate_evaluation:SurrogateEvaluationPlugin",
            tags=('evaluation', 'optional', 'surrogate'),
            summary="代理评估插件：用 surrogate 近似评估并输出不确定度指标。 / Plugin: surrogate-assisted evaluation with uncertainty metrics.",
            use_when=(
                '需要记录/审查/并行/评估增强等工程能力时',
            ),
            minimal_wiring=(
                'from nsgablack.plugins.evaluation.surrogate_evaluation import SurrogateEvaluationPlugin',
                'solver.add_plugin(SurrogateEvaluationPlugin())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                'name',
                'config',
                'model_type',
                'surrogate',
                'online_training',
                'parallel_evaluator',
                'parallel_kwargs',
            ),
            example_entry='python -m nsgablack catalog search surrogate_eval --kind example',
        ),
        
        CatalogEntry(
            key="plugin.multi_fidelity_eval",
            title="MultiFidelityEvaluationPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.evaluation.multi_fidelity_evaluation:MultiFidelityEvaluationPlugin",
            tags=('evaluation', 'frontier', 'multi_fidelity', 'plugin'),
            summary="多保真评估插件：在低/高保真之间分阶段切换。 / Plugin: multi-fidelity evaluation switching between low/high fidelity.",
            use_when=(
                '需要记录/审查/并行/评估增强等工程能力时',
            ),
            minimal_wiring=(
                'from nsgablack.plugins.evaluation.multi_fidelity_evaluation import MultiFidelityEvaluationPlugin',
                'solver.add_plugin(MultiFidelityEvaluationPlugin())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                'name',
                'config',
                'low_fidelity',
            ),
            example_entry='python -m nsgablack catalog search multi_fidelity_eval --kind example',
        ),
        # --- Representation helpers ---
        CatalogEntry(
            key="repr.context_gaussian",
            title="ContextGaussianMutation",
            kind="representation",
            import_path="nsgablack.representation.continuous:ContextGaussianMutation",
            tags=('context', 'continuous', 'mutation', 'vns'),
            summary="表示组件：基于上下文的高斯变异算子。 / Representation: ContextGaussianMutation.",
            companions=("adapter.vns",),
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation.continuous import ContextGaussianMutation',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                'adapter.vns',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search context_gaussian --kind example',
        ),
        CatalogEntry(
            key="repr.context_switch",
            title="ContextSelectMutator",
            kind="representation",
            import_path="nsgablack.representation:ContextSelectMutator",
            tags=('context', 'discrete', 'mutation', 'switch', 'vns'),
            summary="表示组件：基于上下文的变异算子选择器。 / Representation: ContextSelectMutator.",
            companions=("adapter.vns",),
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation import ContextSelectMutator',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                'adapter.vns',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search context_switch --kind example',
        ),
        CatalogEntry(
            key="repr.projection_repair",
            title="ProjectionRepair",
            kind="representation",
            import_path="nsgablack.representation.continuous:ProjectionRepair",
            tags=('bounds', 'pipeline', 'projection', 'repair', 'simplex'),
            summary="表示组件：投影修复，将候选映射回可行域。 / Representation: ProjectionRepair.",
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation.continuous import ProjectionRepair',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search projection_repair --kind example',
        ),
        
        CatalogEntry(
            key="repr.dynamic_repair",
            title="DynamicRepair",
            kind="representation",
            import_path="nsgablack.representation.dynamic:DynamicRepair",
            tags=('dynamic', 'pipeline', 'repair'),
            summary="表示组件：动态修复策略，根据上下文调整修复。 / Representation: DynamicRepair.",
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation.dynamic import DynamicRepair',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search dynamic_repair --kind example',
        ),
        CatalogEntry(
            key="bias.pso",
            title="ParticleSwarmBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.pso:ParticleSwarmBias",
            tags=('algorithmic', 'bias', 'particle_swarm', 'pso', 'strategy', 'swarm'),
            summary="粒子群偏置：惯性/群体吸引引导。 / Algorithmic bias: PSO inertia/social guidance.",
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.algorithmic.pso import ParticleSwarmBias',
                'bias_module.add(ParticleSwarmBias())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search pso --kind example',
        ),
        CatalogEntry(
            key="bias.cmaes",
            title="CMAESBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.cma_es:CMAESBias",
            tags=('algorithmic', 'bias', 'cma-es', 'cmaes', 'covariance', 'strategy'),
            summary="CMA-ES偏置：协方差自适应搜索。 / Algorithmic bias: CMA-ES covariance adaptation.",
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.algorithmic.cma_es import CMAESBias',
                'bias_module.add(CMAESBias())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search cmaes --kind example',
        ),
        CatalogEntry(
            key="bias.levy",
            title="LevyFlightBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.levy_flight:LevyFlightBias",
            tags=('algorithmic', 'bias', 'exploration', 'levy', 'random_walk'),
            summary="Levy飞行偏置：长跳跃探索。 / Algorithmic bias: Levy-flight exploration.",
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.algorithmic.levy_flight import LevyFlightBias',
                'bias_module.add(LevyFlightBias())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search levy --kind example',
        ),
        CatalogEntry(
            key="bias.convergence",
            title="ConvergenceBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.convergence:ConvergenceBias",
            tags=('algorithmic', 'bias', 'convergence', 'exploitation', 'schedule'),
            summary="收敛偏置：优先收敛与精修。 / Algorithmic bias: convergence acceleration.",
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.algorithmic.convergence import ConvergenceBias',
                'bias_module.add(ConvergenceBias())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search convergence --kind example',
        ),
        CatalogEntry(
            key="bias.diversity",
            title="DiversityBias",
            kind="bias",
            import_path="nsgablack.bias.algorithmic.diversity:DiversityBias",
            tags=('algorithmic', 'bias', 'diversity', 'exploration', 'niching'),
            summary="多样性偏置：维持解集分散。 / Algorithmic bias: diversity maintenance.",
            use_when=(
                '需要在不改变硬约束的前提下注入软偏好引导时 / Need to inject soft preference guidance without changing hard constraints.',
            ),
            minimal_wiring=(
                'from nsgablack.bias.algorithmic.diversity import DiversityBias',
                'bias_module.add(DiversityBias())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search diversity --kind example',
        ),

        # --- Plugins (more capabilities) ---
        CatalogEntry(
            key="plugin.elite",
            title="BasicElitePlugin",
            kind="plugin",
            import_path="nsgablack.plugins.runtime.elite_retention:BasicElitePlugin",
            tags=('archive', 'elite', 'plugin'),
            summary="精英保留插件：保留高质量个体，降低退化风险。 / Plugin: elite retention to reduce quality regression.",
            use_when=(
                '需要记录/审查/并行/评估增强等工程能力时',
            ),
            minimal_wiring=(
                'from nsgablack.plugins.runtime.elite_retention import BasicElitePlugin',
                'solver.add_plugin(BasicElitePlugin())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                'retention_prob',
                'retention_ratio',
            ),
            example_entry='python -m nsgablack catalog search elite --kind example',
        ),
        CatalogEntry(
            key="plugin.diversity_init",
            title="DiversityInitPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.runtime.diversity_init:DiversityInitPlugin",
            tags=('diversity', 'init', 'plugin'),
            summary="多样性初始化插件：降低重复、提升初始覆盖。 / Plugin: improve initial population diversity by duplicate/similarity control.",
            use_when=(
                '需要记录/审查/并行/评估增强等工程能力时',
            ),
            minimal_wiring=(
                'from nsgablack.plugins.runtime.diversity_init import DiversityInitPlugin',
                'solver.add_plugin(DiversityInitPlugin())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                'similarity_threshold',
                'rejection_prob',
            ),
            example_entry='python -m nsgablack catalog search diversity_init --kind example',
        ),
        CatalogEntry(
            key="plugin.memory",
            title="MemoryPlugin",
            kind="plugin",
            import_path="nsgablack.plugins.system.memory_optimize:MemoryPlugin",
            tags=('engineering', 'memory', 'plugin'),
            summary="内存优化插件：周期清理临时数据并记录内存指标。 / Plugin: periodic memory cleanup with memory metric snapshots.",
            use_when=(
                '需要记录/审查/并行/评估增强等工程能力时',
            ),
            minimal_wiring=(
                'from nsgablack.plugins.system.memory_optimize import MemoryPlugin',
                'solver.add_plugin(MemoryPlugin())',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                'cleanup_interval',
                'enable_auto_gc',
            ),
            example_entry='python -m nsgablack catalog search memory --kind example',
        ),

        # --- Representation (core presets) ---
        CatalogEntry(
            key="repr.pipeline",
            title="RepresentationPipeline",
            kind="representation",
            import_path="nsgablack.representation:RepresentationPipeline",
            tags=('core', 'pipeline', 'representation'),
            summary="表示管线：初始化/变异/修复的统一执行链。 / Representation: RepresentationPipeline.",
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation import RepresentationPipeline',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search pipeline --kind example',
        ),
        CatalogEntry(
            key="repr.continuous",
            title="UniformInitializer",
            kind="representation",
            import_path="nsgablack.representation.continuous:UniformInitializer",
            tags=('continuous', 'initializer', 'real'),
            summary="表示组件：连续变量均匀初始化器。 / Representation: UniformInitializer.",
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation.continuous import UniformInitializer',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search continuous --kind example',
        ),
        CatalogEntry(
            key="repr.integer",
            title="IntegerInitializer",
            kind="representation",
            import_path="nsgablack.representation.integer:IntegerInitializer",
            tags=('discrete', 'initializer', 'integer'),
            summary="表示组件：整数变量初始化器。 / Representation: IntegerInitializer.",
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation.integer import IntegerInitializer',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search integer --kind example',
        ),
        CatalogEntry(
            key="repr.permutation",
            title="PermutationInitializer",
            kind="representation",
            import_path="nsgablack.representation.permutation:PermutationInitializer",
            tags=('discrete', 'initializer', 'permutation', 'tsp'),
            summary="表示组件：排列初始化器。 / Representation: PermutationInitializer.",
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation.permutation import PermutationInitializer',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search permutation --kind example',
        ),
        CatalogEntry(
            key="repr.binary",
            title="BinaryInitializer",
            kind="representation",
            import_path="nsgablack.representation.binary:BinaryInitializer",
            tags=('binary', 'bit', 'initializer'),
            summary="表示组件：二进制初始化器。 / Representation: BinaryInitializer.",
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation.binary import BinaryInitializer',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search binary --kind example',
        ),
        CatalogEntry(
            key="repr.graph",
            title="GraphEdgeInitializer",
            kind="representation",
            import_path="nsgablack.representation.graph:GraphEdgeInitializer",
            tags=('graph', 'initializer', 'network'),
            summary="表示组件：图边初始化器。 / Representation: GraphEdgeInitializer.",
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation.graph import GraphEdgeInitializer',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search graph --kind example',
        ),
        CatalogEntry(
            key="repr.matrix",
            title="IntegerMatrixInitializer",
            kind="representation",
            import_path="nsgablack.representation.matrix:IntegerMatrixInitializer",
            tags=('grid', 'initializer', 'matrix'),
            summary="表示组件：整数矩阵初始化器。 / Representation: IntegerMatrixInitializer.",
            use_when=(
                '需要接入表示层的初始化/变异/修复行为时 / Need to wire representation initializer/mutator/repair behavior.',
            ),
            minimal_wiring=(
                'from nsgablack.representation.matrix import IntegerMatrixInitializer',
                'Attach this component into RepresentationPipeline as initializer/mutator/repair as appropriate.',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search matrix --kind example',
        ),

        # --- Tools (utilities; discoverable but not part of the solver base) ---
        CatalogEntry(
            key="tool.parallel_evaluator",
            title="ParallelEvaluator",
            kind="tool",
            import_path="nsgablack.utils.parallel:ParallelEvaluator",
            tags=('evaluation', 'parallel', 'tool'),
            summary="工具：并行评估执行器。 / Tool: ParallelEvaluator.",
            use_when=(
                '需要在流程装配或诊断中用到该工具时 / Need this utility/tool in workflow assembly or diagnostics.',
            ),
            minimal_wiring=(
                'from nsgablack.utils.parallel import ParallelEvaluator',
                'ParallelEvaluator()',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search parallel_evaluator --kind example',
        ),
        CatalogEntry(
            key="tool.context_keys",
            title="Context Keys",
            kind="tool",
            import_path="nsgablack.core.state:context_keys",
            tags=('context', 'keys', 'schema', 'tool'),
            summary="工具：Context Keys 规范与索引。 / Tool: Context Keys.",
            use_when=(
                '需要在流程装配或诊断中用到该工具时 / Need this utility/tool in workflow assembly or diagnostics.',
            ),
            minimal_wiring=(
                'from nsgablack.core.state import context_keys',
                'context_keys()',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search context_keys --kind example',
        ),
        CatalogEntry(
            key="tool.context_schema",
            title="MinimalEvaluationContext",
            kind="tool",
            import_path="nsgablack.core.state:MinimalEvaluationContext",
            tags=('context', 'parallel', 'schema', 'tool'),
            summary="工具：最小评估上下文结构。 / Tool: MinimalEvaluationContext.",
            companions=("tool.context_keys",),
            use_when=(
                '需要在流程装配或诊断中用到该工具时 / Need this utility/tool in workflow assembly or diagnostics.',
            ),
            minimal_wiring=(
                'from nsgablack.core.state import MinimalEvaluationContext',
                'MinimalEvaluationContext()',
            ),
            required_companions=(
                'tool.context_keys',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search context_schema --kind example',
        ),
        CatalogEntry(
            key="tool.logging",
            title="configure_logging",
            kind="tool",
            import_path="nsgablack.utils.engineering:configure_logging",
            tags=('engineering', 'logging', 'tool'),
            summary="工具：日志配置入口。 / Tool: configure_logging.",
            use_when=(
                '需要在流程装配或诊断中用到该工具时 / Need this utility/tool in workflow assembly or diagnostics.',
            ),
            minimal_wiring=(
                'from nsgablack.utils.engineering import configure_logging',
                'configure_logging()',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search logging --kind example',
        ),
        CatalogEntry(
            key="tool.metrics",
            title="pareto_filter",
            kind="tool",
            import_path="nsgablack.utils.analysis:pareto_filter",
            tags=('analysis', 'metrics', 'pareto', 'tool'),
            summary="工具：Pareto 过滤器。 / Tool: pareto_filter.",
            use_when=(
                '需要在流程装配或诊断中用到该工具时 / Need this utility/tool in workflow assembly or diagnostics.',
            ),
            minimal_wiring=(
                'from nsgablack.utils.analysis import pareto_filter',
                'pareto_filter()',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='python -m nsgablack catalog search metrics --kind example',
        ),
        # --- Examples (templates / demos) ---
        CatalogEntry(
            key="example.template_continuous",
            title="template_continuous_constrained",
            kind="example",
            import_path="nsgablack.examples_registry:template_continuous_constrained",
            tags=('bias', 'constraint', 'continuous', 'example', 'pipeline', 'template'),
            summary="示例：连续变量约束优化模板。 / Example: template_continuous_constrained.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import template_continuous_constrained',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\template_continuous_constrained.py:build_solver',
        ),
        CatalogEntry(
            key="example.template_knapsack",
            title="template_knapsack_binary",
            kind="example",
            import_path="nsgablack.examples_registry:template_knapsack_binary",
            tags=('binary', 'example', 'knapsack', 'repair', 'template'),
            summary="示例：背包问题（二进制）模板。 / Example: template_knapsack_binary.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import template_knapsack_binary',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\template_knapsack_binary.py:build_solver',
        ),
        CatalogEntry(
            key="example.template_tsp",
            title="template_tsp_permutation",
            kind="example",
            import_path="nsgablack.examples_registry:template_tsp_permutation",
            tags=('2opt', 'example', 'permutation', 'template', 'tsp'),
            summary="示例：TSP（排列表示）模板。 / Example: template_tsp_permutation.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import template_tsp_permutation',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\template_tsp_permutation.py:build_solver',
        ),
        CatalogEntry(
            key="example.template_graph_path",
            title="template_graph_path",
            kind="example",
            import_path="nsgablack.examples_registry:template_graph_path",
            tags=('example', 'graph', 'path', 'repair', 'template'),
            summary="示例：图路径优化模板。 / Example: template_graph_path.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import template_graph_path',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\template_graph_path.py:build_solver',
        ),
        CatalogEntry(
            key="example.template_assignment",
            title="template_assignment_matrix",
            kind="example",
            import_path="nsgablack.examples_registry:template_assignment_matrix",
            tags=('assignment', 'example', 'matrix', 'repair', 'template'),
            summary="示例：指派问题（矩阵表示）模板。 / Example: template_assignment_matrix.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import template_assignment_matrix',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\template_assignment_matrix.py:build_solver',
        ),
        CatalogEntry(
            key="example.template_production_simple",
            title="template_production_schedule_simple",
            kind="example",
            import_path="nsgablack.examples_registry:template_production_schedule_simple",
            tags=('example', 'matrix', 'production', 'schedule', 'template'),
            summary="示例：简化生产排程模板。 / Example: template_production_schedule_simple.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import template_production_schedule_simple',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\template_production_schedule_simple.py:build_solver',
        ),
        CatalogEntry(
            key="example.template_portfolio",
            title="template_portfolio_pareto",
            kind="example",
            import_path="nsgablack.examples_registry:template_portfolio_pareto",
            tags=('example', 'mo', 'pareto', 'portfolio', 'template'),
            summary="示例：投资组合多目标 Pareto 模板。 / Example: template_portfolio_pareto.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import template_portfolio_pareto',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\template_portfolio_pareto.py:build_solver',
        ),
        CatalogEntry(
            key="example.template_mo_pareto",
            title="template_multiobjective_pareto",
            kind="example",
            import_path="nsgablack.examples_registry:template_multiobjective_pareto",
            tags=('example', 'moead', 'multiobjective', 'pareto', 'template'),
            summary="示例：通用多目标 Pareto 模板。 / Example: template_multiobjective_pareto.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import template_multiobjective_pareto',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\template_multiobjective_pareto.py:build_solver',
        ),
        CatalogEntry(
            key="example.dynamic_multi_strategy",
            title="dynamic_multi_strategy_demo",
            kind="example",
            import_path="nsgablack.examples_registry:dynamic_multi_strategy_demo",
            tags=('demo', 'dynamic', 'example', 'multi_strategy', 'switch'),
            summary="示例：动态多策略协同编排演示。 / Example: dynamic_multi_strategy_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import dynamic_multi_strategy_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\dynamic_multi_strategy_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.trust_region_dfo",
            title="trust_region_dfo_demo",
            kind="example",
            import_path="nsgablack.examples_registry:trust_region_dfo_demo",
            tags=('demo', 'dfo', 'example', 'trust_region'),
            summary="示例：信赖域 DFO 演示。 / Example: trust_region_dfo_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import trust_region_dfo_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\trust_region_dfo_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.trust_region_subspace",
            title="trust_region_subspace_demo",
            kind="example",
            import_path="nsgablack.examples_registry:trust_region_subspace_demo",
            tags=('demo', 'example', 'subspace', 'trust_region'),
            summary="示例：子空间/低秩信赖域演示。 / Example: trust_region_subspace_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import trust_region_subspace_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\trust_region_subspace_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.monte_carlo_robust",
            title="monte_carlo_dp_robust_demo",
            kind="example",
            import_path="nsgablack.examples_registry:monte_carlo_dp_robust_demo",
            tags=('demo', 'example', 'monte_carlo', 'robust'),
            summary="示例：Monte Carlo 鲁棒评估演示。 / Example: monte_carlo_dp_robust_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import monte_carlo_dp_robust_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\monte_carlo_dp_robust_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.surrogate_plugin",
            title="surrogate_plugin_demo",
            kind="example",
            import_path="nsgablack.examples_registry:surrogate_plugin_demo",
            tags=('demo', 'example', 'plugin', 'surrogate'),
            summary="示例：代理评估插件演示。 / Example: surrogate_plugin_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import surrogate_plugin_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\surrogate_plugin_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.multi_fidelity",
            title="multi_fidelity_demo",
            kind="example",
            import_path="nsgablack.examples_registry:multi_fidelity_demo",
            tags=('demo', 'example', 'multi_fidelity'),
            summary="示例：多保真评估演示。 / Example: multi_fidelity_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import multi_fidelity_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\multi_fidelity_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.risk_bias",
            title="risk_bias_demo",
            kind="example",
            import_path="nsgablack.examples_registry:risk_bias_demo",
            tags=('bias', 'demo', 'example', 'risk'),
            summary="示例：风险偏置演示。 / Example: risk_bias_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import risk_bias_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\risk_bias_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.bias_gallery",
            title="bias_gallery_demo",
            kind="example",
            import_path="nsgablack.examples_registry:bias_gallery_demo",
            tags=('bias', 'demo', 'example', 'gallery'),
            summary="示例：偏置组件集合演示。 / Example: bias_gallery_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import bias_gallery_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\bias_gallery_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.plugin_gallery",
            title="plugin_gallery_demo",
            kind="example",
            import_path="nsgablack.examples_registry:plugin_gallery_demo",
            tags=('demo', 'example', 'gallery', 'plugin'),
            summary="示例：插件组合演示。 / Example: plugin_gallery_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import plugin_gallery_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\plugin_gallery_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.role_adapters",
            title="role_adapters_demo",
            kind="example",
            import_path="nsgablack.examples_registry:role_adapters_demo",
            tags=('adapter', 'demo', 'example', 'multi_role', 'role'),
            summary="示例：角色适配器协同演示。 / Example: role_adapters_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import role_adapters_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\role_adapters_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.astar",
            title="astar_demo",
            kind="example",
            import_path="nsgablack.examples_registry:astar_demo",
            tags=('astar', 'demo', 'example', 'graph', 'search'),
            summary="示例：A* 搜索演示。 / Example: astar_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import astar_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\astar_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.moa_star",
            title="moa_star_demo",
            kind="example",
            import_path="nsgablack.examples_registry:moa_star_demo",
            tags=('demo', 'example', 'moa_star', 'pareto', 'search'),
            summary="示例：多目标 A*（MOA*）演示。 / Example: moa_star_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import moa_star_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\moa_star_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.parallel_repair",
            title="parallel_repair_demo",
            kind="example",
            import_path="nsgablack.examples_registry:parallel_repair_demo",
            tags=('demo', 'example', 'parallel', 'pipeline', 'repair'),
            summary="示例：并行修复演示。 / Example: parallel_repair_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import parallel_repair_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\parallel_repair_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.nsga2_solver",
            title="nsga2_solver_demo",
            kind="example",
            import_path="nsgablack.examples_registry:nsga2_solver_demo",
            tags=('demo', 'example', 'nsga2', 'solver', 'suite'),
            summary="示例：NSGA-II 求解器演示。 / Example: nsga2_solver_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import nsga2_solver_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\nsga2_solver_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.parallel_evaluator",
            title="parallel_evaluator_demo",
            kind="example",
            import_path="nsgablack.examples_registry:parallel_evaluator_demo",
            tags=('demo', 'evaluation', 'example', 'parallel'),
            summary="示例：并行评估器演示。 / Example: parallel_evaluator_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import parallel_evaluator_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\parallel_evaluator_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.context_keys",
            title="context_keys_demo",
            kind="example",
            import_path="nsgablack.examples_registry:context_keys_demo",
            tags=('context', 'demo', 'example', 'keys'),
            summary="示例：Context Keys 使用演示。 / Example: context_keys_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import context_keys_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\context_keys_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.context_schema",
            title="context_schema_demo",
            kind="example",
            import_path="nsgablack.examples_registry:context_schema_demo",
            tags=('context', 'demo', 'example', 'schema'),
            summary="示例：Context Schema 使用演示。 / Example: context_schema_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import context_schema_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\context_schema_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.logging",
            title="logging_demo",
            kind="example",
            import_path="nsgablack.examples_registry:logging_demo",
            tags=('demo', 'example', 'logging', 'tool'),
            summary="示例：日志配置演示。 / Example: logging_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import logging_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\logging_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.metrics",
            title="metrics_demo",
            kind="example",
            import_path="nsgablack.examples_registry:metrics_demo",
            tags=('demo', 'example', 'metrics', 'pareto'),
            summary="示例：指标统计/比较演示。 / Example: metrics_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import metrics_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\metrics_demo.py:build_solver',
        ),
        CatalogEntry(
            key="example.dynamic_cli_signal",
            title="dynamic_cli_signal_demo",
            kind="example",
            import_path="nsgablack.examples_registry:dynamic_cli_signal_demo",
            tags=('cli', 'demo', 'dynamic', 'example', 'signal'),
            summary="示例：动态 CLI 信号演示。 / Example: dynamic_cli_signal_demo.",
            use_when=(
                '需要可运行参考实现时',
            ),
            minimal_wiring=(
                'from nsgablack.examples_registry import dynamic_cli_signal_demo',
            ),
            required_companions=(
                '(none)',
            ),
            config_keys=(
                '(none)',
            ),
            example_entry='C:\\Users\\hp\\Desktop\\代码逻辑 - 副本\\nsgablack\\examples\\dynamic_cli_signal_demo.py:build_solver',
        ),
    ]


_CATALOG_BY_PROFILE: Dict[str, Catalog] = {}


def _normalize_catalog_profile(profile: Optional[str]) -> str:
    raw = str(profile or os.environ.get("NSGABLACK_CATALOG_PROFILE", "default")).strip().lower()
    if raw in {"framework-core", "framework_core", "core"}:
        return "framework-core"
    return "default"


def _uses_examples_path(text: str) -> bool:
    raw = str(text or "").lower()
    return (
        "examples/" in raw
        or "examples\\" in raw
        or "nsgablack.examples_registry" in raw
    )


def _apply_catalog_profile(entries: Sequence[CatalogEntry], profile: str) -> List[CatalogEntry]:
    normalized = _normalize_catalog_profile(profile)
    if normalized != "framework-core":
        return list(entries)

    out: List[CatalogEntry] = []
    for entry in entries:
        if entry.kind in {"example", "doc"}:
            continue
        if _uses_examples_path(entry.import_path):
            continue
        if _uses_examples_path(entry.example_entry):
            entry = replace(entry, example_entry="")
        out.append(entry)
    return out


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
        "nsgablack.adapters",
        "nsgablack.bias",
        "nsgablack.representation",
        "nsgablack.utils.wiring",
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


class CatalogProvider:
    """Catalog source provider interface."""

    name: str = "provider"

    def load(self) -> List[CatalogEntry]:
        raise NotImplementedError


def _parse_entries_from_toml(path: Path) -> List[CatalogEntry]:
    if _toml is None or not path.exists():
        return []
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    items: List[Dict[str, object]] = []
    try:
        data = _toml.loads(raw_text)
        loaded = data.get("entry", [])
        if isinstance(loaded, list):
            items = [it for it in loaded if isinstance(it, dict)]
    except Exception:
        blocks = raw_text.split("[[entry]]")
        parsed: List[Dict[str, object]] = []
        for block in blocks[1:]:
            item = _parse_entry_block_fallback(block)
            if item:
                parsed.append(item)
        items = parsed
    out: List[CatalogEntry] = []
    for item in items:
        detail_ref = str(item.get("detail_ref", "")).strip()
        if not detail_ref:
            detail_ref = str(item.get("details_file", "")).strip()
        if detail_ref:
            detail_path = (path.parent / detail_ref).resolve()
            detail_ref = str(detail_path)
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
                detail_ref=detail_ref,
            )
        )
    return [e for e in out if e.key and e.kind and e.import_path]


def _collect_toml_paths(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("*.toml"))
    return []


def _load_toml_entries(paths: Sequence[Path]) -> List[CatalogEntry]:
    out: List[CatalogEntry] = []
    for p in paths:
        for toml_path in _collect_toml_paths(p):
            try:
                out.extend(_parse_entries_from_toml(toml_path))
            except Exception:
                continue
    return out


class BuiltinTomlProvider(CatalogProvider):
    """
    Builtin catalog source:
    - catalog/entries.toml
    - catalog/entries/*.toml
    """

    name = "builtin_toml"

    def load(self) -> List[CatalogEntry]:
        return _load_toml_entries(
            [
                Path(__file__).with_name("entries.toml"),
                Path(__file__).with_name("entries"),
            ]
        )


class EnvTomlProvider(CatalogProvider):
    """External catalog from NSGABLACK_CATALOG_PATH (file or directory list)."""

    name = "env_toml"

    def load(self) -> List[CatalogEntry]:
        env = os.environ.get("NSGABLACK_CATALOG_PATH", "").strip()
        if not env:
            return []
        paths: List[Path] = []
        for part in env.split(os.pathsep):
            p = part.strip().strip('"')
            if p:
                paths.append(Path(p))
        return _load_toml_entries(paths)


def _load_external_entries() -> List[CatalogEntry]:
    """Load entries from configured catalog providers."""
    providers: List[CatalogProvider] = [BuiltinTomlProvider(), EnvTomlProvider()]
    try:
        from .store.mysql import mysql_config_enabled, mysql_config_mode
        from .providers.mysql_provider import MySQLCatalogProvider

        if mysql_config_enabled() and mysql_config_mode() != "off":
            providers.append(MySQLCatalogProvider())
    except Exception:
        pass
    out: List[CatalogEntry] = []
    for provider in providers:
        try:
            out.extend(provider.load())
        except Exception:
            continue
    return out


def get_catalog(*, refresh: bool = False, profile: Optional[str] = None) -> Catalog:
    global _CATALOG_BY_PROFILE
    profile_name = _normalize_catalog_profile(profile)
    if refresh or profile_name not in _CATALOG_BY_PROFILE:
        from .usage import enrich_context_contracts, enrich_usage_contracts
        try:
            from .store.mysql import mysql_config_enabled, mysql_config_mode
            from .providers.mysql_provider import MySQLCatalogProvider
        except Exception:
            mysql_config_enabled = None
            mysql_config_mode = None
            MySQLCatalogProvider = None

        if mysql_config_enabled and mysql_config_mode and MySQLCatalogProvider:
            if mysql_config_enabled() and mysql_config_mode() == "only":
                mysql_entries = MySQLCatalogProvider().load()
                profiled_entries = _apply_catalog_profile(list(mysql_entries), profile_name)
                enriched = enrich_context_contracts(
                    profiled_entries,
                    kinds=("plugin", "adapter", "bias", "representation"),
                )
                enriched = enrich_usage_contracts(enriched)
                _CATALOG_BY_PROFILE[profile_name] = Catalog(enriched)
                return _CATALOG_BY_PROFILE[profile_name]

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
        profiled_entries = _apply_catalog_profile(list(merged.values()), profile_name)

        enriched = enrich_context_contracts(
            profiled_entries,
            kinds=("plugin", "adapter", "bias", "representation"),
        )
        enriched = enrich_usage_contracts(enriched)
        _CATALOG_BY_PROFILE[profile_name] = Catalog(enriched)
    return _CATALOG_BY_PROFILE[profile_name]
