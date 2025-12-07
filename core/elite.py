import math
import numpy as np


class AdvancedEliteRetention:
    """高级精英保留策略 - 基于停滞代数和多样性的概率性精英管理"""

    def __init__(self, max_generations, population_size, initial_retention_prob=0.9,
                 min_replace_ratio: float = 0.05, max_replace_ratio: float = 0.6,
                 replacement_weights: dict | None = None):
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
