"""
优化求解器插件系统

提供可插拔的扩展功能，包括：
- 精英保留策略
- 多样性初始化
- 收敛检测
- 内存优化

设计原则：
1. 核心求解器保持简洁
2. 高级特性作为插件提供
3. 用户按需选择和组合
"""

from .base import Plugin, PluginManager
from .elite_retention import BasicElitePlugin, HistoricalElitePlugin
from .diversity_init import DiversityInitPlugin
from .convergence import ConvergencePlugin
from .memory_optimize import MemoryPlugin
from .adaptive_parameters import AdaptiveParametersPlugin
from .surrogate_evaluation import SurrogateEvaluationPlugin, SurrogateEvaluationConfig
from .monte_carlo_evaluation import MonteCarloEvaluationPlugin, MonteCarloEvaluationConfig
from .pareto_archive import ParetoArchivePlugin, ParetoArchiveConfig
from .benchmark_harness import BenchmarkHarnessPlugin, BenchmarkHarnessConfig
from .module_report import ModuleReportPlugin, ModuleReportConfig
from .profiler import ProfilerPlugin, ProfilerConfig

__all__ = [
    'Plugin',
    'PluginManager',
    'BasicElitePlugin',
    'HistoricalElitePlugin',
    'DiversityInitPlugin',
    'ConvergencePlugin',
    'MemoryPlugin',
    'AdaptiveParametersPlugin',
    'SurrogateEvaluationPlugin',
    'SurrogateEvaluationConfig',
    'MonteCarloEvaluationPlugin',
    'MonteCarloEvaluationConfig',
    'ParetoArchivePlugin',
    'ParetoArchiveConfig',
    'BenchmarkHarnessPlugin',
    'BenchmarkHarnessConfig',
    'ModuleReportPlugin',
    'ModuleReportConfig',
    'ProfilerPlugin',
    'ProfilerConfig',
]
