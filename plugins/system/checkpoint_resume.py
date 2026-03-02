from __future__ import annotations

import copy
import hashlib
import hmac
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
    hmac_env_var: str = "NSGABLACK_CHECKPOINT_HMAC_KEY"
    unsafe_allow_unsigned: bool = False
    trusted_roots: tuple[str, ...] = ()


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
    ENVELOPE_VERSION = "nsgablack.checkpoint.envelope.v1"

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
        self._assert_strict_security_ready()
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
        self._assert_strict_security_ready()

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
        self._assert_strict_security_ready()
        path = self._resolve_checkpoint_path(checkpoint)
        if path is None:
            if bool(self.cfg.strict):
                raise FileNotFoundError(f"checkpoint not found: {checkpoint}")
            return False

        if not self._is_path_trusted(path):
            msg = f"checkpoint path is not trusted: {path}"
            if bool(self.cfg.strict):
                raise PermissionError(msg)
            return False

        with path.open("rb") as f:
            # SECURITY NOTE: pickle.load can execute arbitrary code.
            # Only load checkpoints from trusted sources (your own runs).
            loaded = pickle.load(f)  # nosec B301
        payload = self._unwrap_and_verify_payload(loaded)
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
        if len(candidates) == 0:
            return None
        return candidates[0]

    def _atomic_write_pickle(self, path: Path, payload: Dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        envelope = self._wrap_payload(payload)
        with tmp.open("wb") as f:
            pickle.dump(envelope, f, protocol=pickle.HIGHEST_PROTOCOL)
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

    def _resolve_hmac_key(self) -> Optional[bytes]:
        env_var = str(getattr(self.cfg, "hmac_env_var", "") or "").strip()
        if not env_var:
            return None
        raw = os.environ.get(env_var)
        if raw is None:
            return None
        key = raw.encode("utf-8")
        return key if key else None

    def _assert_strict_security_ready(self) -> None:
        if not bool(getattr(self.cfg, "strict", False)):
            return
        key = self._resolve_hmac_key()
        if key is None:
            env_var = str(getattr(self.cfg, "hmac_env_var", "NSGABLACK_CHECKPOINT_HMAC_KEY") or "").strip()
            raise ValueError(
                f"strict checkpoint mode requires HMAC key in environment variable: {env_var}"
            )
        if bool(getattr(self.cfg, "unsafe_allow_unsigned", False)):
            raise ValueError("strict checkpoint mode forbids unsafe_allow_unsigned=True")

    def _compute_payload_mac(self, payload: Dict[str, Any], key: bytes) -> str:
        payload_bytes = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
        return hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()

    def _wrap_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        key = self._resolve_hmac_key()
        mac: Optional[str] = None
        if key is not None:
            try:
                mac = self._compute_payload_mac(payload, key)
            except Exception:
                if bool(self.cfg.strict):
                    raise
                mac = None
        return {
            "_checkpoint_envelope": self.ENVELOPE_VERSION,
            "payload": payload,
            "hmac_sha256": mac,
            "hmac_env_var": str(getattr(self.cfg, "hmac_env_var", "NSGABLACK_CHECKPOINT_HMAC_KEY")),
        }

    def _unwrap_and_verify_payload(self, loaded: Any) -> Dict[str, Any]:
        if isinstance(loaded, dict) and "_checkpoint_envelope" in loaded and "payload" in loaded:
            payload = loaded.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("invalid checkpoint envelope: payload missing or invalid")
            provided_mac = loaded.get("hmac_sha256")
        elif isinstance(loaded, dict):
            # Backward compatibility: old checkpoints had raw payload only.
            payload = loaded
            provided_mac = None
        else:
            raise ValueError("invalid checkpoint payload: unsupported type")

        key = self._resolve_hmac_key()
        if bool(getattr(self.cfg, "strict", False)):
            if key is None:
                env_var = str(getattr(self.cfg, "hmac_env_var", "NSGABLACK_CHECKPOINT_HMAC_KEY") or "").strip()
                raise ValueError(
                    f"strict checkpoint mode requires HMAC key in environment variable: {env_var}"
                )
            if not provided_mac:
                raise ValueError("strict checkpoint mode requires signed checkpoint envelope")
        if provided_mac:
            if key is None:
                if bool(self.cfg.strict):
                    raise ValueError(
                        "checkpoint contains HMAC signature but no key is configured in environment"
                    )
            else:
                expected = self._compute_payload_mac(payload, key)
                if not hmac.compare_digest(str(provided_mac), expected):
                    raise ValueError("checkpoint HMAC verification failed")
        elif key is not None and not bool(getattr(self.cfg, "unsafe_allow_unsigned", False)):
            raise ValueError(
                "unsigned checkpoint is blocked; set unsafe_allow_unsigned=True to bypass verification"
            )
        return payload

    def _trusted_root_paths(self) -> tuple[Path, ...]:
        out: list[Path] = [Path(self.cfg.checkpoint_dir).resolve()]
        for raw in getattr(self.cfg, "trusted_roots", ()) or ():
            text = str(raw).strip()
            if not text:
                continue
            out.append(Path(text).resolve())
        return tuple(out)

    def _is_path_trusted(self, path: Path) -> bool:
        candidate = Path(path).resolve()
        for root in self._trusted_root_paths():
            try:
                candidate.relative_to(root)
                return True
            except Exception:
                continue
        return False

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
        runtime = getattr(solver, "runtime", None)
        eval_count = int(state.get("evaluation_count", getattr(solver, "evaluation_count", 0)))
        def _set_field(field: str, value: Any) -> None:
            setattr(solver, str(field), value)

        set_generation = getattr(solver, "set_generation", None)
        if callable(set_generation):
            try:
                set_generation(generation)
            except Exception:
                _set_field("generation", generation)
        elif runtime is not None and hasattr(runtime, "set_generation"):
            try:
                runtime.set_generation(generation)
            except Exception:
                _set_field("generation", generation)
        else:
            _set_field("generation", generation)

        increment_eval = getattr(solver, "increment_evaluation_count", None)
        if callable(increment_eval):
            try:
                current = int(getattr(solver, "evaluation_count", 0) or 0)
                increment_eval(eval_count - current)
            except Exception:
                _set_field("evaluation_count", eval_count)
        elif runtime is not None and hasattr(runtime, "increment_evaluation_count"):
            try:
                current = int(getattr(solver, "evaluation_count", 0) or 0)
                runtime.increment_evaluation_count(eval_count - current)
            except Exception:
                _set_field("evaluation_count", eval_count)
        else:
            _set_field("generation", generation)
            _set_field("evaluation_count", eval_count)
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

        if "pareto_solutions" in state or "pareto_objectives" in state:
            set_pareto = getattr(solver, "set_pareto_snapshot", None)
            if callable(set_pareto):
                try:
                    set_pareto(state.get("pareto_solutions"), state.get("pareto_objectives"))
                except Exception:
                    _set_field("pareto_solutions", state.get("pareto_solutions"))
                    _set_field("pareto_objectives", state.get("pareto_objectives"))
            elif runtime is not None and hasattr(runtime, "set_pareto_snapshot"):
                try:
                    runtime.set_pareto_snapshot(state.get("pareto_solutions"), state.get("pareto_objectives"))
                except Exception:
                    _set_field("pareto_solutions", state.get("pareto_solutions"))
                    _set_field("pareto_objectives", state.get("pareto_objectives"))
            else:
                _set_field("pareto_solutions", state.get("pareto_solutions"))
                _set_field("pareto_objectives", state.get("pareto_objectives"))

        if "history" in state:
            _set_field("history", state.get("history"))
        if "best_x" in state or "best_objective" in state:
            set_best = getattr(solver, "set_best_snapshot", None)
            if callable(set_best):
                try:
                    set_best(state.get("best_x"), state.get("best_objective"))
                except Exception:
                    _set_field("best_x", state.get("best_x"))
                    _set_field("best_objective", state.get("best_objective"))
            elif runtime is not None and hasattr(runtime, "set_best_snapshot"):
                try:
                    runtime.set_best_snapshot(state.get("best_x"), state.get("best_objective"))
                except Exception:
                    _set_field("best_x", state.get("best_x"))
                    _set_field("best_objective", state.get("best_objective"))
            else:
                _set_field("best_x", state.get("best_x"))
                _set_field("best_objective", state.get("best_objective"))
        if "best_f" in state:
            _set_field("best_f", state.get("best_f"))
        if "random_seed" in state:
            _set_field("random_seed", state.get("random_seed"))

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
            "hmac_env_var": str(self.cfg.hmac_env_var),
            "unsafe_allow_unsigned": bool(self.cfg.unsafe_allow_unsigned),
            "trusted_roots": list(self.cfg.trusted_roots or ()),
            "latest_checkpoint_path": self.latest_checkpoint_path,
            "last_loaded_path": self.last_loaded_path,
            "last_saved_generation": self.last_saved_generation,
            "last_loaded_generation": self.last_loaded_generation,
        }
