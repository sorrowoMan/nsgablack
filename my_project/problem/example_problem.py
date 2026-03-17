# -*- coding: utf-8 -*-
"""Example problem: simple two-objective continuous optimization."""

from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem


class ExampleProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 8) -> None:
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
        super().__init__(
            name="ExampleProblem",
            dimension=dimension,
            bounds=bounds,
            objectives=["sphere", "l1"],
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float).reshape(-1)
        f1 = float(np.sum(arr ** 2))
        f2 = float(np.sum(np.abs(arr)))
        return np.array([f1, f2], dtype=float)

    def evaluate_batch(self, population: np.ndarray) -> np.ndarray:
        pop = np.asarray(population, dtype=float)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)
        f1 = np.sum(pop ** 2, axis=1, keepdims=True)
        f2 = np.sum(np.abs(pop), axis=1, keepdims=True)
        return np.concatenate([f1, f2], axis=1)

    def evaluate_gpu_batch(
        self,
        population: np.ndarray,
        *,
        backend: str,
        device: str = "cuda:0",
    ) -> np.ndarray:
        pop = np.asarray(population, dtype=float)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)
        name = str(backend or "").strip().lower()
        if name == "torch":
            import torch  # type: ignore

            t = torch.as_tensor(pop, dtype=torch.float32, device=device)
            f1 = torch.sum(t * t, dim=1, keepdim=True)
            f2 = torch.sum(torch.abs(t), dim=1, keepdim=True)
            out = torch.cat([f1, f2], dim=1)
            return out.detach().cpu().numpy()
        if name == "cupy":
            import cupy as cp  # type: ignore

            t = cp.asarray(pop)
            f1 = cp.sum(t * t, axis=1, keepdims=True)
            f2 = cp.sum(cp.abs(t), axis=1, keepdims=True)
            out = cp.concatenate([f1, f2], axis=1)
            return cp.asnumpy(out)
        raise ValueError(f"Unsupported GPU backend: {backend}")

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        # No hard constraints in this minimal example.
        return np.zeros(0, dtype=float)

    def evaluate_constraints_batch(self, population: np.ndarray) -> np.ndarray:
        pop = np.asarray(population, dtype=float)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)
        return np.zeros((pop.shape[0], 0), dtype=float)

    def evaluate_batch_auto(
        self,
        population: np.ndarray,
        *,
        backend: str = "auto",
        device: str = "cuda:0",
    ) -> np.ndarray:
        """Unified batch evaluation entry (GPU if available, else CPU)."""
        pop = np.asarray(population, dtype=float)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)

        selected = self._select_gpu_backend(backend)
        if selected is not None:
            try:
                return self.evaluate_gpu_batch(pop, backend=selected, device=device)
            except Exception:
                # Fallback to CPU path on any GPU failure.
                pass
        return self.evaluate_batch(pop)

    @staticmethod
    def _select_gpu_backend(preferred: str) -> str | None:
        pref = str(preferred or "auto").strip().lower()
        candidates = [pref] if pref in {"torch", "cupy"} else ["torch", "cupy"]
        for name in candidates:
            try:
                if name == "torch":
                    import torch  # type: ignore

                    if bool(torch.cuda.is_available()):
                        return "torch"
                if name == "cupy":
                    import cupy  # type: ignore  # noqa: F401

                    return "cupy"
            except Exception:
                continue
        return None
