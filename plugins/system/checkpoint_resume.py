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
from typing import Any, Dict, Mapping, Optional

from ..base import Plugin
from ...core.state.incumbent import DEFAULT_INCUMBENT_POLICY_ID, IncumbentState
from blackbase.context.context_keys import (
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
    artifact_provides = (KEY_CHECKPOINT_LATEST_PATH, KEY_CHECKPOINT_LAST_LOADED_PATH)
    context_notes = (
        "Persists solver/adapters/plugin state as checkpoint files and can resume from latest/path.",
    )
    """
    Checkpoint + resume plugin.

    Save points are generation-boundary snapshots. Resume restores solver state,
    adapter state, optional plugin state, and optional RNG state.
    """

    SCHEMA_V1 = "nsgablack.checkpoint.v1"
    SCHEMA_V2 = "nsgablack.checkpoint.v2"
    SCHEMA = SCHEMA_V2
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
        path = self._get_checkpoint_path(checkpoint)
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
    def _get_checkpoint_path(self, checkpoint: str) -> Optional[Path]:
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

    def _get_hmac_key(self) -> Optional[bytes]:
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
        key = self._get_hmac_key()
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
        key = self._get_hmac_key()
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

        key = self._get_hmac_key()
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
        snap_pop, snap_obj, snap_vio = self.get_population_snapshot(solver)
        projection_payload: Dict[str, Any] = {}
        export_incumbent = getattr(solver, "export_incumbent_checkpoint_state", None)
        if callable(export_incumbent):
            incumbent_export = dict(export_incumbent() or {})
            incumbent_payload = incumbent_export.get("incumbent")
            projection_payload = dict(
                incumbent_export.get("incumbent_projection", {}) or {}
            )
            selection_payload = dict(
                incumbent_export.get("incumbent_selection", {}) or {}
            )
        else:
            get_incumbent = getattr(solver, "get_incumbent", None)
            incumbent = get_incumbent() if callable(get_incumbent) else None
            incumbent_payload = (
                None if incumbent is None else incumbent.as_dict()
            )
            incumbent_dict = dict(incumbent_payload or {})
            selection_policy_context = getattr(
                solver,
                "incumbent_scalarizer_context",
                incumbent_dict.get("policy_context", {}),
            )
            selection_payload = {
                "policy_id": str(
                    getattr(
                        solver,
                        "incumbent_scalarizer_id",
                        incumbent_dict.get(
                            "policy_id",
                            DEFAULT_INCUMBENT_POLICY_ID,
                        ),
                    )
                ),
                "policy_context": dict(selection_policy_context or {}),
                "failure_policy": getattr(
                    solver,
                    "scalarizer_failure_policy",
                    "raise",
                ),
                "fallback_count": int(
                    getattr(solver, "scalarizer_fallback_count", 0) or 0
                ),
                "result_quality_degraded": getattr(
                    solver,
                    "result_quality_degraded",
                    False,
                ),
                "audit_complete": bool(
                    getattr(solver, "scalarizer_audit_complete", True)
                ),
            }
        if not projection_payload:
            get_projection_audit = getattr(
                solver,
                "get_incumbent_projection_audit",
                None,
            )
            if callable(get_projection_audit):
                projection_payload = dict(get_projection_audit() or {})
        solver_state = {
            "generation": generation,
            "evaluation_count": int(getattr(solver, "evaluation_count", 0)),
            "population": self._safe_copy(snap_pop),
            "objectives": self._safe_copy(snap_obj),
            "constraint_violations": self._safe_copy(snap_vio),
            "pareto_solutions": self._safe_copy(getattr(solver, "pareto_solutions", None)),
            "pareto_objectives": self._safe_copy(getattr(solver, "pareto_objectives", None)),
            "history": self._safe_copy(getattr(solver, "history", None)),
            "incumbent": (
                None
                if incumbent_payload is None
                else self._safe_copy(incumbent_payload)
            ),
            "active_run_id": getattr(solver, "_active_run_id", None),
            "run_sequence": int(getattr(solver, "_run_sequence", 0) or 0),
            "incumbent_projection": self._safe_copy(projection_payload),
            "incumbent_selection": self._safe_copy(selection_payload),
            "random_seed": self._safe_copy(getattr(solver, "random_seed", None)),
        }
        self._validate_checkpoint_internal_selection(solver, solver_state)
        self._validate_checkpoint_projection_audit(solver_state)

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

    def _apply_solver_state(self, solver: Any, state: Dict[str, Any], resume_cursor: Optional[int]) -> None:
        generation = int(state.get("generation", getattr(solver, "generation", 0)))
        eval_count = int(state.get("evaluation_count", getattr(solver, "evaluation_count", 0)))
        def _set_field(field: str, value: Any) -> None:
            setattr(solver, str(field), value)

        set_generation = getattr(solver, "set_generation", None)
        if callable(set_generation):
            try:
                set_generation(generation)
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
        else:
            _set_field("evaluation_count", eval_count)
        if state.get("active_run_id") is not None:
            _set_field("_active_run_id", str(state.get("active_run_id")))
        if state.get("run_sequence") is not None:
            restored_sequence = max(0, int(state.get("run_sequence", 0) or 0))
            current_sequence = max(0, int(getattr(solver, "_run_sequence", 0) or 0))
            _set_field("_run_sequence", max(current_sequence, restored_sequence))
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
            else:
                _set_field("pareto_solutions", state.get("pareto_solutions"))
                _set_field("pareto_objectives", state.get("pareto_objectives"))

        if "history" in state:
            _set_field("history", state.get("history"))
        projection_audit = state.get("incumbent_projection")
        record_projection_audit = getattr(
            solver,
            "_record_restored_incumbent_projection_audit",
            None,
        )
        if callable(record_projection_audit):
            record_projection_audit(
                projection_audit if isinstance(projection_audit, Mapping) else None
            )
        incumbent_payload = state.get("incumbent")
        if isinstance(incumbent_payload, dict):
            incumbent = IncumbentState.from_dict(incumbent_payload)
            set_incumbent = getattr(solver, "set_incumbent", None)
            if not callable(set_incumbent):
                raise TypeError("checkpoint target does not support atomic incumbent restore")
            set_incumbent(incumbent)
        elif self._legacy_incumbent_payload(state) is not None:
            incumbent = IncumbentState.from_dict(self._legacy_incumbent_payload(state))
            set_incumbent = getattr(solver, "set_incumbent", None)
            if not callable(set_incumbent):
                raise TypeError("checkpoint target does not support atomic incumbent restore")
            set_incumbent(incumbent)
        else:
            incomplete_best = state.get("legacy_best_snapshot")
            if not isinstance(incomplete_best, dict) and (
                "best_x" in state or "best_objective" in state
            ):
                incomplete_best = {
                    "candidate": state.get("best_x"),
                    "score": state.get("best_objective", state.get("best_f")),
                }
            if isinstance(incomplete_best, dict) and incomplete_best.get("candidate") is not None:
                raise ValueError(
                    "checkpoint contains an incomplete best candidate without "
                    "objectives and constraint evidence; it cannot be restored "
                    "as an authoritative incumbent"
                )
            else:
                clear_incumbent = getattr(solver, "clear_incumbent", None)
                if callable(clear_incumbent):
                    clear_incumbent()
        selection = state.get("incumbent_selection")
        if isinstance(selection, dict):
            if hasattr(solver, "scalarizer_fallback_count"):
                fallback_count = selection.get("fallback_count")
                if fallback_count is not None:
                    _set_field("scalarizer_fallback_count", int(fallback_count))
            if hasattr(solver, "result_quality_degraded"):
                _set_field(
                    "result_quality_degraded",
                    selection.get("result_quality_degraded"),
                )
            if hasattr(solver, "scalarizer_audit_complete"):
                _set_field(
                    "scalarizer_audit_complete",
                    bool(selection.get("audit_complete", False)),
                )
        if "random_seed" in state:
            _set_field("random_seed", state.get("random_seed"))

        setattr(solver, "_resume_loaded", True)
        if resume_cursor is None:
            setattr(solver, "_resume_cursor", generation)
        else:
            setattr(solver, "_resume_cursor", int(resume_cursor))

    @staticmethod
    def _legacy_incumbent_payload(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        candidate = state.get("best_x")
        objectives = state.get("best_objectives")
        violation = state.get("best_constraint_violation")
        score = state.get(
            "best_score",
            state.get("best_objective", state.get("best_f")),
        )
        if any(value is None for value in (candidate, objectives, violation, score)):
            return None
        return {
            "candidate": candidate,
            "objectives": objectives,
            "constraint_violation": violation,
            "score": score,
            "policy_id": DEFAULT_INCUMBENT_POLICY_ID,
            "source": "checkpoint_legacy",
            "source_run_id": state.get("active_run_id"),
            "metadata": {"migrated_from_legacy_fields": True},
        }

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

    @staticmethod
    def _run_sequence_from_id(active_run_id: Any) -> int:
        text = str(active_run_id or "")
        marker = ":solver-run:"
        if marker not in text:
            return 0
        suffix = text.split(marker, 1)[1]
        try:
            return max(0, int(suffix.split(":", 1)[0]))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _migrate_payload(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        schema = str(payload.get("schema", "")).strip()
        if schema == cls.SCHEMA_V2:
            return payload
        if schema != cls.SCHEMA_V1:
            raise ValueError(f"unsupported checkpoint schema: {schema or '<missing>'}")

        migrated = copy.deepcopy(payload)
        state = migrated.get("solver_state")
        if not isinstance(state, dict):
            raise ValueError("invalid checkpoint payload: missing solver_state")
        incumbent_payload = state.get("incumbent")
        if isinstance(incumbent_payload, dict):
            policy_id = str(
                incumbent_payload.get("policy_id", DEFAULT_INCUMBENT_POLICY_ID)
            )
            policy_context = dict(
                incumbent_payload.get("policy_context", {}) or {}
            )
        else:
            policy_id = DEFAULT_INCUMBENT_POLICY_ID
            policy_context = {}
        state.setdefault(
            "incumbent_selection",
            {
                "policy_id": policy_id,
                "policy_context": policy_context,
                "failure_policy": None,
                "fallback_count": None,
                "result_quality_degraded": None,
                "audit_complete": False,
            },
        )
        state.setdefault(
            "run_sequence",
            cls._run_sequence_from_id(state.get("active_run_id")),
        )
        migrated["schema"] = cls.SCHEMA_V2
        migrated["migrated_from_schema"] = cls.SCHEMA_V1
        return migrated

    @staticmethod
    def _selection_contexts_match(
        solver: Any,
        left: Mapping[str, Any],
        right: Mapping[str, Any],
    ) -> bool:
        signature = getattr(solver, "_policy_context_signature", None)
        if callable(signature):
            return signature(dict(left)) == signature(dict(right))
        return dict(left) == dict(right)

    @classmethod
    def _validate_checkpoint_internal_selection(
        cls,
        solver: Any,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        selection = state.get("incumbent_selection")
        if not isinstance(selection, dict):
            raise ValueError("checkpoint v2 is missing incumbent_selection audit state")

        saved_policy_id = str(selection.get("policy_id", "") or "").strip()
        if not saved_policy_id:
            raise ValueError("checkpoint incumbent_selection policy_id must not be empty")
        incumbent = state.get("incumbent")
        if isinstance(incumbent, dict):
            incumbent_policy_id = str(
                incumbent.get("policy_id", DEFAULT_INCUMBENT_POLICY_ID) or ""
            ).strip()
            if incumbent_policy_id != saved_policy_id:
                raise ValueError(
                    "checkpoint incumbent/selection policy mismatch: "
                    f"incumbent={incumbent_policy_id!r}, "
                    f"selection={saved_policy_id!r}"
                )
            incumbent_context = dict(incumbent.get("policy_context", {}) or {})
            selection_context = dict(selection.get("policy_context", {}) or {})
            if not cls._selection_contexts_match(
                solver,
                incumbent_context,
                selection_context,
            ):
                raise ValueError(
                    "checkpoint incumbent/selection policy context mismatch"
                )
        return selection

    @staticmethod
    def _validate_checkpoint_projection_audit(
        state: Mapping[str, Any],
    ) -> None:
        projection = state.get("incumbent_projection")
        if projection is None:
            return
        if not isinstance(projection, Mapping):
            raise ValueError("checkpoint incumbent_projection audit must be a mapping")
        required = (
            "incumbent_revision",
            "incumbent_context_projection_revision",
            "incumbent_context_projection_current",
            "incumbent_context_projection_error",
        )
        missing = [key for key in required if key not in projection]
        if missing:
            raise ValueError(
                "checkpoint incumbent_projection audit is missing fields: "
                + ", ".join(missing)
            )
        incumbent_revision = int(projection["incumbent_revision"])
        published_revision = int(
            projection["incumbent_context_projection_revision"]
        )
        if published_revision > incumbent_revision:
            raise ValueError(
                "checkpoint incumbent projection revision exceeds incumbent revision"
            )
        error = projection["incumbent_context_projection_error"]
        if error is not None and not isinstance(error, Mapping):
            raise ValueError(
                "checkpoint incumbent projection error must be a mapping or null"
            )
        expected_current = published_revision == incumbent_revision and error is None
        if bool(projection["incumbent_context_projection_current"]) != expected_current:
            raise ValueError(
                "checkpoint incumbent projection current flag is inconsistent"
            )

    @classmethod
    def _validate_incumbent_selection(
        cls,
        solver: Any,
        state: Dict[str, Any],
    ) -> None:
        selection = cls._validate_checkpoint_internal_selection(solver, state)
        cls._validate_checkpoint_projection_audit(state)
        saved_policy_id = str(selection.get("policy_id", "") or "").strip()
        current_policy_id = getattr(solver, "incumbent_scalarizer_id", None)
        if current_policy_id is not None and saved_policy_id != str(current_policy_id):
            raise ValueError(
                "checkpoint incumbent scalarizer policy mismatch: "
                f"saved={saved_policy_id!r}, current={str(current_policy_id)!r}"
            )

        if current_policy_id is not None:
            saved_context = dict(selection.get("policy_context", {}) or {})
            current_context = dict(
                getattr(solver, "incumbent_scalarizer_context", {}) or {}
            )
            if not cls._selection_contexts_match(
                solver,
                saved_context,
                current_context,
            ):
                raise ValueError(
                    "checkpoint incumbent scalarizer context does not match builder configuration"
                )

        saved_failure_policy = selection.get("failure_policy")
        current_failure_policy = getattr(solver, "scalarizer_failure_policy", None)
        if (
            saved_failure_policy is not None
            and current_failure_policy is not None
            and str(saved_failure_policy) != str(current_failure_policy)
        ):
            raise ValueError(
                "checkpoint scalarizer failure policy mismatch: "
                f"saved={saved_failure_policy!r}, current={current_failure_policy!r}"
            )

    def _restore_payload(self, *, solver: Any, payload: Dict[str, Any]) -> None:
        payload = self._migrate_payload(payload)

        state = payload.get("solver_state")
        if not isinstance(state, dict):
            raise ValueError("invalid checkpoint payload: missing solver_state")
        self._validate_incumbent_selection(solver, state)

        resume_cursor = payload.get("resume_cursor")
        self._apply_solver_state(solver, state, resume_cursor if isinstance(resume_cursor, int) else None)
        self._apply_adapter_state(solver, payload.get("adapter_state"))
        self._apply_plugin_states(solver, payload.get("plugin_states", {}))
        self._apply_rng_state(solver, payload.get("rng_state", {}))

    def get_report(self) -> Optional[Dict[str, Any]]:
        return {
            "checkpoint_schema": self.SCHEMA,
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

