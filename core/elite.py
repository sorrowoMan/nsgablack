import math
import random
import numpy as np
import json
from typing import List, Tuple, Dict, Any, Optional
from collections import deque


class IntelligentHistoryManager:
    """智能历史管理器 - 完整历史保存 + 特征提取 + 智能采样"""

    def __init__(self, max_memory_size=10000, working_memory_size=100,
                 diversity_memory_size=50, enable_perturbation=True):
        # 完整历史存储
        self.full_history = []  # 完整历史记录
        self.max_memory_size = max_memory_size

        # 工作记忆（快速访问）
        self.working_memory_size = working_memory_size
        self.working_memory = deque(maxlen=working_memory_size)

        # 多样性记忆池
        self.diversity_memory_size = diversity_memory_size
        self.diversity_pool = []

        # 精英档案（历史最优解）
        self.elite_archive = []
        self.max_elite_archive = 50

        # 特征摘要
        self.feature_summary = {
            'improvement_points': [],    # 显著改进点
            'plateau_periods': [],       # 停滞期
            'diversity_trends': [],      # 多样性趋势
            'convergence_events': []     # 收敛事件
        }

        # 配置参数
        self.enable_perturbation = enable_perturbation
        self.perturbation_strength = 0.1
        self.sampling_strategy = 'mixed'  # 'recent', 'diverse', 'mixed'

    def add_generation(self, generation: int, population: np.ndarray,
                      objectives: np.ndarray, fitness_history: List[float],
                      diversity_metrics: Optional[Dict] = None):
        """添加新一代数据到历史管理器"""

        generation_data = {
            'generation': generation,
            'population': population.copy(),
            'objectives': objectives.copy(),
            'best_fitness': min(fitness_history) if fitness_history else float('inf'),
            'avg_fitness': np.mean(fitness_history) if fitness_history else 0.0,
            'diversity_metrics': diversity_metrics or {}
        }

        # 1. 添加到完整历史
        self.full_history.append(generation_data)
        if len(self.full_history) > self.max_memory_size:
            self.full_history.pop(0)

        # 2. 更新工作记忆
        self.working_memory.append(generation_data)

        # 3. 提取和更新特征
        self._extract_features(generation_data)

        # 4. 更新精英档案 - 根据目标维度选择策略
        if len(objectives.shape) > 1 and objectives.shape[1] > 1:
            # 多目标优化 - 使用帕累托档案
            self.update_pareto_archive(generation, population, objectives)
        else:
            # 单目标优化 - 使用原有的精英档案
            self._update_elite_archive(generation_data)

        # 5. 更新多样性池
        self._update_diversity_pool(generation_data)

    def _extract_features(self, generation_data: Dict):
        """提取历史特征"""
        generation = generation_data['generation']
        best_fitness = generation_data['best_fitness']

        # 检测显著改进点
        if len(self.full_history) >= 2:
            prev_best = self.full_history[-2]['best_fitness']
            improvement = prev_best - best_fitness
            if improvement > abs(prev_best) * 0.01:  # 1%的显著改进
                self.feature_summary['improvement_points'].append({
                    'generation': generation,
                    'improvement': improvement,
                    'fitness': best_fitness
                })

        # 检测停滞期
        if len(self.full_history) >= 10:
            recent_best = [h['best_fitness'] for h in self.full_history[-10:]]
            improvement = recent_best[0] - recent_best[-1]
            if abs(improvement) < abs(recent_best[0]) * 0.001:  # 0.1%以内变化
                if not self.feature_summary['plateau_periods'] or \
                   generation - self.feature_summary['plateau_periods'][-1]['end'] > 20:
                    self.feature_summary['plateau_periods'].append({
                        'start': generation - 9,
                        'end': generation,
                        'fitness_variance': np.var(recent_best)
                    })

    def _update_elite_archive(self, generation_data: Dict):
        """更新精英档案"""
        population = generation_data['population']
        objectives = generation_data['objectives']

        for i, obj in enumerate(objectives):
            candidate = {
                'individual': population[i].copy(),
                'objectives': obj.copy() if hasattr(obj, 'copy') else np.array(obj),
                'generation': generation_data['generation'],
                'fitness': generation_data['best_fitness'] if len(objectives) == 1 else np.mean(obj)
            }

            # 检查是否应该加入精英档案
            should_add = True
            for j, elite in enumerate(self.elite_archive):
                # 如果与现有精英太相似，跳过
                if np.linalg.norm(candidate['individual'] - elite['individual']) < 0.01:
                    should_add = False
                    # 如果新解更好，替换旧解
                    if candidate['fitness'] < elite['fitness']:
                        self.elite_archive[j] = candidate
                    break

            if should_add and len(self.elite_archive) < self.max_elite_archive:
                self.elite_archive.append(candidate)
            elif should_add and self.elite_archive:
                # 如果档案满了，替换最差的精英
                worst_idx = np.argmax([e['fitness'] for e in self.elite_archive])
                if candidate['fitness'] < self.elite_archive[worst_idx]['fitness']:
                    self.elite_archive[worst_idx] = candidate

    def _update_diversity_pool(self, generation_data: Dict):
        """更新多样性池"""
        population = generation_data['population']

        # 随机选择一些个体加入多样性池
        if len(population) > 5:
            selected_indices = np.random.choice(len(population),
                                             min(3, len(population)),
                                             replace=False)
            for idx in selected_indices:
                candidate = {
                    'individual': population[idx].copy(),
                    'objectives': generation_data['objectives'][idx].copy() if hasattr(generation_data['objectives'][idx], 'copy') else np.array(generation_data['objectives'][idx]),
                    'generation': generation_data['generation']
                }

                # 检查多样性
                is_diverse = True
                for diverse in self.diversity_pool:
                    if np.linalg.norm(candidate['individual'] - diverse['individual']) < 0.1:
                        is_diverse = False
                        break

                if is_diverse and len(self.diversity_pool) < self.diversity_memory_size:
                    self.diversity_pool.append(candidate)

    def get_historical_samples(self, sample_size: int = 20, strategy: str = None) -> List[Dict]:
        """获取历史样本"""
        if strategy is None:
            strategy = self.sampling_strategy

        samples = []

        if strategy == 'recent':
            # 最近的样本
            recent_data = list(self.working_memory)[-sample_size//2:]
            samples = self._extract_individuals_from_history(recent_data, sample_size//2)

        elif strategy == 'diverse':
            # 多样性样本
            samples = random.sample(self.diversity_pool,
                                  min(sample_size, len(self.diversity_pool)))

        elif strategy == 'mixed':
            # 混合策略：近期 + 精英 + 多样性
            recent_count = sample_size // 3
            elite_count = sample_size // 3
            diverse_count = sample_size - recent_count - elite_count

            # 近期样本
            recent_data = list(self.working_memory)[-recent_count:]
            recent_samples = self._extract_individuals_from_history(recent_data, recent_count)

            # 精英样本
            elite_samples = random.sample(self.elite_archive,
                                        min(elite_count, len(self.elite_archive)))

            # 多样性样本
            diverse_samples = random.sample(self.diversity_pool,
                                          min(diverse_count, len(self.diversity_pool)))

            samples = recent_samples + elite_samples + diverse_samples

        # 如果样本不够，从完整历史中补充
        if len(samples) < sample_size and len(self.full_history) > 0:
            needed = sample_size - len(samples)
            additional = random.sample(self.full_history,
                                     min(needed, len(self.full_history)))
            additional_samples = self._extract_individuals_from_history(additional, needed)
            samples.extend(additional_samples)

        return samples[:sample_size]

    def _extract_individuals_from_history(self, history_data: List[Dict], count: int) -> List[Dict]:
        """从历史数据中提取个体"""
        samples = []
        for data in history_data:
            if len(samples) >= count:
                break

            population = data['population']
            objectives = data['objectives']

            # 选择最好的几个个体
            if len(objectives.shape) == 1:  # 单目标
                best_indices = np.argsort(objectives)[:min(3, len(objectives))]
            else:  # 多目标
                # 简单求和选择
                sums = np.sum(objectives, axis=1) if len(objectives.shape) > 1 else objectives
                best_indices = np.argsort(sums)[:min(3, len(sums))]

            for idx in best_indices:
                if len(samples) >= count:
                    break
                samples.append({
                    'individual': population[idx].copy(),
                    'objectives': objectives[idx].copy() if hasattr(objectives[idx], 'copy') else np.array(objectives[idx]),
                    'generation': data['generation']
                })

        return samples

    def generate_perturbed_candidates(self, base_samples: List[Dict],
                                    var_bounds: Dict, perturbation_strength: float = None) -> List[Dict]:
        """生成历史扰动候选解"""
        if not self.enable_perturbation:
            return []

        if perturbation_strength is None:
            perturbation_strength = self.perturbation_strength

        perturbed = []

        for sample in base_samples[:len(base_samples)//2]:  # 只对一半样本进行扰动
            individual = sample['individual'].copy()

            # 基于个体质量调整扰动强度
            fitness = np.mean(sample['objectives'])
            adaptive_strength = perturbation_strength * (1 + fitness * 0.1)

            # 添加高斯扰动
            noise = np.random.normal(0, adaptive_strength, individual.shape)

            # 应用变量边界约束
            for i, var in enumerate(var_bounds):
                min_val, max_val = var_bounds[var]
                individual[i] += noise[i]
                individual[i] = np.clip(individual[i], min_val, max_val)

            perturbed.append({
                'individual': individual,
                'objectives': None,  # 需要重新评估
                'generation': -1,    # 标记为扰动生成
                'source_generation': sample['generation']
            })

        return perturbed

    def get_enhanced_elite_candidates(self, current_population: np.ndarray,
                                     current_objectives: np.ndarray,
                                     var_bounds: Dict,
                                     target_count: int = 10) -> np.ndarray:
        """获取增强的精英候选解（结合历史和扰动）"""

        # 1. 获取历史样本
        historical_samples = self.get_historical_samples(target_count // 2)

        # 2. 生成扰动候选解
        perturbed_candidates = self.generate_perturbed_candidates(
            historical_samples, var_bounds
        )

        # 3. 合并所有候选解
        all_candidates = []

        # 历史样本的个体
        for sample in historical_samples:
            all_candidates.append(sample['individual'])

        # 扰动候选解
        for candidate in perturbed_candidates:
            all_candidates.append(candidate['individual'])

        # 如果还需要更多候选解，从当前种群中选择一些优秀个体
        if len(all_candidates) < target_count and len(current_population) > 0:
            remaining = target_count - len(all_candidates)

            if len(current_objectives.shape) == 1:  # 单目标
                best_indices = np.argsort(current_objectives)[:remaining]
            else:  # 多目标
                sums = np.sum(current_objectives, axis=1)
                best_indices = np.argsort(sums)[:remaining]

            for idx in best_indices:
                all_candidates.append(current_population[idx].copy())

        # 转换为numpy数组
        result = np.array(all_candidates[:target_count])

        return result

    def save_history(self, filename: str):
        """保存完整历史到文件"""
        try:
            history_data = {
                'full_history': [],
                'feature_summary': self.feature_summary,
                'elite_archive_count': len(self.elite_archive),
                'diversity_pool_count': len(self.diversity_pool)
            }

            # 转换历史数据为可序列化格式
            for data in self.full_history:
                serializable_data = {
                    'generation': data['generation'],
                    'best_fitness': float(data['best_fitness']),
                    'avg_fitness': float(data['avg_fitness']),
                    'diversity_metrics': data['diversity_metrics']
                    # 注意：不保存population和objectives，因为文件会太大
                }
                history_data['full_history'].append(serializable_data)

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"保存历史失败: {e}")

    def load_history(self, filename: str):
        """从文件加载历史摘要"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                history_data = json.load(f)

            self.feature_summary = history_data.get('feature_summary', {})
            # 注意：只加载摘要，不加载完整历史
            print(f"成功加载历史摘要，包含 {len(self.feature_summary.get('improvement_points', []))} 个改进点")

        except Exception as e:
            print(f"加载历史失败: {e}")

    # ======== 多目标优化专用方法 ========

    def _is_dominated(self, obj1: np.ndarray, obj2: np.ndarray) -> bool:
        """判断 obj1 是否被 obj2 支配"""
        # 如果 obj2 在所有目标上都 <= obj1，且至少有一个目标 < obj1，则 obj1 被 obj2 支配
        return np.all(obj2 <= obj1) and np.any(obj2 < obj1)

    def _get_pareto_front(self, objectives: np.ndarray) -> np.ndarray:
        """获取帕累托前沿索引"""
        n = len(objectives)
        pareto_mask = np.ones(n, dtype=bool)

        for i in range(n):
            if pareto_mask[i]:
                for j in range(n):
                    if i != j and self._is_dominated(objectives[i], objectives[j]):
                        pareto_mask[i] = False
                        break

        return np.where(pareto_mask)[0]

    def _calculate_crowding_distance(self, objectives: np.ndarray, pareto_indices: np.ndarray) -> np.ndarray:
        """计算拥挤度距离"""
        if len(pareto_indices) == 0:
            return np.array([])

        n_objectives = objectives.shape[1]
        n_pareto = len(pareto_indices)
        crowding = np.zeros(n_pareto)

        # 对每个目标计算拥挤度
        for obj_idx in range(n_objectives):
            # 按当前目标排序
            sorted_indices = np.argsort(objectives[pareto_indices, obj_idx])

            # 边界点设置为无穷大
            crowding[sorted_indices[0]] = float('inf')
            crowding[sorted_indices[-1]] = float('inf')

            # 计算中间点的拥挤度
            obj_range = objectives[pareto_indices[sorted_indices[-1]], obj_idx] - objectives[pareto_indices[sorted_indices[0]], obj_idx]
            if obj_range > 0:
                for i in range(1, n_pareto - 1):
                    crowding[sorted_indices[i]] += (
                        objectives[pareto_indices[sorted_indices[i + 1]], obj_idx] -
                        objectives[pareto_indices[sorted_indices[i - 1]], obj_idx]
                    ) / obj_range

        return crowding

    def update_pareto_archive(self, generation: int, population: np.ndarray, objectives: np.ndarray):
        """更新帕累托档案"""
        # 获取当前代的帕累托前沿
        pareto_indices = self._get_pareto_front(objectives)

        for idx in pareto_indices:
            candidate = {
                'individual': population[idx].copy(),
                'objectives': objectives[idx].copy(),
                'generation': generation,
                'added_to_archive': generation
            }

            # 检查是否应该加入帕累托档案
            should_add = True

            # 移除被新解支配的现有解
            self.elite_archive = [elite for elite in self.elite_archive
                                if not self._is_dominated(elite['objectives'], candidate['objectives'])]

            # 检查新解是否被档案中的解支配
            for elite in self.elite_archive:
                if self._is_dominated(candidate['objectives'], elite['objectives']):
                    should_add = False
                    break

            # 如果档案未满且应该添加，则添加
            if should_add and len(self.elite_archive) < self.max_elite_archive:
                self.elite_archive.append(candidate)
            elif should_add and len(self.elite_archive) >= self.max_elite_archive:
                # 使用拥挤度距离选择要替换的解
                archive_objectives = np.array([elite['objectives'] for elite in self.elite_archive])
                archive_pareto = self._get_pareto_front(archive_objectives)

                if len(archive_pareto) > 0:
                    archive_crowding = self._calculate_crowding_distance(archive_objectives, archive_pareto)
                    # 找到拥挤度最小的解
                    worst_idx_in_pareto = archive_pareto[np.argmin(archive_crowding)]
                    self.elite_archive[worst_idx_in_pareto] = candidate

    def get_pareto_samples(self, sample_size: int = 20, diversity_strategy: str = 'crowding') -> List[Dict]:
        """从帕累托档案中获取样本"""
        if not self.elite_archive:
            return []

        archive_objectives = np.array([elite['objectives'] for elite in self.elite_archive])
        pareto_indices = self._get_pareto_front(archive_objectives)

        if len(pareto_indices) == 0:
            return []

        if diversity_strategy == 'crowding' and len(pareto_indices) > sample_size:
            # 使用拥挤度距离选择多样化样本
            crowding = self._calculate_crowding_distance(archive_objectives, pareto_indices)
            # 选择拥挤度最大的样本（最多样化）
            selected_indices = np.argsort(-crowding)[:sample_size]
            selected_pareto = pareto_indices[selected_indices]
        elif len(pareto_indices) > sample_size:
            # 随机选择
            selected_pareto = np.random.choice(pareto_indices, sample_size, replace=False)
        else:
            selected_pareto = pareto_indices

        samples = []
        for idx in selected_pareto:
            elite = self.elite_archive[idx]
            samples.append({
                'individual': elite['individual'].copy(),
                'objectives': elite['objectives'].copy(),
                'generation': elite['generation'],
                'source': 'pareto_archive'
            })

        return samples

    def analyze_pareto_convergence(self, window_size: int = 10) -> Dict[str, Any]:
        """分析帕累托前沿的收敛性"""
        if len(self.full_history) < window_size:
            return {'status': 'insufficient_data'}

        recent_history = self.full_history[-window_size:]
        pareto_sizes = []
        hypervolumes = []

        for generation_data in recent_history:
            objectives = generation_data['objectives']
            if len(objectives.shape) > 1:
                pareto_indices = self._get_pareto_front(objectives)
                pareto_sizes.append(len(pareto_indices))

                # 简化的超体积计算（仅适用于2目标）
                if objectives.shape[1] == 2 and len(pareto_indices) > 0:
                    pareto_obj = objectives[pareto_indices]
                    # 使用参考点为所有目标的最大值
                    ref_point = np.max(objectives, axis=0) * 1.1
                    hv = 0
                    sorted_obj = pareto_obj[np.argsort(pareto_obj[:, 0])]
                    for i in range(len(sorted_obj)):
                        hv += (ref_point[0] - sorted_obj[i, 0]) * (ref_point[1] - sorted_obj[i, 1])
                        if i > 0:
                            hv -= (ref_point[0] - sorted_obj[i-1, 0]) * (ref_point[1] - sorted_obj[i, 1])
                    hypervolumes.append(hv)

        result = {
            'pareto_size_trend': pareto_sizes,
            'hypervolume_trend': hypervolumes,
            'avg_pareto_size': np.mean(pareto_sizes) if pareto_sizes else 0,
            'pareto_size_stability': np.std(pareto_sizes) if len(pareto_sizes) > 1 else 0,
            'hypervolume_improvement': (hypervolumes[-1] - hypervolumes[0]) if len(hypervolumes) > 1 else 0
        }

        if len(hypervolumes) > 1:
            result['hypervolume_convergence_rate'] = hypervolumes[-1] / hypervolumes[0] if hypervolumes[0] > 0 else 0

        return result

    def get_multi_objective_replacement_candidates(self, current_population: np.ndarray,
                                                  current_objectives: np.ndarray,
                                                  var_bounds: Dict,
                                                  replacement_count: int,
                                                  strategy: str = 'pareto_diverse') -> np.ndarray:
        """获取多目标优化的历史替换候选解"""
        if strategy == 'pareto_diverse':
            # 优先从帕累托档案中选择
            pareto_samples = self.get_pareto_samples(replacement_count, diversity_strategy='crowding')
            candidates = [sample['individual'] for sample in pareto_samples]
        else:
            # 使用原有的方法但改进多目标处理
            historical_samples = self.get_historical_samples(replacement_count)
            candidates = []

            for sample in historical_samples:
                candidates.append(sample['individual'])

        # 如果候选解不够，生成一些在帕累托前沿附近的扰动解
        if len(candidates) < replacement_count and len(self.elite_archive) > 0:
            remaining = replacement_count - len(candidates)

            for _ in range(remaining):
                # 随机选择一个帕累托解作为基础
                base_elite = np.random.choice(self.elite_archive)
                base_individual = base_elite['individual'].copy()

                # 生成扰动
                perturbed = base_individual.copy()
                for var in var_bounds:
                    perturbation = np.random.normal(0, 0.05 * (var_bounds[var][1] - var_bounds[var][0]))
                    perturbed[var] = np.clip(
                        base_individual[var] + perturbation,
                        var_bounds[var][0],
                        var_bounds[var][1]
                    )
                candidates.append(perturbed)

        return np.array(candidates[:replacement_count]) if candidates else np.array([])


class AdvancedEliteRetention:
    """高级精英保留策略 - 基于停滞代数和多样性的概率性精英管理 + 智能历史管理"""

    def __init__(self, max_generations, population_size, initial_retention_prob=0.9,
                 min_replace_ratio: float = 0.05, max_replace_ratio: float = 0.6,
                 replacement_weights: dict | None = None, enable_intelligent_history=True):
        self.max_generations = max_generations
        self.population_size = population_size
        self.initial_retention_prob = initial_retention_prob
        self.stagnation_count = 0
        self.consecutive_improvements = 0
        self.diversity_history = []
        self.fitness_history = []
        self._last_factors = None
        self.min_replace_ratio = float(min_replace_ratio)
        self.max_replace_ratio = float(max_replace_ratio)
        self.replacement_weights = {
            'base': 0.25,
            'stagnation_neg': 0.45,
            'diversity_neg': 0.35,
            'progress_pos': 0.15,
            'improvement_neg': 0.30,
            'retention_neg': 0.25,
            'retention_bias': 0.125
        }
        if isinstance(replacement_weights, dict):
            self.replacement_weights.update(replacement_weights)

        # 智能历史管理器
        self.enable_intelligent_history = enable_intelligent_history
        if enable_intelligent_history:
            self.history_manager = IntelligentHistoryManager(
                max_memory_size=10000,
                working_memory_size=100,
                diversity_memory_size=50,
                enable_perturbation=True
            )
        else:
            self.history_manager = None

    def set_replacement_config(self, *, min_ratio: float | None = None,
                               max_ratio: float | None = None,
                               weights: dict | None = None):
        if min_ratio is not None:
            self.min_replace_ratio = float(min_ratio)
        if max_ratio is not None:
            self.max_replace_ratio = float(max_ratio)
        if isinstance(weights, dict):
            self.replacement_weights.update(weights)

    def calculate_elite_retention_probability(self, current_generation, current_best_fitness,
                                              population_fitnesses, population):
        stagnation_factor = self._calculate_stagnation_factor(current_best_fitness)
        progress_factor = self._calculate_progress_factor(current_generation)
        diversity_factor = self._calculate_diversity_factor(population_fitnesses, population)
        improvement_factor = self._calculate_improvement_factor(current_best_fitness)
        self._last_factors = {
            'stagnation_factor': stagnation_factor,
            'progress_factor': progress_factor,
            'diversity_factor': diversity_factor,
            'improvement_factor': improvement_factor,
        }
        base_prob = self.initial_retention_prob
        stagnation_penalty = (1 - stagnation_factor) * 0.4
        diversity_penalty = (1 - diversity_factor) * 0.3
        progress_adjustment = (1 - progress_factor) * 0.2
        improvement_bonus = improvement_factor * 0.1
        retention_prob = (
            base_prob
            - stagnation_penalty
            - diversity_penalty
            - progress_adjustment
            + improvement_bonus
        )
        retention_prob = self._apply_nonlinear_transform(retention_prob)
        return max(0.05, min(0.95, retention_prob))

    def get_elite_replacement_ratio(self, retention_prob: float | None = None):
        if not self._last_factors:
            return 0.3
        f = self._last_factors
        w = self.replacement_weights
        ratio = (
            float(w.get('base', 0.25))
            + float(w.get('stagnation_neg', 0.45)) * (1.0 - float(f['stagnation_factor']))
            + float(w.get('diversity_neg', 0.35)) * (1.0 - float(f['diversity_factor']))
            + float(w.get('progress_pos', 0.15)) * float(f['progress_factor'])
            - float(w.get('improvement_neg', 0.30)) * float(f['improvement_factor'])
        )
        if retention_prob is not None:
            ratio = ratio - float(w.get('retention_neg', 0.25)) * float(retention_prob) + float(w.get('retention_bias', 0.125))
        lo = min(self.min_replace_ratio, self.max_replace_ratio)
        hi = max(self.min_replace_ratio, self.max_replace_ratio)
        return max(lo, min(hi, float(ratio)))

    def _calculate_stagnation_factor(self, current_best_fitness):
        if len(self.fitness_history) < 2:
            self.stagnation_count = 0
            return 1.0
        previous_best = max(self.fitness_history[-5:]) if len(self.fitness_history) >= 5 else self.fitness_history[-1]
        improvement_threshold = previous_best * 0.001
        if current_best_fitness > previous_best + improvement_threshold:
            self.stagnation_count = 0
            self.consecutive_improvements += 1
        else:
            self.stagnation_count += 1
            self.consecutive_improvements = max(0, self.consecutive_improvements - 0.5)
        stagnation_weight = min(self.stagnation_count / 50.0, 1.0)
        stagnation_factor = 1 - math.tanh(stagnation_weight * 2) / 2
        return stagnation_factor

    def _calculate_progress_factor(self, current_generation):
        progress_ratio = current_generation / self.max_generations
        if progress_ratio < 0.3:
            return 1 - (progress_ratio / 0.3) ** 2 * 0.3
        elif progress_ratio < 0.7:
            return 0.7 - (progress_ratio - 0.3) / 0.4 * 0.4
        else:
            return 0.3 - (progress_ratio - 0.7) / 0.3 * 0.25

    def _calculate_diversity_factor(self, fitnesses, population):
        if len(fitnesses) <= 1:
            return 1.0
        geno_diversity = self._calculate_genotypic_diversity(population)
        pheno_diversity = self._calculate_phenotypic_diversity(fitnesses)
        trend_diversity = self._calculate_diversity_trend(geno_diversity)
        combined_diversity = (geno_diversity * 0.4 + pheno_diversity * 0.4 + trend_diversity * 0.2)
        self.diversity_history.append(combined_diversity)
        if len(self.diversity_history) > 100:
            self.diversity_history.pop(0)
        return combined_diversity

    def _calculate_genotypic_diversity(self, population):
        if len(population) <= 1:
            return 1.0
        sample_size = min(20, len(population))
        sampled_indices = np.random.choice(len(population), sample_size, replace=False)
        total_distance = 0
        count = 0
        for i in range(sample_size):
            for j in range(i+1, sample_size):
                idx1, idx2 = sampled_indices[i], sampled_indices[j]
                dist = np.linalg.norm(population[idx1] - population[idx2])
                max_possible_dist = np.sqrt(len(population[0])) * 2
                normalized_dist = min(dist / max_possible_dist, 1.0)
                total_distance += normalized_dist
                count += 1
        return total_distance / count if count > 0 else 0.0

    def _calculate_phenotypic_diversity(self, fitnesses):
        if len(fitnesses) <= 1:
            return 1.0
        fitness_array = np.array(fitnesses)
        mean_fitness = np.mean(fitness_array)
        if abs(mean_fitness) < 1e-10:
            cv = 1.0
        else:
            cv = min(np.std(fitness_array) / abs(mean_fitness), 2.0) / 2.0
        fitness_range = (np.max(fitness_array) - np.min(fitness_array))
        if abs(mean_fitness) > 1e-10:
            range_ratio = min(fitness_range / abs(mean_fitness), 1.0)
        else:
            range_ratio = 1.0
        return (cv * 0.6 + range_ratio * 0.4)

    def _calculate_diversity_trend(self, current_diversity):
        if len(self.diversity_history) < 5:
            return 1.0
        recent_diversities = self.diversity_history[-5:]
        if len(recent_diversities) < 2:
            return 1.0
        trend = (recent_diversities[-1] - recent_diversities[0]) / len(recent_diversities)
        if trend > 0.01:
            return 1.0
        elif trend > -0.01:
            return 0.5
        else:
            return 0.0

    def _calculate_improvement_factor(self, current_best_fitness):
        if len(self.fitness_history) < 3:
            return 1.0
        improvement_factor = min(self.consecutive_improvements / 10.0, 1.0)
        if len(self.fitness_history) >= 5:
            old_best = max(self.fitness_history[-5:-1])
            if old_best > 0:
                improvement_ratio = (current_best_fitness - old_best) / abs(old_best)
                improvement_factor = max(improvement_factor, min(improvement_ratio * 10, 1.0))
        return improvement_factor

    def _apply_nonlinear_transform(self, probability):
        if probability < 0.5:
            transformed = 0.05 + 0.9 * (1 - math.exp(-3 * probability))
        else:
            transformed = 0.95 - 0.9 * math.exp(-3 * (1 - probability))
        return transformed

    def update_history(self, best_fitness):
        self.fitness_history.append(best_fitness)
        if len(self.fitness_history) > 100:
            self.fitness_history.pop(0)

    def update_history_with_generation_data(self, generation: int, population: np.ndarray,
                                           objectives: np.ndarray, var_bounds: Dict,
                                           diversity_metrics: Optional[Dict] = None):
        """使用智能历史管理器更新历史数据"""
        if self.history_manager:
            self.history_manager.add_generation(
                generation, population, objectives, self.fitness_history, diversity_metrics
            )

    def get_intelligent_elite_candidates(self, current_population: np.ndarray,
                                        current_objectives: np.ndarray,
                                        var_bounds: Dict,
                                        target_count: int = 10) -> Optional[np.ndarray]:
        """获取基于智能历史管理的精英候选解"""
        if not self.history_manager:
            return None

        return self.history_manager.get_enhanced_elite_candidates(
            current_population, current_objectives, var_bounds, target_count
        )

    def should_use_historical_replacement(self, current_generation: int,
                                        current_best_fitness: float) -> bool:
        """决定是否使用历史替换策略"""
        if not self.history_manager:
            return False

        # 在停滞期或多样性低时更倾向于使用历史替换
        stagnation_factor = self._calculate_stagnation_factor(current_best_fitness)

        # 如果停滞代数较多，增加历史替换概率
        stagnation_probability = min(0.7, self.stagnation_count / 30.0)

        # 如果有显著改进点，减少历史替换概率
        improvement_count = len(self.history_manager.feature_summary.get('improvement_points', []))
        improvement_factor = max(0.1, 1.0 - improvement_count * 0.1)

        use_historical = random.random() < (stagnation_probability * improvement_factor)

        return use_historical

    def get_historical_replacement_candidates(self, var_bounds: Dict,
                                            replacement_count: int) -> np.ndarray:
        """获取历史替换候选解"""
        if not self.history_manager:
            return np.array([])

        # 获取历史样本
        historical_samples = self.history_manager.get_historical_samples(replacement_count)

        # 生成扰动候选解
        perturbed_candidates = self.history_manager.generate_perturbed_candidates(
            historical_samples, var_bounds, perturbation_strength=0.15
        )

        # 合并历史样本和扰动样本
        all_candidates = []

        for sample in historical_samples:
            all_candidates.append(sample['individual'])

        for candidate in perturbed_candidates:
            all_candidates.append(candidate['individual'])

        # 如果候选解不够，生成一些随机解
        if len(all_candidates) < replacement_count:
            remaining = replacement_count - len(all_candidates)
            for _ in range(remaining):
                random_candidate = np.array([
                    np.random.uniform(var_bounds[var][0], var_bounds[var][1])
                    for var in var_bounds
                ])
                all_candidates.append(random_candidate)

        return np.array(all_candidates[:replacement_count])

    def save_intelligent_history(self, filename: str):
        """保存智能历史管理器的数据"""
        if self.history_manager:
            self.history_manager.save_history(filename)

    def load_intelligent_history(self, filename: str):
        """加载智能历史管理器的数据"""
        if self.history_manager:
            self.history_manager.load_history(filename)
