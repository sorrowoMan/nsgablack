"""Auto-extracted mixin module."""
from __future__ import annotations


import math
from typing import Dict, List
import numpy as np
from ..core.role import AgentRole
from ..core.population import AgentPopulation

class ScoringMixin:
    """Mixin for multi-agent solver."""

    def _compute_role_scores(self) -> Dict[AgentRole, float]:
        """score roles for ratio adaptation"""
        improvements = {}
        feasibilities = {}
        diversities = {}

        for role, pop in self.agent_populations.items():
            if pop.best_objectives is not None:
                current_mean = float(np.mean(pop.best_objectives))
            else:
                current_mean = float('inf')

            if pop.last_best_objectives is None or pop.best_objectives is None:
                improvement = 0.0
            else:
                prev_mean = float(np.mean(pop.last_best_objectives))
                improvement = max(0.0, prev_mean - current_mean)

            if pop.best_objectives is not None:
                pop.last_best_objectives = pop.best_objectives.copy()

            improvements[role] = improvement
            feasibilities[role] = float(pop.feasible_rate)
            diversities[role] = self._role_diversity(pop)

        norm_improve = self._normalize_metric(improvements)
        norm_feasible = self._normalize_metric(feasibilities)
        norm_diverse = self._normalize_metric(diversities)

        weights = self.config.get('role_score_weights', {})
        w_improve = float(weights.get('improvement', 0.5))
        w_feasible = float(weights.get('feasibility', 0.3))
        w_diverse = float(weights.get('diversity', 0.2))

        scores = {}
        for role in self.agent_populations:
            pop = self.agent_populations[role]
            score = (
                w_improve * norm_improve.get(role, 0.0) +
                w_feasible * norm_feasible.get(role, 0.0) +
                w_diverse * norm_diverse.get(role, 0.0)
            )
            score += self._score_with_biases(role, pop)
            scores[role] = score
            pop.score = score
            self.history['agent_scores'][role].append(score)

        return scores

    def _get_score_biases(self, role: AgentRole, pop: AgentPopulation) -> List:
        biases = []
        global_biases = self.config.get('global_score_biases') or []
        role_biases = self.config.get('role_score_biases') or {}

        biases.extend(global_biases if isinstance(global_biases, list) else [global_biases])
        if isinstance(role_biases, dict):
            if role in role_biases:
                biases.extend(role_biases.get(role) or [])
            elif role.value in role_biases:
                biases.extend(role_biases.get(role.value) or [])

        profile_biases = pop.bias_profile.get('score_biases') if isinstance(pop.bias_profile, dict) else None
        if profile_biases:
            biases.extend(profile_biases if isinstance(profile_biases, list) else [profile_biases])

        return [b for b in biases if b is not None]

    def _score_with_biases(self, role: AgentRole, pop: AgentPopulation) -> float:
        biases = self._get_score_biases(role, pop)
        if not biases or pop.best_individual is None:
            return 0.0

        constraints = pop.best_constraints or []
        violation = self._total_violation(constraints)
        context = {
            'role': role.value,
            'population': pop.population,
            'objectives': pop.objectives,
            'constraints': pop.constraints,
            'fitness': pop.fitness,
            'best_objectives': pop.best_objectives,
            'feasible_rate': pop.feasible_rate,
            'avg_violation': pop.avg_violation,
            'constraint_violation': violation,
            'archives': self.archives,
            'generation': self.history.get('generation', 0),
            'problem': self.problem,
        }

        total = 0.0
        for bias in biases:
            result = self._call_score_bias(bias, pop.best_individual, constraints, context, pop)
            total += self._extract_score_value(result)
        return total

    def _call_score_bias(self, bias, x, constraints, context, pop):
        if hasattr(bias, 'compute_score'):
            return bias.compute_score(x, constraints, context)
        if hasattr(bias, 'score'):
            return bias.score(x, constraints, context)
        if callable(bias):
            for args in (
                (x, constraints, context),
                (x, context),
                (x, constraints),
                (x,),
                (context,),
                (pop, context),
                (pop,),
            ):
                try:
                    return bias(*args)
                except TypeError:
                    continue
        return 0.0

    def _extract_score_value(self, result) -> float:
        if isinstance(result, dict):
            if 'score' in result:
                return float(result.get('score', 0.0))
            if 'reward' in result:
                return float(result.get('reward', 0.0))
            if 'penalty' in result:
                return -float(result.get('penalty', 0.0))
            if 'value' in result:
                return float(result.get('value', 0.0))
            return 0.0
        if isinstance(result, (tuple, list)) and len(result) >= 1:
            try:
                return float(result[0])
            except Exception:
                return 0.0
        try:
            return float(result)
        except Exception:
            return 0.0

    def _role_diversity(self, pop: AgentPopulation) -> float:
        """role diversity vs global best"""
        if self.global_best is None or not pop.population:
            return 0.0
        distances = [float(np.linalg.norm(ind - self.global_best)) for ind in pop.population]
        return float(np.mean(distances)) if distances else 0.0

    def _update_role_ratios(self, scores: Dict[AgentRole, float]) -> None:
        """update role ratios and resize populations"""
        total_score = sum(scores.values())
        if total_score <= 0:
            return

        target = {role: score / total_score for role, score in scores.items()}
        current = self.config.get('agent_ratios', {})
        rate = float(self.config.get('ratio_update_rate', 0.2))
        min_r = float(self.config.get('min_role_ratio', 0.05))
        max_r = float(self.config.get('max_role_ratio', 0.6))

        new_ratios = {}
        for role, cur in current.items():
            new_ratio = (1.0 - rate) * cur + rate * target.get(role, cur)
            new_ratio = float(np.clip(new_ratio, min_r, max_r))
            new_ratios[role] = new_ratio

        # renormalize
        total = sum(new_ratios.values())
        if total > 0:
            for role in new_ratios:
                new_ratios[role] = new_ratios[role] / total

        self.config['agent_ratios'] = new_ratios
        self._apply_role_ratios(new_ratios)

    def _apply_role_ratios(self, ratios: Dict[AgentRole, float]) -> None:
        """resize populations based on ratios"""
        total_pop = int(self.config.get('total_population', 0))
        if total_pop <= 0:
            return

        desired = {role: int(total_pop * ratio) for role, ratio in ratios.items()}
        diff = total_pop - sum(desired.values())
        if diff != 0:
            # distribute rounding diff
            roles_sorted = sorted(ratios.items(), key=lambda item: item[1], reverse=(diff > 0))
            for i in range(abs(diff)):
                role = roles_sorted[i % len(roles_sorted)][0]
                desired[role] += 1 if diff > 0 else -1

        # remove excess
        for role, pop in self.agent_populations.items():
            if role not in desired:
                continue
            excess = len(pop.population) - desired[role]
            if excess > 0:
                self._remove_worst(pop, excess)

        # add deficit
        for role, pop in self.agent_populations.items():
            if role not in desired:
                continue
            deficit = desired[role] - len(pop.population)
            if deficit > 0:
                # prefer borrowing from waiter pool
                if role != AgentRole.WAITER:
                    waiter_pop = self.agent_populations.get(AgentRole.WAITER)
                    if waiter_pop is not None and waiter_pop.population:
                        moved = self._take_waiter_individuals(waiter_pop, min(deficit, len(waiter_pop.population)))
                        self._append_individuals(pop, moved)
                        deficit = desired[role] - len(pop.population)
                if deficit > 0:
                    self._add_individuals(pop, deficit, role)

