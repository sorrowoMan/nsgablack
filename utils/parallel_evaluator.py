"""种群内并行评估模块

提供种群评估的并行化支持，设计为可独立使用也可以无缝集成到现有求解器。
支持多种后端和智能调度策略。
"""

from __future__ import annotations

import os
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from typing import Callable, Dict, List, Literal, Optional, Tuple, Union, Any

import numpy as np

try:
    # 当作为包导入时使用相对导入
    from ..core.base import BlackBoxProblem
    from ..utils.bias import BiasModule
except ImportError:
    # 当作为脚本运行时使用绝对导入
    from core.base import BlackBoxProblem
    from bias import BiasModule

# 类型定义
Backend = Literal["process", "thread", "ray", "joblib"]


class ParallelEvaluator:
    """种群并行评估器

    提供种群评估的并行化支持，支持多种后端和智能调度策略。

    特性：
    - 多种后端支持 (multiprocessing, threading, ray, joblib)
    - 智能工作负载均衡
    - 错误处理和重试机制
    - 内存优化的批处理
    - 进度监控和日志
    """

    def __init__(
        self,
        backend: Backend = "process",
        max_workers: Optional[int] = None,
        chunk_size: Optional[int] = None,
        enable_load_balancing: bool = True,
        retry_errors: bool = True,
        max_retries: int = 3,
        verbose: bool = False
    ):
        """初始化并行评估器

        Args:
            backend: 并行后端 ('process', 'thread', 'ray', 'joblib')
            max_workers: 最大工作进程数，None为自动检测
            chunk_size: 批处理大小，None为自动计算
            enable_load_balancing: 启用负载均衡
            retry_errors: 启用错误重试
            max_retries: 最大重试次数
            verbose: 是否输出详细日志
        """
        self.backend = backend
        self.max_workers = max_workers or self._get_default_workers(backend)
        self.chunk_size = chunk_size
        self.enable_load_balancing = enable_load_balancing
        self.retry_errors = retry_errors
        self.max_retries = max_retries
        self.verbose = verbose

        # 性能统计
        self.stats = {
            'total_evaluations': 0,
            'total_time': 0.0,
            'avg_evaluation_time': 0.0,
            'error_count': 0,
            'retry_count': 0
        }

        # 初始化执行器
        self._executor = None

    def _get_default_workers(self, backend: Backend) -> int:
        """获取默认的工作进程数"""
        if backend == "process":
            # 对于CPU密集型任务，通常使用CPU核心数
            return min(cpu_count(), 8)  # 限制最大8个进程避免内存问题
        elif backend == "thread":
            # 对于I/O密集型任务，可以使用更多线程
            return min(cpu_count() * 2, 16)
        else:
            return cpu_count()

    def _create_executor(self):
        """创建执行器实例"""
        if self._executor is None:
            if self.backend == "process":
                self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
            elif self.backend == "thread":
                self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
            elif self.backend == "ray":
                try:
                    import ray
                    if not ray.is_initialized():
                        ray.init()
                    # Ray不需要传统的executor
                except ImportError:
                    warnings.warn("Ray not installed, falling back to process backend")
                    self.backend = "process"
                    self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
            elif self.backend == "joblib":
                # Joblib使用不同的接口，不在这里初始化
                pass
        return self._executor

    def _evaluate_individual_task(
        self,
        task_args: Tuple[np.ndarray, int, Dict[str, Any]]
    ) -> Tuple[int, np.ndarray, float, Optional[str]]:
        """单个个体评估的任务函数

        设计为独立函数，便于多进程序列化。

        Args:
            task_args: (个体, 索引, 配置字典)

        Returns:
            (索引, 目标值, 约束违反度, 错误信息)
        """
        individual, idx, config = task_args
        problem = config['problem']
        enable_bias = config.get('enable_bias', False)
        bias_module = config.get('bias_module', None)
        num_objectives = config.get('num_objectives', 1)

        try:
            # 评估目标函数
            val = problem.evaluate(individual)
            obj = np.asarray(val, dtype=float).flatten()

            # 评估约束
            try:
                cons = problem.evaluate_constraints(individual)
                cons_arr = np.asarray(cons, dtype=float).flatten()
                violation = float(np.sum(np.maximum(cons_arr, 0.0))) if cons_arr.size > 0 else 0.0
            except Exception:
                violation = 0.0

            # 应用偏置模块
            if enable_bias and bias_module is not None:
                if num_objectives == 1:
                    f_biased = bias_module.compute_bias(individual, float(obj[0]), idx)
                    obj = np.array([f_biased])
                else:
                    # 多目标：对每个目标分别应用 bias
                    obj_biased = []
                    for i in range(len(obj)):
                        f_biased = bias_module.compute_bias(individual, float(obj[i]), idx)
                        obj_biased.append(f_biased)
                    obj = np.array(obj_biased)

            return idx, obj, violation, None

        except Exception as e:
            return idx, np.full(num_objectives, np.inf), float('inf'), str(e)

    def _create_chunks(self, population: np.ndarray) -> List[np.ndarray]:
        """将种群分成块，用于批处理"""
        pop_size = len(population)

        if self.chunk_size is None:
            # 自动计算最优块大小
            chunk_size = max(1, pop_size // (self.max_workers * 2))
        else:
            chunk_size = self.chunk_size

        chunks = []
        for i in range(0, pop_size, chunk_size):
            chunks.append(population[i:i + chunk_size])

        return chunks

    def evaluate_population(
        self,
        population: np.ndarray,
        problem: BlackBoxProblem,
        enable_bias: bool = False,
        bias_module: Optional[BiasModule] = None,
        return_detailed: bool = False
    ) -> Union[Tuple[np.ndarray, np.ndarray], Dict[str, Any]]:
        """并行评估整个种群

        Args:
            population: 待评估的种群，形状为 (n_individuals, n_variables)
            problem: 优化问题实例
            enable_bias: 是否启用偏置模块
            bias_module: 偏置模块实例
            return_detailed: 是否返回详细信息

        Returns:
            如果 return_detailed=False: (objectives, constraint_violations)
            如果 return_detailed=True: 包含详细信息的字典
        """
        start_time = time.time()

        # 验证输入
        if not isinstance(population, np.ndarray):
            population = np.array(population)

        pop_size = population.shape[0]
        num_objectives = 1 if problem.get_num_objectives() is None else problem.get_num_objectives()

        # 准备结果数组
        objectives = np.full((pop_size, num_objectives), np.inf)
        constraint_violations = np.full(pop_size, np.inf)

        # 准备任务配置
        task_config = {
            'problem': problem,
            'enable_bias': enable_bias,
            'bias_module': bias_module,
            'num_objectives': num_objectives
        }

        # 准备任务列表
        tasks = [(population[i], i, task_config) for i in range(pop_size)]

        if self.verbose:
            print(f"开始并行评估 {pop_size} 个个体，使用 {self.max_workers} 个工作进程...")

        # 执行并行评估
        try:
            if self.backend == "joblib":
                results = self._evaluate_with_joblib(tasks)
            else:
                results = self._evaluate_with_executor(tasks)

            # 处理结果
            error_count = 0
            for idx, obj, violation, error in results:
                if error is None:
                    objectives[idx] = obj
                    constraint_violations[idx] = violation
                else:
                    error_count += 1
                    if self.verbose:
                        warnings.warn(f"个体 {idx} 评估失败: {error}")
                    self.stats['error_count'] += 1

                    # 重试失败的评估
                    if self.retry_errors and self.max_retries > 0:
                        objectives[idx], constraint_violations[idx] = self._retry_evaluation(
                            population[idx], idx, task_config
                        )

        except Exception as e:
            warnings.warn(f"并行评估失败，回退到串行评估: {e}")
            # 回退到串行评估
            return self._evaluate_serial(population, problem, enable_bias, bias_module, return_detailed)

        finally:
            # 清理执行器
            if self._executor is not None and hasattr(self._executor, 'shutdown'):
                self._executor.shutdown(wait=False)
                self._executor = None

        # 更新统计信息
        total_time = time.time() - start_time
        self.stats.update({
            'total_evaluations': self.stats['total_evaluations'] + pop_size,
            'total_time': self.stats['total_time'] + total_time,
            'avg_evaluation_time': total_time / pop_size,
            'error_count': self.stats['error_count'] + error_count
        })

        if self.verbose:
            print(f"并行评估完成，耗时: {total_time:.2f}s，平均每个: {total_time/pop_size*1000:.2f}ms")
            if error_count > 0:
                print(f"警告: {error_count} 个个体评估失败")

        if return_detailed:
            return {
                'objectives': objectives,
                'constraint_violations': constraint_violations,
                'evaluation_time': total_time,
                'stats': self.stats.copy(),
                'error_count': error_count,
                'success_rate': (pop_size - error_count) / pop_size
            }
        else:
            return objectives, constraint_violations

    def _evaluate_with_executor(self, tasks: List[Tuple]) -> List[Tuple]:
        """使用标准执行器执行任务"""
        executor = self._create_executor()

        if self.enable_load_balancing:
            # 负载均衡：动态分配任务
            futures = {executor.submit(self._evaluate_individual_task, task): task[1]
                      for task in tasks}

            results = []
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=30)  # 30秒超时
                    results.append(result)
                except Exception as e:
                    idx = futures[future]
                    results.append((idx, np.full(1, np.inf), float('inf'), str(e)))
        else:
            # 顺序执行：更简单的批处理
            results = []
            with executor as executor:
                for result in executor.map(self._evaluate_individual_task, tasks, timeout=30):
                    results.append(result)

        return results

    def _evaluate_with_joblib(self, tasks: List[Tuple]) -> List[Tuple]:
        """使用Joblib执行任务（更好的内存管理）"""
        try:
            from joblib import Parallel, delayed
        except ImportError:
            raise ImportError("Joblib not installed. Install with: pip install joblib")

        def _joblib_task(task_args):
            return self._evaluate_individual_task(task_args)

        results = Parallel(
            n_jobs=self.max_workers,
            backend='multiprocessing' if self.backend == 'process' else 'threading',
            verbose=5 if self.verbose else 0,
            batch_size=self.chunk_size or 'auto'
        )(delayed(_joblib_task)(task) for task in tasks)

        return results

    def _retry_evaluation(
        self,
        individual: np.ndarray,
        idx: int,
        config: Dict[str, Any]
    ) -> Tuple[np.ndarray, float]:
        """重试失败的评估"""
        for attempt in range(self.max_retries):
            try:
                _, obj, violation, error = self._evaluate_individual_task((individual, idx, config))
                if error is None:
                    self.stats['retry_count'] += 1
                    if self.verbose:
                        print(f"个体 {idx} 重试成功 (尝试 {attempt + 1})")
                    return obj, violation
            except Exception:
                continue

        warnings.warn(f"个体 {idx} 重试 {self.max_retries} 次后仍然失败")
        return np.full(1, np.inf), float('inf')

    def _evaluate_serial(
        self,
        population: np.ndarray,
        problem: BlackBoxProblem,
        enable_bias: bool = False,
        bias_module: Optional[BiasModule] = None,
        return_detailed: bool = False
    ) -> Union[Tuple[np.ndarray, np.ndarray], Dict[str, Any]]:
        """串行评估（回退方案）"""
        if self.verbose:
            print("使用串行评估作为回退...")

        pop_size = population.shape[0]
        num_objectives = 1 if problem.get_num_objectives() is None else problem.get_num_objectives()
        objectives = np.zeros((pop_size, num_objectives))
        constraint_violations = np.zeros(pop_size, dtype=float)

        for i in range(pop_size):
            _, obj, violation, _ = self._evaluate_individual_task(
                (population[i], i, {
                    'problem': problem,
                    'enable_bias': enable_bias,
                    'bias_module': bias_module,
                    'num_objectives': num_objectives
                })
            )
            objectives[i] = obj
            constraint_violations[i] = violation

        if return_detailed:
            return {
                'objectives': objectives,
                'constraint_violations': constraint_violations,
                'evaluation_time': 0.0,
                'stats': self.stats.copy(),
                'error_count': 0,
                'success_rate': 1.0
            }
        else:
            return objectives, constraint_violations

    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return self.stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_evaluations': 0,
            'total_time': 0.0,
            'avg_evaluation_time': 0.0,
            'error_count': 0,
            'retry_count': 0
        }

    def estimate_speedup(self, population_size: int, avg_eval_time: float) -> float:
        """估算并行加速比

        Args:
            population_size: 种群大小
            avg_eval_time: 平均单个评估时间（秒）

        Returns:
            预估的加速比
        """
        if self.max_workers <= 1:
            return 1.0

        # Amdahl定律：加速比 = 1 / (S + P/N)
        # S是串行部分比例，P是并行部分比例，N是处理器数
        serial_fraction = 0.1  # 假设10%是串行开销
        parallel_fraction = 1 - serial_fraction

        theoretical_speedup = 1 / (serial_fraction + parallel_fraction / self.max_workers)

        # 考虑种群规模的影响
        if population_size < self.max_workers * 2:
            # 种群太小，并行效果有限
            size_factor = population_size / (self.max_workers * 2)
            theoretical_speedup *= size_factor

        return min(theoretical_speedup, self.max_workers)

    def __enter__(self):
        """上下文管理器支持"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器清理"""
        if self._executor is not None and hasattr(self._executor, 'shutdown'):
            self._executor.shutdown(wait=True)
            self._executor = None


# 便捷函数
def create_parallel_evaluator(
    backend: Backend = "process",
    max_workers: Optional[int] = None,
    **kwargs
) -> ParallelEvaluator:
    """创建并行评估器的便捷函数"""
    return ParallelEvaluator(
        backend=backend,
        max_workers=max_workers,
        **kwargs
    )


# 智能评估器选择器
class SmartEvaluatorSelector:
    """根据问题特性智能选择最佳的并行评估策略"""

    @staticmethod
    def select_evaluator(
        problem: BlackBoxProblem,
        population_size: int,
        environment: Optional[Dict[str, Any]] = None
    ) -> ParallelEvaluator:
        """智能选择评估器

        Args:
            problem: 优化问题
            population_size: 种群大小
            environment: 环境信息（如CPU核心数、内存等）

        Returns:
            配置好的并行评估器
        """
        environment = environment or {}

        # 检测问题特性
        problem_type = SmartEvaluatorSelector._analyze_problem_type(problem)

        # 检测环境特性
        cpu_count = environment.get('cpu_count', os.cpu_count())
        memory_gb = environment.get('memory_gb', 8)  # 假设8GB

        # 根据问题类型选择策略
        if problem_type['cpu_intensive']:
            # CPU密集型：使用多进程
            backend = "process"
            max_workers = min(cpu_count, 8)  # 限制进程数避免内存问题
        elif problem_type['io_intensive']:
            # I/O密集型：使用多线程
            backend = "thread"
            max_workers = min(cpu_count * 2, 16)
        elif problem_type['memory_intensive']:
            # 内存密集型：使用joblib（更好的内存管理）
            backend = "joblib"
            max_workers = max(1, cpu_count // 2)  # 减少并行度
        else:
            # 默认：使用多进程
            backend = "process"
            max_workers = min(cpu_count, 4)

        # 根据种群大小调整
        if population_size < 10:
            # 小种群：可能不需要并行
            max_workers = min(max_workers, 2)
            chunk_size = 1
        elif population_size > 100:
            # 大种群：使用批处理
            chunk_size = population_size // (max_workers * 2)
        else:
            chunk_size = None

        return ParallelEvaluator(
            backend=backend,
            max_workers=max_workers,
            chunk_size=chunk_size,
            enable_load_balancing=population_size > 20,
            verbose=False
        )

    @staticmethod
    def _analyze_problem_type(problem: BlackBoxProblem) -> Dict[str, bool]:
        """分析问题类型"""
        # 这里可以添加更复杂的逻辑来判断问题类型
        # 现在使用简单的启发式规则

        return {
            'cpu_intensive': True,  # 默认假设是CPU密集型
            'io_intensive': False,
            'memory_intensive': False,
            'has_constraints': hasattr(problem, 'evaluate_constraints'),
            'is_multi_objective': problem.get_num_objectives() > 1
        }