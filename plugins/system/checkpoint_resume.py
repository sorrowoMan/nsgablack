from __future__ import annotations

import copy
import os
import pickle
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..base import Plugin
from ...utils.context.context_keys import (
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_CHECKPOINT_LAST_LOADED_PATH,
    KEY_CHECKPOINT_LATEST_PATH,
)


@dataclass
class CheckpointResumeConfig:
    checkpoint_dir: str = "runs/checkpoints"
    file_prefix: str = "checkpoint"
    save_every: int = 10
    save_on_finish: bool = True
    keep_last: int = 5
    auto_resume: bool = False
    resume_from: str = "latest"  # "latest" or explicit path
    restore_plugin_state: bool = True
    restore_rng_state: bool = True
    strict: bool = False


class CheckpointResumePlugin(Plugin):
    context_requires = ()
    context_provides = (KEY_CHECKPOINT_LATEST_PATH, KEY_CHECKPOINT_LAST_LOADED_PATH)
    context_mutates = (KEY_CHECKPOINT_LATEST_PATH,)
    context_cache = (KEY_CHECKPOINT_LATEST_PATH,)
    context_notes = (
        "Persists solver/adapters/plugin state as checkpoint files and can resume from latest/path.",
    )
    """
    Checkpoint + resume plugin.

    Save points are generation-boundary snapshots. Resume restores solver state,
    adapter state, optional plugin state, and optional RNG state.
    """

    SCHEMA = "nsgablack.checkpoint.v1"

    def __init__(
        self,
        name: str = "checkpoint_resume",
        *,
        config: Optional[CheckpointResumeConfig] = None,
    ) -> None:
        super().__init__(name=name)
        self.cfg = config or CheckpointResumeConfig()
        self.latest_checkpoint_path: Optional[str] = None
        self.last_loaded_path: Optional[str] = None
        self.last_saved_generation: Optional[int] = None
        self.last_loaded_generation: Optional[int] = None
        self.is_algorithmic = False
        # Allow solver.add_plugin() to fail-fast when strict resume is requested.
        self.raise_on_init_error = bool(self.cfg.strict)

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------
    def on_solver_init(self, solver):
        if not bool(self.cfg.auto_resume):
            return None
        try:
            self.resume(self.cfg.resume_from)
        except Exception:
            if bool(self.cfg.strict):
                raise
        return None

    def on_generation_end(self, generation: int):
        save_every = int(self.cfg.save_every)
        if save_every <= 0:
            return None
        if int(generation) <= 0:
            return None
        if int(generation) % save_every != 0:
            return None
        self.save_checkpoint(reason="generation_end")
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        if bool(self.cfg.save_on_finish):
            path = self.save_checkpoint(reason="solver_finish")
            if path is not None and isinstance(result, dict):
                result["checkpoint_latest"] = str(path)
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def save_checkpoint(self, *, reason: str = "manual") -> Optional[Path]:
        solver = self.solver
        if solver is None:
            return None

        ckpt_dir = Path(self.cfg.checkpoint_dir).resolve()
        ckpt_dir.mkdir(parents=True, exist_ok=True)

        generation = int(getattr(solver, "generation", 0))
        stamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{self.cfg.file_prefix}_g{generation:06d}_{stamp}.pkl"
        target = ckpt_dir / filename

        payload = self._build_payload(solver=solver, reason=reason)
        self._atomic_write_pickle(target, payload)
        self.latest_checkpoint_path = str(target)
        self.last_saved_generation = generation

        self._apply_retention(ckpt_dir)
        return target

    def resume(self, checkpoint: str = "latest") -> bool:
        solver = self.solver
        if solver is None:
            return False
        path = self._resolve_checkpoint_path(checkpoint)
        if path is None:
            if bool(self.cfg.strict):
                raise FileNotFoundError(f"checkpoint not found: {checkpoint}")
            return False

        with path.open("rb") as f:
            # SECURITY NOTE: pickle.load can execute arbitrary code.
            # Only load checkpoints from trusted sources (your own runs).
            payload = pickle.load(f)  # nosec B301
        self._restore_payload(solver=solver, payload=payload)
        self.last_loaded_path = str(path)
        self.last_loaded_generation = int(getattr(solver, "generation", 0))
        self.latest_checkpoint_path = str(path)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_checkpoint_path(self, checkpoint: str) -> Optional[Path]:
        text = str(checkpoint or "").strip()
        if text and text.lower() != "latest":
            path = Path(text)
            if not path.is_absolute():
                path = Path(self.cfg.checkpoint_dir).resolve() / path
            return path if path.exists() else None

        ckpt_dir = Path(self.cfg.checkpoint_dir).resolve()
        if not ckpt_dir.exists():
            return None

        pattern = f"{self.cfg.file_prefix}_g*.pkl"
        candidates = sorted(
            ckpt_dir.glob(pattern),
            key=lambda p: (p.stat().st_mtime, p.name),
            reverse=True,
        )
        if not candidates:
            return None
        return candidates[0]

    def _atomic_write_pickle(self, path: Path, payload: Dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)

    def _apply_retention(self, checkpoint_dir: Path) -> None:
        keep_last = int(self.cfg.keep_last)
        if keep_last <= 0:
            return
        pattern = f"{self.cfg.file_prefix}_g*.pkl"
        files = sorted(
            checkpoint_dir.glob(pattern),
            key=lambda p: (p.stat().st_mtime, p.name),
            reverse=True,
        )
        for path in files[keep_last:]:
            try:
                path.unlink()
            except Exception:
                continue

    def _safe_copy(self, value: Any) -> Any:
        try:
            return copy.deepcopy(value)
        except Exception:
            return value

    def _collect_adapter_state(self, solver: Any) -> Optional[Dict[str, Any]]:
        adapter = getattr(solver, "adapter", None)
        if adapter is None:
            return None
        getter = getattr(adapter, "get_state", None)
        if not callable(getter):
            return None
        try:
            return self._safe_copy(getter())
        except Exception:
            return None

    def _collect_plugin_states(self, solver: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        manager = getattr(solver, "plugin_manager", None)
        if manager is None or not hasattr(manager, "list_plugins"):
            return out
        for plugin in manager.list_plugins(enabled_only=False):
            if plugin is self:
                continue
            getter = getattr(plugin, "get_state", None)
            if not callable(getter):
                continue
            try:
                out[str(getattr(plugin, "name", plugin.__class__.__name__))] = self._safe_copy(getter())
            except Exception:
                continue
        return out

    def _infer_resume_cursor(self, solver: Any, generation: int) -> int:
        if hasattr(solver, "max_steps") and not hasattr(solver, "max_generations"):
            return max(0, int(generation) + 1)
        return max(0, int(generation))

    def _build_payload(self, *, solver: Any, reason: str) -> Dict[str, Any]:
        generation = int(getattr(solver, "generation", 0))
        best_x_ctx, best_obj_ctx = self._resolve_context_best(solver)
        snap_pop, snap_obj, snap_vio = self.resolve_population_snapshot(solver)
        solver_state = {
            "generation": generation,
            "evaluation_count": int(getattr(solver, "evaluation_count", 0)),
            "population": self._safe_copy(snap_pop),
            "objectives": self._safe_copy(snap_obj),
            "constraint_violations": self._safe_copy(snap_vio),
            "pareto_solutions": self._safe_copy(getattr(solver, "pareto_solutions", None)),
            "pareto_objectives": self._safe_copy(getattr(solver, "pareto_objectives", None)),
            "history": self._safe_copy(getattr(solver, "history", None)),
            "best_x": self._safe_copy(best_x_ctx if best_x_ctx is not None else getattr(solver, "best_x", None)),
            "best_f": self._safe_copy(getattr(solver, "best_f", None)),
            "best_objective": self._safe_copy(
                best_obj_ctx if best_obj_ctx is not None else getattr(solver, "best_objective", None)
            ),
            "random_seed": self._safe_copy(getattr(solver, "random_seed", None)),
        }

        payload = {
            "schema": self.SCHEMA,
            "saved_at": float(time.time()),
            "reason": str(reason),
            "solver_module": str(solver.__class__.__module__),
            "solver_class": str(solver.__class__.__name__),
            "solver_state": solver_state,
            "resume_cursor": self._infer_resume_cursor(solver, generation),
            "adapter_state": self._collect_adapter_state(solver),
            "plugin_states": self._collect_plugin_states(solver),
            "rng_state": {
                "solver_numpy": self._safe_copy(
                    getattr(solver, "get_rng_state", lambda: None)()
                ),
                "python": random.getstate(),
            },
            "meta": {
                "max_generations": getattr(solver, "max_generations", None),
                "max_steps": getattr(solver, "max_steps", None),
                "pop_size": getattr(solver, "pop_size", None),
            },
        }
        return payload

    def _resolve_context_best(self, solver: Any) -> tuple[Any, Optional[float]]:
        getter = getattr(solver, "get_context", None)
        if not callable(getter):
            return None, None
        try:
            ctx = getter()
        except Exception:
            return None, None
        if not isinstance(ctx, dict):
            return None, None
        best_x = ctx.get(KEY_BEST_X)
        best_obj_raw = ctx.get(KEY_BEST_OBJECTIVE)
        best_obj: Optional[float] = None
        if best_obj_raw is not None:
            try:
                best_obj = float(best_obj_raw)
            except Exception:
                best_obj = None
        return best_x, best_obj

    def _apply_solver_state(self, solver: Any, state: Dict[str, Any], resume_cursor: Optional[int]) -> None:
        generation = int(state.get("generation", getattr(solver, "generation", 0)))
        setattr(solver, "generation", generation)
        setattr(solver, "evaluation_count", int(state.get("evaluation_count", getattr(solver, "evaluation_count", 0))))
        if (
            "population" in state
            and "objectives" in state
            and "constraint_violations" in state
        ):
            writer = getattr(solver, "write_population_snapshot", None)
            if callable(writer):
                try:
                    writer(
                        state.get("population"),
                        state.get("objectives"),
                        state.get("constraint_violations"),
                    )
                except Exception:
                    if bool(self.cfg.strict):
                        raise

        for key in (
            "pareto_solutions",
            "pareto_objectives",
            "history",
            "best_x",
            "best_f",
            "best_objective",
            "random_seed",
        ):
            if key in state:
                setattr(solver, key, state.get(key))

        setattr(solver, "_resume_loaded", True)
        if resume_cursor is None:
            setattr(solver, "_resume_cursor", generation)
        else:
            setattr(solver, "_resume_cursor", int(resume_cursor))

    def _apply_adapter_state(self, solver: Any, adapter_state: Any) -> None:
        if adapter_state is None:
            return
        adapter = getattr(solver, "adapter", None)
        if adapter is None:
            return
        setter = getattr(adapter, "set_state", None)
        if not callable(setter):
            return
        try:
            setter(adapter_state)
        except Exception:
            if bool(self.cfg.strict):
                raise

    def _apply_plugin_states(self, solver: Any, plugin_states: Dict[str, Any]) -> None:
        if not bool(self.cfg.restore_plugin_state):
            return
        if not isinstance(plugin_states, dict):
            return
        manager = getattr(solver, "plugin_manager", None)
        if manager is None or not hasattr(manager, "get"):
            return
        for name, state in plugin_states.items():
            plugin = manager.get(str(name))
            if plugin is None or plugin is self:
                continue
            setter = getattr(plugin, "set_state", None)
            if not callable(setter):
                continue
            try:
                setter(state)
            except Exception:
                if bool(self.cfg.strict):
                    raise

    def _apply_rng_state(self, solver: Any, rng_state: Dict[str, Any]) -> None:
        if not bool(self.cfg.restore_rng_state):
            return
        if not isinstance(rng_state, dict):
            return
        np_state = rng_state.get("solver_numpy")
        py_state = rng_state.get("python")
        if np_state is not None:
            try:
                setter = getattr(solver, "set_rng_state", None)
                if callable(setter):
                    setter(np_state)
            except Exception:
                if bool(self.cfg.strict):
                    raise
        if py_state is not None:
            try:
                random.setstate(py_state)
            except Exception:
                if bool(self.cfg.strict):
                    raise
        setattr(solver, "_resume_rng_state", rng_state)

    def _restore_payload(self, *, solver: Any, payload: Dict[str, Any]) -> None:
        schema = str(payload.get("schema", "")).strip()
        if schema != self.SCHEMA:
            if bool(self.cfg.strict):
                raise ValueError(f"unsupported checkpoint schema: {schema}")

        state = payload.get("solver_state")
        if not isinstance(state, dict):
            raise ValueError("invalid checkpoint payload: missing solver_state")

        resume_cursor = payload.get("resume_cursor")
        self._apply_solver_state(solver, state, resume_cursor if isinstance(resume_cursor, int) else None)
        self._apply_adapter_state(solver, payload.get("adapter_state"))
        self._apply_plugin_states(solver, payload.get("plugin_states", {}))
        self._apply_rng_state(solver, payload.get("rng_state", {}))

    def get_report(self) -> Optional[Dict[str, Any]]:
        return {
            "checkpoint_dir": str(self.cfg.checkpoint_dir),
            "save_every": int(self.cfg.save_every),
            "auto_resume": bool(self.cfg.auto_resume),
            "latest_checkpoint_path": self.latest_checkpoint_path,
            "last_loaded_path": self.last_loaded_path,
            "last_saved_generation": self.last_saved_generation,
            "last_loaded_generation": self.last_loaded_generation,
        }
