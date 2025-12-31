"""
Memory management utilities for optimization algorithms
"""

import gc
import psutil
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
import warnings
from collections import deque
import threading
import time


class MemoryManager:
    """
    Memory management system for optimization algorithms
    Provides monitoring, cleanup, and optimization utilities
    """

    def __init__(self, max_memory_usage_gb: float = 4.0, cleanup_threshold: float = 0.8):
        """
        Initialize memory manager

        Args:
            max_memory_usage_gb: Maximum allowed memory usage in GB
            cleanup_threshold: Fraction of max memory that triggers cleanup
        """
        self.max_memory_bytes = max_memory_usage_gb * 1024 * 1024 * 1024
        self.cleanup_threshold = cleanup_threshold
        self.memory_history = deque(maxlen=100)
        self.cleanup_strategies = []
        self.monitoring_active = False
        self.monitor_thread = None
        self._lock = threading.Lock()

        # Register default cleanup strategies
        self.register_cleanup_strategy(self._gc_collect)
        self.register_cleanup_strategy(self._clear_arrays)

    def get_memory_usage(self) -> Dict[str, float]:
        """
        Get current memory usage information

        Returns:
            Dictionary with memory statistics
        """
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size
            'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size
            'percent': process.memory_percent(),
            'available_gb': psutil.virtual_memory().available / 1024 / 1024 / 1024
        }

    def check_memory_pressure(self) -> bool:
        """
        Check if memory usage exceeds threshold

        Returns:
            True if cleanup is needed
        """
        memory_info = self.get_memory_usage()
        current_usage = memory_info['rss_mb'] * 1024 * 1024

        with self._lock:
            self.memory_history.append(current_usage)

        return current_usage > (self.max_memory_bytes * self.cleanup_threshold)

    def register_cleanup_strategy(self, strategy_func):
        """
        Register a memory cleanup strategy

        Args:
            strategy_func: Function that performs cleanup, should accept no arguments
        """
        self.cleanup_strategies.append(strategy_func)

    def cleanup_memory(self, force: bool = False) -> bool:
        """
        Perform memory cleanup using registered strategies

        Args:
            force: Force cleanup regardless of threshold

        Returns:
            True if cleanup was performed
        """
        if not force and not self.check_memory_pressure():
            return False

        initial_memory = self.get_memory_usage()['rss_mb']
        cleaned = False

        with self._lock:
            for strategy in self.cleanup_strategies:
                try:
                    strategy()
                    cleaned = True
                except Exception as e:
                    warnings.warn(f"Cleanup strategy failed: {e}")

        final_memory = self.get_memory_usage()['rss_mb']
        memory_freed = initial_memory - final_memory

        if memory_freed > 0:
            print(f"Memory cleanup freed {memory_freed:.2f} MB")

        return cleaned

    def _gc_collect(self):
        """Force garbage collection"""
        gc.collect()

    def _clear_arrays(self):
        """Clear large temporary arrays"""
        # This is a placeholder - specific implementation would depend on context
        pass

    def start_monitoring(self, interval_seconds: float = 5.0):
        """
        Start background memory monitoring

        Args:
            interval_seconds: Monitoring interval
        """
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval_seconds,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop background memory monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)

    def _monitor_loop(self, interval_seconds: float):
        """Background monitoring loop"""
        while self.monitoring_active:
            try:
                if self.check_memory_pressure():
                    self.cleanup_memory()
                time.sleep(interval_seconds)
            except Exception as e:
                warnings.warn(f"Memory monitoring error: {e}")

    def get_memory_trend(self) -> Dict[str, Any]:
        """
        Analyze memory usage trend

        Returns:
            Dictionary with trend information
        """
        if len(self.memory_history) < 2:
            return {'trend': 'insufficient_data'}

        memory_list = list(self.memory_history)
        recent_avg = np.mean(memory_list[-10:])
        older_avg = np.mean(memory_list[:-10]) if len(memory_list) > 10 else recent_avg

        if recent_avg > older_avg * 1.1:
            trend = 'increasing'
        elif recent_avg < older_avg * 0.9:
            trend = 'decreasing'
        else:
            trend = 'stable'

        return {
            'trend': trend,
            'recent_avg_mb': recent_avg / 1024 / 1024,
            'peak_mb': max(memory_list) / 1024 / 1024,
            'current_mb': memory_list[-1] / 1024 / 1024
        }


class SmartArrayCache:
    """
    Smart array cache with memory-aware eviction
    """

    def __init__(self, max_size_mb: float = 100.0, eviction_policy: str = 'lru'):
        """
        Initialize smart array cache

        Args:
            max_size_mb: Maximum cache size in MB
            eviction_policy: 'lru', 'lfu', or 'size'
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.eviction_policy = eviction_policy
        self.cache = {}
        self.access_count = {}
        self.last_access = {}
        self.current_size = 0
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[np.ndarray]:
        """
        Get array from cache

        Args:
            key: Cache key

        Returns:
            Cached array or None
        """
        with self._lock:
            if key in self.cache:
                self.access_count[key] = self.access_count.get(key, 0) + 1
                self.last_access[key] = time.time()
                return self.cache[key].copy()  # Return copy to prevent modification
            return None

    def put(self, key: str, array: np.ndarray) -> bool:
        """
        Put array into cache

        Args:
            key: Cache key
            array: Array to cache

        Returns:
            True if array was cached
        """
        array_size = array.nbytes

        with self._lock:
            # Check if single array is larger than cache
            if array_size > self.max_size_bytes:
                return False

            # Evict if necessary
            while (self.current_size + array_size > self.max_size_bytes) and self.cache:
                self._evict_one()

            # Add to cache
            self.cache[key] = array.copy()  # Store copy to prevent modification
            self.access_count[key] = 1
            self.last_access[key] = time.time()
            self.current_size += array_size

            return True

    def _evict_one(self):
        """Evict one array based on policy"""
        if not self.cache:
            return

        if self.eviction_policy == 'lru':
            # Least Recently Used
            key_to_evict = min(self.last_access.keys(), key=self.last_access.get)
        elif self.eviction_policy == 'lfu':
            # Least Frequently Used
            key_to_evict = min(self.access_count.keys(), key=self.access_count.get)
        elif self.eviction_policy == 'size':
            # Largest size
            key_to_evict = max(self.cache.keys(), key=lambda k: self.cache[k].nbytes)
        else:
            # Default: LRU
            key_to_evict = min(self.last_access.keys(), key=self.last_access.get)

        # Remove from cache
        if key_to_evict in self.cache:
            self.current_size -= self.cache[key_to_evict].nbytes
            del self.cache[key_to_evict]
            del self.access_count[key_to_evict]
            del self.last_access[key_to_evict]

    def clear(self):
        """Clear cache"""
        with self._lock:
            self.cache.clear()
            self.access_count.clear()
            self.last_access.clear()
            self.current_size = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                'size_mb': self.current_size / 1024 / 1024,
                'max_size_mb': self.max_size_bytes / 1024 / 1024,
                'num_arrays': len(self.cache),
                'utilization': self.current_size / self.max_size_bytes
            }


class OptimizationMemoryOptimizer:
    """
    Memory optimizer specifically for optimization algorithms
    """

    def __init__(self, solver_instance):
        """
        Initialize optimizer for a solver

        Args:
            solver_instance: The solver instance to optimize
        """
        self.solver = solver_instance
        self.memory_manager = MemoryManager()
        self.array_cache = SmartArrayCache()
        self.optimization_history = []

    def optimize_history_storage(self, max_generations: int = None):
        """
        Optimize history storage to reduce memory usage

        Args:
            max_generations: Maximum number of generations to store
        """
        if hasattr(self.solver, 'history'):
            history = self.solver.history

            # Store only every k-th generation for older generations
            if max_generations and len(history) > max_generations:
                # Keep recent generations, sample older ones
                recent_count = max_generations // 2
                sample_count = len(history) - recent_count
                sample_interval = max(1, sample_count // (recent_count // 2))

                optimized_history = []
                # Keep all recent generations
                optimized_history.extend(history[-recent_count:])

                # Sample older generations
                for i in range(0, len(history) - recent_count, sample_interval):
                    optimized_history.append(history[i])

                self.solver.history = optimized_history

    def optimize_population_storage(self):
        """Optimize population storage for memory efficiency"""
        if hasattr(self.solver, 'population'):
            # Convert to float32 if precision allows
            if self.solver.population.dtype == np.float64:
                # Check if we can safely downgrade to float32
                pop_min = np.min(self.solver.population)
                pop_max = np.max(self.solver.population)

                # Only downgrade if precision loss is acceptable
                if np.allclose(self.solver.population, self.solver.population.astype(np.float32)):
                    self.solver.population = self.solver.population.astype(np.float32)

                    if hasattr(self.solver, 'objectives') and self.solver.objectives.dtype == np.float64:
                        if np.allclose(self.solver.objectives, self.solver.objectives.astype(np.float32)):
                            self.solver.objectives = self.solver.objectives.astype(np.float32)

    def clear_temporary_data(self):
        """Clear temporary data that might accumulate during optimization"""
        if hasattr(self.solver, 'temp_data'):
            self.solver.temp_data.clear()

        # Clear any cached computations
        if hasattr(self.solver, '_cached_computations'):
            self.solver._cached_computations.clear()

    def auto_optimize(self):
        """Perform automatic memory optimization"""
        # Get current memory usage
        memory_info = self.memory_manager.get_memory_usage()

        # Optimization strategies based on memory pressure
        if memory_info['percent'] > 70:
            print("High memory usage detected, applying optimizations...")

            # Optimize history storage
            self.optimize_history_storage(max_generations=100)

            # Optimize population storage
            self.optimize_population_storage()

            # Clear temporary data
            self.clear_temporary_data()

            # Force cleanup
            self.memory_manager.cleanup_memory(force=True)

            # Report results
            new_memory_info = self.memory_manager.get_memory_usage()
            memory_freed = memory_info['rss_mb'] - new_memory_info['rss_mb']
            print(f"Memory optimization freed {memory_freed:.2f} MB")

    def get_optimization_report(self) -> Dict[str, Any]:
        """Get memory optimization report"""
        memory_info = self.memory_manager.get_memory_usage()
        cache_stats = self.array_cache.get_stats()
        memory_trend = self.memory_manager.get_memory_trend()

        return {
            'memory_usage': memory_info,
            'cache_stats': cache_stats,
            'memory_trend': memory_trend,
            'recommendations': self._get_recommendations(memory_info, memory_trend)
        }

    def _get_recommendations(self, memory_info: Dict, memory_trend: Dict) -> List[str]:
        """Get memory optimization recommendations"""
        recommendations = []

        if memory_info['percent'] > 80:
            recommendations.append("Consider reducing population size")
            recommendations.append("Enable more aggressive history pruning")

        if memory_trend['trend'] == 'increasing':
            recommendations.append("Memory usage is trending upward")
            recommendations.append("Consider more frequent cleanup")

        if cache_stats['utilization'] > 0.9:
            recommendations.append("Cache is nearly full, consider increasing size")

        return recommendations


# Global memory manager instance
_global_memory_manager = None


def get_global_memory_manager() -> MemoryManager:
    """Get or create global memory manager"""
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = MemoryManager()
    return _global_memory_manager


def monitor_and_optimize_memory(solver_instance, auto_optimize: bool = True):
    """
    Convenience function to monitor and optimize solver memory usage

    Args:
        solver_instance: Solver to monitor
        auto_optimize: Whether to automatically apply optimizations
    """
    optimizer = OptimizationMemoryOptimizer(solver_instance)

    if auto_optimize:
        optimizer.auto_optimize()

    return optimizer.get_optimization_report()


# Decorator for memory-intensive functions
def memory_monitoring(max_memory_gb: float = 2.0):
    """
    Decorator to monitor memory usage of functions

    Args:
        max_memory_gb: Maximum allowed memory usage in GB
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            memory_manager = MemoryManager(max_memory_usage_gb=max_memory_gb)

            # Pre-execution memory check
            initial_memory = memory_manager.get_memory_usage()

            try:
                result = func(*args, **kwargs)

                # Post-execution memory check
                final_memory = memory_manager.get_memory_usage()
                memory_increase = final_memory['rss_mb'] - initial_memory['rss_mb']

                if memory_increase > 100:  # More than 100MB increase
                    warnings.warn(f"Function {func.__name__} increased memory usage by {memory_increase:.2f} MB")

                # Cleanup if necessary
                memory_manager.cleanup_memory()

                return result

            except MemoryError:
                # Force cleanup and retry
                memory_manager.cleanup_memory(force=True)
                raise

        return wrapper
    return decorator