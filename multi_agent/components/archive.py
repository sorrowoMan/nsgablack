"""Auto-extracted mixin module."""
from __future__ import annotations


import random
from typing import Dict, List
import numpy as np
from scipy.spatial.distance import cdist
from ..core.role import AgentRole
from ..core.population import AgentPopulation

class ArchiveMixin:
    """Mixin for multi-agent solver."""

    def _update_archives(self) -> None:
        """update multi-layer archives"""
        if not self.config.get('archive_enabled', True):
            return

        candidates = []
        gen = self.history.get('generation', 0)
        for role, pop in self.agent_populations.items():
            for i, individual in enumerate(pop.population):
                if i >= len(pop.objectives):
                    continue
                obj = pop.objectives[i]
                cons = pop.constraints[i] if pop.constraints else []
                violation = self._total_violation(cons)
                candidates.append({
                    'x': individual.copy(),
                    'objectives': obj,
                    'constraints': cons,
                    'violation': violation,
                    'role': role,
                    'generation': gen
                })

        if not candidates:
            return

        sizes = self._get_archive_sizes()
        feasible = [c for c in candidates if c['violation'] == 0.0]
        infeasible = [c for c in candidates if c['violation'] > 0.0]

        self.archives['feasible'] = self._update_feasible_archive(
            self.archives.get('feasible', []), feasible, sizes['feasible']
        )
        self.archives['boundary'] = self._update_boundary_archive(
            self.archives.get('boundary', []), infeasible, sizes['boundary']
        )

        diversity_source = self.archives['feasible'] if self.archives['feasible'] else candidates
        self.archives['diversity'] = self._update_diversity_archive(
            self.archives.get('diversity', []), diversity_source, sizes['diversity']
        )

        # backward compatible alias (feasible archive)
        self.archive = self.archives['feasible']

    def _get_archive_sizes(self) -> Dict[str, int]:
        sizes = self.config.get('archive_sizes')
        if isinstance(sizes, dict):
            return {
                'feasible': int(sizes.get('feasible', 0) or 0),
                'boundary': int(sizes.get('boundary', 0) or 0),
                'diversity': int(sizes.get('diversity', 0) or 0),
            }
        base = int(self.config.get('archive_size', 200))
        boundary = max(10, base // 2) if base > 0 else 0
        return {
            'feasible': base,
            'boundary': boundary,
            'diversity': base
        }

    def _update_feasible_archive(self, archive: List[Dict], candidates: List[Dict], max_size: int) -> List[Dict]:
        if not candidates and not archive:
            return []
        updated = archive[:]
        for cand in candidates:
            dominated = False
            to_remove = []
            for idx, arc in enumerate(updated):
                if self._dominates(arc['objectives'], cand['objectives']):
                    dominated = True
                    break
                if self._dominates(cand['objectives'], arc['objectives']):
                    to_remove.append(idx)
            if dominated:
                continue
            for idx in reversed(to_remove):
                del updated[idx]
            updated.append(cand)

        if max_size > 0 and len(updated) > max_size:
            updated = self._prune_archive(updated, max_size)
        return updated

    def _update_boundary_archive(self, archive: List[Dict], candidates: List[Dict], max_size: int) -> List[Dict]:
        if max_size <= 0:
            return []
        pool = archive[:] + candidates
        if not pool:
            return []
        pool_sorted = sorted(
            pool,
            key=lambda a: (float(a.get('violation', 0.0)), float(np.mean(a['objectives'])))
        )
        return pool_sorted[:max_size]

    def _update_diversity_archive(self, archive: List[Dict], candidates: List[Dict], max_size: int) -> List[Dict]:
        if max_size <= 0:
            return []
        pool = archive[:] + candidates
        if not pool:
            return []
        return self._prune_archive(pool, max_size)

    def _prune_archive(self, archive: List[Dict], max_size: int) -> List[Dict]:
        """keep diverse subset based on objective distance"""
        if len(archive) <= max_size:
            return archive
        try:
            objs = np.asarray([a['objectives'] for a in archive], dtype=float)
            if objs.ndim == 1:
                objs = objs.reshape(-1, 1)
            distances = cdist(objs, objs)
            np.fill_diagonal(distances, np.inf)
            min_dist = distances.min(axis=1)
            keep_idx = np.argsort(-min_dist)[:max_size]
            return [archive[i] for i in keep_idx]
        except Exception:
            sorted_idx = sorted(range(len(archive)), key=lambda i: float(np.mean(archive[i]['objectives'])))
            keep_idx = sorted_idx[:max_size]
            return [archive[i] for i in keep_idx]

    def _select_archive_candidates(self, role: AgentRole, k: int) -> List[np.ndarray]:
        """select archive candidates per role"""
        if k <= 0:
            return []

        if role == AgentRole.EXPLORER:
            picked = self._select_from_archives(['diversity', 'feasible'], k, strategy='diverse')
        elif role == AgentRole.EXPLOITER:
            picked = self._select_from_archives(['feasible', 'boundary'], k, strategy='best')
        elif role == AgentRole.WAITER:
            picked = self._select_from_archives(['boundary', 'diversity'], k, strategy='best')
        elif role == AgentRole.ADVISOR:
            best_k = max(1, k // 2)
            picked = self._select_from_archives(['feasible', 'boundary'], best_k, strategy='best')
            picked += self._select_from_archives(['diversity'], k - best_k, strategy='diverse')
        elif role == AgentRole.COORDINATOR:
            best_k = max(1, k // 2)
            picked = self._select_from_archives(['feasible'], best_k, strategy='best')
            picked += self._select_from_archives(['boundary'], k - best_k, strategy='best')
        else:
            picked = self._select_from_archives(['feasible', 'diversity', 'boundary'], k, strategy='random')

        jitter = float(self.config.get('archive_inject_jitter', 0.01))
        role_pop = self.agent_populations.get(role)
        bounds = self._get_effective_bounds(role_pop.bias_profile) if role_pop else self.var_bounds
        out = []
        for item in picked:
            x = item['x'].copy()
            if jitter > 0:
                x = x + np.random.randn(len(x)) * jitter
            x = self._clip_to_bounds(x, bounds)
            out.append(x)
        return out

    def _select_from_archives(self, names: List[str], k: int, strategy: str = 'best') -> List[Dict]:
        archive = self._get_first_archive(names)
        if not archive:
            return []
        if strategy == 'diverse':
            return self._pick_diverse_candidates(archive, k)
        if strategy == 'random':
            return self._pick_random_candidates(archive, k)
        return self._pick_best_candidates(archive, k)

    def _get_first_archive(self, names: List[str]) -> List[Dict]:
        for name in names:
            archive = self.archives.get(name, [])
            if archive:
                return archive
        return []

    def _pick_best_candidates(self, archive: List[Dict], k: int) -> List[Dict]:
        if not archive:
            return []
        sorted_arc = sorted(
            archive,
            key=lambda a: (float(a.get('violation', 0.0)), float(np.mean(a['objectives'])))
        )
        return sorted_arc[:k]

    def _pick_diverse_candidates(self, archive: List[Dict], k: int) -> List[Dict]:
        if not archive:
            return []
        objs = np.asarray([a['objectives'] for a in archive], dtype=float)
        if objs.ndim == 1:
            objs = objs.reshape(-1, 1)
        distances = cdist(objs, objs)
        np.fill_diagonal(distances, np.inf)
        min_dist = distances.min(axis=1)
        keep_idx = np.argsort(-min_dist)[:k]
        return [archive[i] for i in keep_idx]

    def _pick_random_candidates(self, archive: List[Dict], k: int) -> List[Dict]:
        if not archive:
            return []
        k = min(k, len(archive))
        return random.sample(archive, k=k)

    def _inject_archive_candidates(self, pop: AgentPopulation, candidates: List[np.ndarray]) -> None:
        if not candidates or not pop.population:
            return
        replace_count = min(len(candidates), len(pop.population))
        if pop.fitness and len(pop.fitness) == len(pop.population):
            worst_idx = np.argsort(pop.fitness)[:replace_count].tolist()
        else:
            worst_idx = random.sample(range(len(pop.population)), k=replace_count)
        for idx, candidate in zip(worst_idx, candidates):
            pop.population[idx] = candidate
        pop.objectives = []
        pop.constraints = []
        pop.fitness = []
        pop.best_individual = None
        pop.best_objectives = None
        pop.best_constraints = None

