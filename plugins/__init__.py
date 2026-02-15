"""
优化求解器插件系�?

提供可插拔的扩展功能，包括：
- 精英保留策略
- 多样性初始化
- 收敛检�?
- 内存优化

设计原则�?
1. 核心求解器保持简�?
2. 高级特性作为插件提�?
3. 用户按需选择和组�?
"""

from .base import Plugin, PluginManager
from .runtime.elite_retention import BasicElitePlugin, HistoricalElitePlugin
from .runtime.diversity_init import DiversityInitPlugin
from .runtime.convergence import ConvergencePlugin
from .system.memory_optimize import MemoryPlugin
from .runtime.adaptive_parameters import AdaptiveParametersPlugin
from .evaluation.surrogate_evaluation import SurrogateEvaluationPlugin, SurrogateEvaluationConfig
from .evaluation.multi_fidelity_evaluation import MultiFidelityEvaluationPlugin, MultiFidelityEvaluationConfig
from .evaluation.monte_carlo_evaluation import MonteCarloEvaluationPlugin, MonteCarloEvaluationConfig
from .runtime.pareto_archive import ParetoArchivePlugin, ParetoArchiveConfig
from .ops.benchmark_harness import BenchmarkHarnessPlugin, BenchmarkHarnessConfig
from .ops.module_report import ModuleReportPlugin, ModuleReportConfig
from .ops.profiler import ProfilerPlugin, ProfilerConfig
from .runtime.dynamic_switch import DynamicSwitchPlugin
from .ops.sensitivity_analysis import SensitivityAnalysisPlugin, SensitivityAnalysisConfig, SensitivityParam
from .models.mas_model import MASModelPlugin, MASModelConfig
from .models.subspace_basis import SubspaceBasisPlugin, SubspaceBasisConfig
from .storage.mysql_run_logger import MySQLRunLoggerPlugin, MySQLRunLoggerConfig
from .system.async_event_hub import AsyncEventHubPlugin, AsyncEventHubConfig
from .system.boundary_guard import BoundaryGuardPlugin, BoundaryGuardConfig

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
    'MultiFidelityEvaluationPlugin',
    'MultiFidelityEvaluationConfig',
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
    'DynamicSwitchPlugin',
    'SensitivityAnalysisPlugin',
    'SensitivityAnalysisConfig',
    'SensitivityParam',
    'MASModelPlugin',
    'MASModelConfig',
    'SubspaceBasisPlugin',
    'SubspaceBasisConfig',
    'MySQLRunLoggerPlugin',
    'MySQLRunLoggerConfig',
    'AsyncEventHubPlugin',
    'AsyncEventHubConfig',
    'BoundaryGuardPlugin',
    'BoundaryGuardConfig',
]

