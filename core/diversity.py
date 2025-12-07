import json
import os
import time
import numpy as np
from scipy.spatial.distance import cdist
from scipy.stats import qmc


class DiversityAwareInitializerBlackBox:
    """黑箱问题专用的多样性感知初始化器"""

    def __init__(self, problem, history_size=1000, similarity_threshold=0.1, rejection_prob=0.7):
        self.problem = problem
        self.similarity_threshold = similarity_threshold
        self.rejection_prob = rejection_prob
        self.history_solutions = []
        self.history_fitness = []
        self.history_size = history_size
        self.history_file = None

    def set_history_file(self, file_path):
        self.history_file = file_path

    def save_history(self, file_path=None):
        if file_path is None:
            file_path = self.history_file
        if file_path is None:
            print("警告: 未指定历史数据文件路径")
            return False
        try:
            history_data = {
                'problem_name': self.problem.name,
                'dimension': self.problem.dimension,
                'variables': self.problem.variables,
                'bounds': self.problem.bounds,
                'history_solutions': [sol.tolist() for sol in self.history_solutions],
                'history_fitness': self.history_fitness,
                'timestamp': time.time(),
                'total_runs': len(self.history_solutions)
            }
            with open(file_path, 'w') as f:
                json.dump(history_data, f, indent=2)
            print(f"黑箱问题历史数据已保存到: {file_path}")
            return True
        except Exception as e:
            print(f"保存黑箱问题历史数据时出错: {e}")
            return False

    def load_history(self, file_path=None):
        if file_path is None:
            file_path = self.history_file
        if file_path is None or not os.path.exists(file_path):
            print(f"黑箱问题历史数据文件不存在: {file_path}")
            return False
        try:
            with open(file_path, 'r') as f:
                history_data = json.load(f)
            if (history_data['dimension'] != self.problem.dimension):
                print(f"警告: 历史数据与当前问题维度不兼容")
                print(f"历史维度: {history_data['dimension']}")
                print(f"当前维度: {self.problem.dimension}")
                return False
            self.history_solutions = [np.array(sol) for sol in history_data['history_solutions']]
            self.history_fitness = history_data['history_fitness']
            if len(self.history_solutions) > self.history_size:
                self.history_solutions = self.history_solutions[-self.history_size:]
                self.history_fitness = self.history_fitness[-self.history_size:]
            print(f"从 {file_path} 加载了 {len(self.history_solutions)} 个黑箱问题历史解")
            return True
        except Exception as e:
            print(f"加载黑箱问题历史数据时出错: {e}")
            return False

    def clear_history(self):
        self.history_solutions = []
        self.history_fitness = []
        print("黑箱问题历史数据已清除")

    def is_similar_to_history(self, candidate):
        if not self.history_solutions:
            return False
        bounds = self.problem.bounds
        bounds_array = np.array(list(bounds.values()))
        candidate_norm = (candidate - bounds_array[:, 0]) / (bounds_array[:, 1] - bounds_array[:, 0])
        history_array = np.array(self.history_solutions)
        history_norm = (history_array - bounds_array[:, 0]) / (bounds_array[:, 1] - bounds_array[:, 0])
        distances = cdist(candidate_norm.reshape(1, -1), history_norm, metric='euclidean')
        min_distance = np.min(distances)
        return min_distance < self.similarity_threshold

    def add_to_history(self, solution, fitness):
        self.history_solutions.append(solution.copy())
        if isinstance(fitness, np.ndarray) and len(fitness.shape) > 0:
            fitness_record = fitness[0] if len(fitness) > 0 else 0
        else:
            fitness_record = fitness
        self.history_fitness.append(fitness_record)
        if len(self.history_solutions) > self.history_size:
            self.history_solutions.pop(0)
            self.history_fitness.pop(0)

    def initialize_diverse_population(self, pop_size=100, candidate_size=1000, sampling_method='lhs'):
        bounds = self.problem.bounds
        n_dim = self.problem.dimension
        bounds_array = np.array(list(bounds.values()))
        if sampling_method == 'lhs':
            sampler = qmc.LatinHypercube(d=n_dim)
            candidates = sampler.random(n=candidate_size)
            candidates = qmc.scale(candidates, bounds_array[:, 0], bounds_array[:, 1])
        elif sampling_method == 'random':
            candidates = np.zeros((candidate_size, n_dim))
            for i, var in enumerate(self.problem.variables):
                low, high = bounds[var]
                candidates[:, i] = np.random.uniform(low, high, candidate_size)
        else:
            raise ValueError(f"不支持的采样方法: {sampling_method}")
        print("预评估候选解...")
        fitness_values = []
        for i, candidate in enumerate(candidates):
            fitness = self.problem.evaluate(candidate)
            fitness_values.append(fitness)
            if (i + 1) % 100 == 0:
                print(f"已评估 {i + 1}/{candidate_size} 个候选解")
        fitness_values = np.array(fitness_values)
        if self.problem.is_multiobjective():
            sorted_indices = self.sort_candidates_multiobjective(candidates, fitness_values)
        else:
            sorted_indices = np.argsort(fitness_values)
        selected_population = []
        selected_fitness = []
        for idx in sorted_indices:
            if len(selected_population) >= pop_size:
                break
            candidate = candidates[idx]
            fitness = fitness_values[idx]
            if self.is_similar_to_history(candidate):
                if np.random.random() < self.rejection_prob:
                    continue
            selected_population.append(candidate)
            selected_fitness.append(fitness)
        if len(selected_population) < pop_size:
            remaining_needed = pop_size - len(selected_population)
            remaining_added = 0
            for idx in sorted_indices:
                if remaining_added >= remaining_needed:
                    break
                candidate = candidates[idx]
                fitness = fitness_values[idx]
                if candidate.tolist() not in [s.tolist() for s in selected_population]:
                    selected_population.append(candidate)
                    selected_fitness.append(fitness)
                    remaining_added += 1
        for sol, fit in zip(selected_population, selected_fitness):
            self.add_to_history(sol, fit)
        print(f"多样性初始化完成，从 {candidate_size} 个候选解中选择了 {len(selected_population)} 个个体")
        return np.array(selected_population), np.array(selected_fitness)

    def sort_candidates_multiobjective(self, candidates, fitness_values):
        pop_size = candidates.shape[0]
        dominated = np.zeros(pop_size, dtype=bool)
        for i in range(pop_size):
            for j in range(pop_size):
                if i != j and np.all(fitness_values[j] <= fitness_values[i]) and np.any(fitness_values[j] < fitness_values[i]):
                    dominated[i] = True
                    break
        front1_indices = np.where(~dominated)[0]
        if len(front1_indices) > 0:
            crowding_distances = np.zeros(len(front1_indices))
            for obj_idx in range(fitness_values.shape[1]):
                sorted_by_obj = np.argsort(fitness_values[front1_indices, obj_idx])
                if len(sorted_by_obj) > 2:
                    obj_range = fitness_values[front1_indices[sorted_by_obj[-1]], obj_idx] - fitness_values[front1_indices[sorted_by_obj[0]], obj_idx]
                    if obj_range > 1e-10:
                        crowding_distances[sorted_by_obj[1:-1]] += (
                            fitness_values[front1_indices[sorted_by_obj[2:]], obj_idx] -
                            fitness_values[front1_indices[sorted_by_obj[:-2]], obj_idx]
                        ) / obj_range
            front1_sorted = front1_indices[np.argsort(-crowding_distances)]
            remaining_indices = np.where(dominated)[0]
            sorted_indices = np.concatenate([front1_sorted, remaining_indices])
        else:
            sorted_indices = np.argsort(fitness_values[:, 0])
        return sorted_indices

    def adaptive_parameters(self, run_count):
        base_threshold = 0.05
        adaptive_threshold = base_threshold * (1 + 0.1 * run_count)
        adaptive_rejection_prob = min(0.8, 0.5 + 0.05 * run_count)
        return adaptive_threshold, adaptive_rejection_prob
