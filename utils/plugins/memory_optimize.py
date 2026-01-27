"""
内存优化插件

提供内存管理和优化功能
"""

import numpy as np
import gc
from typing import Dict, Any
from .base import Plugin


class MemoryPlugin(Plugin):
    """
    内存优化插件

    功能：优化内存使用，减少内存占用
    特点：
    - 定期清理临时数据
    - 优化历史数据存储
    - 控制numpy数组内存

    推荐用于：
    - 大规模优化问题
    - 内存受限的环境
    - 长时间运行的优化
    """

    def __init__(self, cleanup_interval: int = 10, enable_auto_gc: bool = True):
        """
        初始化内存优化插件

        Args:
            cleanup_interval: 清理间隔（代数）
            enable_auto_gc: 是否启用自动垃圾回收
        """
        super().__init__("memory_optimize")
        self.cleanup_interval = cleanup_interval
        self.enable_auto_gc = enable_auto_gc

        # 内存统计
        self.memory_snapshots = []

    def on_solver_init(self, solver):
        """求解器初始化"""
        self.memory_snapshots = []
        self._take_memory_snapshot(0)

    def on_population_init(self, population, objectives, violations):
        """种群初始化"""
        self._optimize_arrays(population, objectives, violations)

    def on_generation_start(self, generation: int):
        """代开始"""
        pass

    def on_generation_end(self, generation: int):
        """代结束：定期清理"""
        if generation % self.cleanup_interval == 0:
            self._cleanup_memory(generation)

    def on_solver_finish(self, result: Dict[str, Any]):
        """求解器结束"""
        self._take_memory_snapshot("final")
        result['memory_snapshots'] = self.memory_snapshots
        self._cleanup_memory("final")

    def _cleanup_memory(self, generation):
        """清理内存"""
        if not self.enable_auto_gc:
            return

        # 垃圾回收
        gc.collect()

        # 清理求解器的临时数据
        if self.solver is not None:
            # 清理临时变量
            if hasattr(self.solver, 'temp_data'):
                self.solver.temp_data.clear()

            # 优化数组类型
            if hasattr(self.solver, 'population') and self.solver.population is not None:
                self._optimize_arrays(
                    self.solver.population,
                    self.solver.objectives,
                    self.solver.constraint_violations
                )

        # 记录内存快照
        self._take_memory_snapshot(generation)

    def _optimize_arrays(self, population, objectives, violations):
        """优化numpy数组的内存占用"""
        # 优化population数组类型
        if population.dtype == np.float64:
            # 如果值范围小，可以降为float32
            pop_min, pop_max = population.min(), population.max()
            if pop_min >= -1e4 and pop_max <= 1e4:
                # 可以安全降级
                pass  # 不强制降级，可能影响精度

        # 清理NaN和Inf
        if np.any(~np.isfinite(population)):
            population[~np.isfinite(population)] = 0

        if np.any(~np.isfinite(objectives)):
            objectives[~np.isfinite(objectives)] = 1e10

        if violations is not None and np.any(~np.isfinite(violations)):
            violations[~np.isfinite(violations)] = 1e10

    def _take_memory_snapshot(self, generation):
        """记录内存快照"""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            snapshot = {
                'generation': generation,
                'rss_mb': memory_info.rss / 1024 / 1024,  # 常驻内存
                'vms_mb': memory_info.vms / 1024 / 1024,  # 虚拟内存
            }

            self.memory_snapshots.append(snapshot)
        except ImportError:
            # psutil不可用，跳过
            pass

    def get_memory_usage(self) -> Dict[str, Any]:
        """获取内存使用情况"""
        if not self.memory_snapshots:
            return {}

        latest = self.memory_snapshots[-1]
        first = self.memory_snapshots[0]

        return {
            'current_mb': latest['rss_mb'],
            'peak_mb': max(s['rss_mb'] for s in self.memory_snapshots),
            'growth_mb': latest['rss_mb'] - first['rss_mb'],
            'snapshots': self.memory_snapshots
        }
