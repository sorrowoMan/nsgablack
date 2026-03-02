"""
优化求解器插件系统。

提供可插拔的扩展能力，包括：
- 精英保留策略
- 多样性初始化
- 收敛检测
- 内存优化

设计原则：
1. 核心求解器保持简洁
2. 高级能力通过插件接入
3. 用户按需选择与组合
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
from .evaluation.numerical_solver_base import (
    NumericalSolverConfig,
    NumericalSolverPlugin,
)
from .evaluation.newton_solver_plugin import (
    NewtonSolverPlugin,
)
from .evaluation.broyden_solver_plugin import (
    BroydenSolverPlugin,
)
from .evaluation.gpu_evaluation_template import (
    GpuEvaluationTemplateConfig,
    GpuEvaluationTemplatePlugin,
)
from .evaluation.evaluation_model import EvaluationModelPlugin, EvaluationModelConfig
from .solver_backends.inner_solver import InnerSolverPlugin, InnerSolverConfig
from .solver_backends.backend_contract import BackendSolveRequest, BackendSolver
from .solver_backends.ngspice_backend import NgspiceBackend, NgspiceBackendConfig
from .solver_backends.contract_bridge import ContractBridgePlugin, BridgeRule
from .solver_backends.timeout_budget import TimeoutBudgetPlugin, TimeoutBudgetConfig
from .runtime.pareto_archive import ParetoArchivePlugin, ParetoArchiveConfig
from .ops.benchmark_harness import BenchmarkHarnessPlugin, BenchmarkHarnessConfig
from .ops.module_report import ModuleReportPlugin, ModuleReportConfig
from .ops.profiler import ProfilerPlugin, ProfilerConfig
from .runtime.dynamic_switch import DynamicSwitchPlugin
from .ops.sensitivity_analysis import SensitivityAnalysisPlugin, SensitivityAnalysisConfig, SensitivityParam
from .ops.otel_tracing import OpenTelemetryTracingPlugin, OpenTelemetryTracingConfig
from .ops.decision_trace import DecisionTracePlugin, DecisionTraceConfig
from .ops.sequence_graph import SequenceGraphPlugin, SequenceGraphConfig
from .models.mas_model import MASModelPlugin, MASModelConfig
from .models.subspace_basis import SubspaceBasisPlugin, SubspaceBasisConfig
from .storage.mysql_run_logger import MySQLRunLoggerPlugin, MySQLRunLoggerConfig
from .system.async_event_hub import AsyncEventHubPlugin, AsyncEventHubConfig
from .system.boundary_guard import BoundaryGuardPlugin, BoundaryGuardConfig
from .system.checkpoint_resume import CheckpointResumePlugin, CheckpointResumeConfig

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
    'NumericalSolverConfig',
    'NumericalSolverPlugin',
    'NewtonSolverPlugin',
    'BroydenSolverPlugin',
    'GpuEvaluationTemplateConfig',
    'GpuEvaluationTemplatePlugin',
    'EvaluationModelPlugin',
    'EvaluationModelConfig',
    'InnerSolverPlugin',
    'InnerSolverConfig',
    'BackendSolveRequest',
    'BackendSolver',
    'NgspiceBackend',
    'NgspiceBackendConfig',
    'ContractBridgePlugin',
    'BridgeRule',
    'TimeoutBudgetPlugin',
    'TimeoutBudgetConfig',
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
    'OpenTelemetryTracingPlugin',
    'OpenTelemetryTracingConfig',
    'DecisionTracePlugin',
    'DecisionTraceConfig',
    'SequenceGraphPlugin',
    'SequenceGraphConfig',
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
    'CheckpointResumePlugin',
    'CheckpointResumeConfig',
]

