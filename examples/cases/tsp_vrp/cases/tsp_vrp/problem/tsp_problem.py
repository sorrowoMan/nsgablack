"""
TSP / VRP combinatorial route optimization problem.

Uses random-keys encoding: each city has a continuous key value;
the visiting order is obtained by sorting keys (argsort).

VRP extension splits the permutation into vehicle routes with
capacity and depot constraints evaluated via bias.
"""
from __future__ import annotations

import numpy as np
from nsgablack.core.base import BlackBoxProblem


class TSPProblem(BlackBoxProblem):
    """Traveling Salesman Problem with distance matrix.

    Candidate: continuous vector x[i] for city i.
    Permutation: argsort(x).
    Route length = sum of distances along the sorted order.

    VRP mode (optional): treats the first `depot` cities as depots.
    """

    def __init__(
        self,
        distance_matrix: np.ndarray,
        *,
        n_vehicles: int = 1,
        capacity: float | None = None,
        demands: np.ndarray | None = None,
        name: str = "tsp",
    ):
        dm = np.asarray(distance_matrix, dtype=float)
        if dm.ndim != 2 or dm.shape[0] != dm.shape[1]:
            raise ValueError("distance_matrix must be square")
        self.distance_matrix = dm
        self.n_cities = dm.shape[0]
        self.n_vehicles = int(n_vehicles)
        self.capacity = float(capacity) if capacity is not None else float("inf")
        self.demands = (
            np.asarray(demands, dtype=float) if demands is not None
            else np.ones(self.n_cities, dtype=float)
        )
        self.is_vrp = self.n_vehicles > 1 or self.capacity < float("inf")

        bounds = [(0.0, 1.0)] * self.n_cities
        objectives = ["route_length"] if not self.is_vrp else ["total_distance", "fleet_usage"]
        super().__init__(
            name=name,
            dimension=self.n_cities,
            bounds=bounds,
            objectives=objectives,
        )

    def decode_permutation(self, x: np.ndarray) -> np.ndarray:
        """Decode continuous vector to city visitation order via argsort."""
        keys = np.asarray(x, dtype=float).ravel()
        return np.argsort(keys).astype(int)

    def evaluate(self, candidate: np.ndarray) -> np.ndarray:
        perm = self.decode_permutation(candidate)
        total_dist = float(self._route_length(perm))
        if not self.is_vrp:
            return np.array([total_dist], dtype=float)
        # VRP: fleet usage = number of vehicles with at least 2 stops
        routes = self._split_routes(perm)
        used = sum(1 for r in routes if len(r) > 2)
        return np.array([total_dist, float(used)], dtype=float)

    def _route_length(self, perm: np.ndarray) -> float:
        dm = self.distance_matrix
        n = len(perm)
        total = 0.0
        for k in range(n - 1):
            total += dm[perm[k], perm[k + 1]]
        total += dm[perm[-1], perm[0]]
        return total

    def _split_routes(self, perm: np.ndarray) -> list[np.ndarray]:
        """Split permutation into vehicle routes via demand accumulation.

        Uses a simple first-fit: accumulate demand until capacity exceeded,
        then start a new route from depot (city 0) implicitly.
        """
        depot = 0
        routes: list[list[int]] = []
        current: list[int] = [depot]
        load = 0.0
        for city in perm:
            if int(city) == depot:
                continue
            d = self.demands[city]
            if load + d > self.capacity and len(current) > 1:
                current.append(depot)
                routes.append(np.array(current, dtype=int))
                current = [depot]
                load = 0.0
            current.append(int(city))
            load += d
        if len(current) > 1:
            current.append(depot)
            routes.append(np.array(current, dtype=int))
        return routes

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        return np.zeros(0, dtype=float)

    def compute_route_lengths(self, perm: np.ndarray) -> tuple[list[np.ndarray], list[float]]:
        """Compute route segments and their lengths for bias analysis."""
        routes = self._split_routes(perm)
        lengths = [float(self._route_length(r)) for r in routes]
        return routes, lengths

    def compute_subtour_penalty(self, perm: np.ndarray) -> tuple[float, dict]:
        """Compute penalty for subtours and constraint violations.

        TSP: penalty = 0 (argsort guarantees valid permutation)
        VRP: penalty for capacity violations, missing depot visits.
        """
        details: dict = {"capacity_violation": 0.0, "depot_violation": 0.0}
        if not self.is_vrp:
            return 0.0, details

        routes = self._split_routes(perm)
        depot = 0
        cap_violation = 0.0
        depot_violation = 0.0
        for route in routes:
            route_demand = sum(self.demands[int(c)] for c in route if c != depot)
            if route_demand > self.capacity:
                cap_violation += route_demand - self.capacity
            if len(route) > 0 and route[0] != depot:
                depot_violation += 1.0
            if len(route) > 0 and route[-1] != depot:
                depot_violation += 1.0

        penalty = cap_violation * 1000.0 + depot_violation * 10000.0
        details["capacity_violation"] = float(cap_violation)
        details["depot_violation"] = float(depot_violation)
        return penalty, details


class TSPVRPProblem(TSPProblem):
    """Alias with VRP defaults. Prefer TSPProblem(..., n_vehicles=..., capacity=...)."""

    def __init__(
        self,
        distance_matrix: np.ndarray,
        *,
        n_vehicles: int = 2,
        capacity: float = 100.0,
        demands: np.ndarray | None = None,
    ):
        super().__init__(
            distance_matrix,
            n_vehicles=n_vehicles,
            capacity=capacity,
            demands=demands,
            name="tsp_vrp",
        )
