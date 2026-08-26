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

import numpy as np

from ..base import Plugin
from ...core.state.incumbent import DEFAULT_INCUMBENT_POLICY_ID, IncumbentState
from ...core.state.run_progress import RunProgressState
from blackbase.context.context_keys import (
    KEY_CHECKPOINT_LAST_LOADED_PATH,
    KEY_CHECKPOINT_LATEST_PATH,
)
from blackbase.types import PopulationSnapshot


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
    SCHEMA_V3 = "nsgablack.checkpoint.v3"
    SCHEMA_V4 = "nsgablack.checkpoint.v4"
    SCHEMA_V5 = "nsgablack.checkpoint.v5"
    SCHEMA_V6 = "nsgablack.checkpoint.v6"
    SCHEMA_V7 = "nsgablack.checkpoint.v7"
    SCHEMA_V8 = "nsgablack.checkpoint.v8"
    SCHEMA_V9 = "nsgablack.checkpoint.v9"
    SCHEMA = SCHEMA_V9
    ENVELOPE_VERSION = "nsgablack.checkpoint.envelope.v1"
    RESUME_ISSUE_SAMPLE_LIMIT = 32

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
        self._frozen_final_checkpoint: tuple[Path, Dict[str, Any], bytes] | None = None
        self._staged_final_checkpoint_ref: Any = None
        self._last_resume_audit: Dict[str, Any] = {
            "status": "not_attempted",
            "current": False,
            "trajectory_equivalent": False,
            "restored_components": [],
            "skipped_component_count": 0,
            "issue_count": 0,
            "issues": [],
            "audit_truncated": False,
        }
        self.is_algorithmic = False
        # Allow solver.add_plugin() to fail-fast when strict resume is requested.
        self.raise_on_init_error = bool(self.cfg.strict)

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------
    def prepare_restore(self, solver):
        if not bool(self.cfg.auto_resume):
            return None
        try:
            self.resume(self.cfg.resume_from)
        except Exception:
            if bool(self.cfg.strict):
                raise
        return None

    def on_generation_committed(self, generation: int, outcome):
        del generation, outcome
        save_every = int(self.cfg.save_every)
        if save_every <= 0:
            return None
        solver = self.solver
        if solver is None:
            return None
        completed_steps = self._completed_logical_steps(solver)
        if completed_steps <= 0 or completed_steps % save_every != 0:
            return None
        self.save_checkpoint(reason="generation_end")
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        del result
        if not bool(self.cfg.save_on_finish):
            return None
        solver = self.solver
        if solver is None:
            return None
        self._assert_strict_security_ready()
        target = self._next_checkpoint_path(solver)
        payload = self._build_payload(solver=solver, reason="solver_finish")
        envelope = self._wrap_payload(payload)
        encoded = pickle.dumps(envelope, protocol=pickle.HIGHEST_PROTOCOL)
        # Freeze while Provider/Adapter state is still alive.  Publication is
        # delayed until teardown and every strict prepare participant succeed.
        self._frozen_final_checkpoint = (target, payload, encoded)
        return None

    def on_solver_finalization_prepare(self, result: Dict[str, Any]):
        frozen = self._frozen_final_checkpoint
        if frozen is None:
            return None
        solver = self.solver
        runtime = getattr(solver, "case_runtime", None)
        begin = getattr(runtime, "begin_finalization_transaction", None)
        if not callable(begin):
            return None
        target, payload, encoded = frozen
        transaction = begin("case_finalization")
        self._staged_final_checkpoint_ref = transaction.publish(
            "checkpoint_final",
            encoded,
            serializer="bytes",
            kind="checkpoint",
            media_type="application/x-python-pickle",
            metadata={
                "framework": "nsgablack",
                "checkpoint_schema": str(payload.get("schema", self.SCHEMA)),
                "checkpoint_filename": target.name,
                "checkpoint_generation": int(
                    getattr(solver, "generation", 0) or 0
                ),
                "state_frozen_before_teardown": True,
            },
        )
        if isinstance(result, dict):
            result["checkpoint_latest"] = str(self._staged_final_checkpoint_ref.uri)
            result["checkpoint_latest_ref"] = (
                self._staged_final_checkpoint_ref.as_dict()
            )
        return None

    def on_solver_finalized(self, result: Dict[str, Any]):
        frozen = self._frozen_final_checkpoint
        if frozen is None:
            return None
        target, payload, _ = frozen
        solver = self.solver
        runtime = getattr(solver, "case_runtime", None)
        try:
            if runtime is not None:
                publications = dict(
                    getattr(runtime, "artifact_publications", {}) or {}
                )
                receipt = publications.get("checkpoint_final")
                if receipt is None:
                    raise RuntimeError(
                        "final checkpoint did not receive an authoritative "
                        "PublicationReceipt"
                    )
                if receipt.metadata.get("case_finalization_sealed") is not True:
                    raise RuntimeError(
                        "final checkpoint receipt is not Case-finalization sealed"
                    )
                ref = receipt.ref
                self.latest_checkpoint_path = str(ref.uri)
                if isinstance(result, dict):
                    result["checkpoint_latest"] = str(ref.uri)
                    result["checkpoint_latest_ref"] = ref.as_dict()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                self._atomic_write_pickle(target, payload)
                self.latest_checkpoint_path = str(target)
                self._apply_retention(target.parent)
                if isinstance(result, dict):
                    result["checkpoint_latest"] = str(target)
            self.last_saved_generation = int(
                getattr(solver, "generation", 0) or 0
            )
        finally:
            self._frozen_final_checkpoint = None
            self._staged_final_checkpoint_ref = None
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def save_checkpoint(self, *, reason: str = "manual") -> Optional[Path]:
        solver = self.solver
        if solver is None:
            return None
        self._assert_strict_security_ready()

        target = self._next_checkpoint_path(solver)
        ckpt_dir = target.parent
        ckpt_dir.mkdir(parents=True, exist_ok=True)

        generation = int(getattr(solver, "generation", 0))

        payload = self._build_payload(solver=solver, reason=reason)
        self._atomic_write_pickle(target, payload)
        self.latest_checkpoint_path = str(target)
        self.last_saved_generation = generation

        self._apply_retention(ckpt_dir)
        return target

    def _next_checkpoint_path(self, solver: Any) -> Path:
        ckpt_dir = Path(self.cfg.checkpoint_dir).resolve()
        generation = int(getattr(solver, "generation", 0))
        stamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{self.cfg.file_prefix}_g{generation:06d}_{stamp}.pkl"
        return ckpt_dir / filename

    def resume(self, checkpoint: str = "latest") -> bool:
        self._begin_resume_audit(checkpoint)
        solver = self.solver
        if solver is None:
            self._finish_resume_audit(status="unavailable", current=False)
            return False
        try:
            self._assert_strict_security_ready()
            path = self._get_checkpoint_path(checkpoint)
            if path is None:
                error = FileNotFoundError(f"checkpoint not found: {checkpoint}")
                self._record_resume_issue("checkpoint", "not_found", error)
                self._finish_resume_audit(status="unavailable", current=False)
                if bool(self.cfg.strict):
                    raise error
                return False

            self._last_resume_audit["checkpoint_path"] = str(path)
            if not self._is_path_trusted(path):
                error = PermissionError(f"checkpoint path is not trusted: {path}")
                self._record_resume_issue("checkpoint", "untrusted_path", error)
                self._finish_resume_audit(status="error", current=False)
                if bool(self.cfg.strict):
                    raise error
                return False

            with path.open("rb") as f:
                # SECURITY NOTE: pickle.load can execute arbitrary code.
                # Only load checkpoints from trusted sources (your own runs).
                loaded = pickle.load(f)  # nosec B301
            payload = self._unwrap_and_verify_payload(loaded)
            payload = self._migrate_payload(payload)
            state_for_validation = payload.get("solver_state")
            if not isinstance(state_for_validation, dict):
                raise ValueError("invalid checkpoint payload: missing solver_state")
            self._validate_incumbent_selection(solver, state_for_validation)
            queue_restore = getattr(solver, "queue_restore_envelope", None)
            setup_complete = bool(
                getattr(solver, "_runtime_setup_complete", False)
            )
            restore_collection_active = bool(
                getattr(solver, "_restore_collection_active", False)
            )
            if callable(queue_restore) and (
                not setup_complete or restore_collection_active
            ):
                def _apply_queued_restore() -> None:
                    try:
                        self._restore_payload(solver=solver, payload=payload)
                        self.last_loaded_generation = int(
                            getattr(solver, "generation", 0)
                        )
                        status = (
                            "degraded"
                            if int(
                                self._last_resume_audit.get("issue_count", 0) or 0
                            ) > 0
                            else "restored"
                        )
                        self._finish_resume_audit(status=status, current=True)
                    except Exception as exc:
                        self._record_resume_issue(
                            "checkpoint",
                            "queued_restore_error",
                            exc,
                        )
                        self._finish_resume_audit(status="error", current=False)
                        raise

                queue_restore(
                    _apply_queued_restore,
                    source=f"checkpoint:{path}",
                )
                self.last_loaded_path = str(path)
                self.latest_checkpoint_path = str(path)
                state = payload.get("solver_state", {})
                resume_cursor = self._resume_cursor_from_payload(payload)
                setattr(
                    solver,
                    "_resume_cursor",
                    int(resume_cursor),
                )
                self.last_loaded_generation = int(
                    state.get("generation", 0)
                    if isinstance(state, Mapping)
                    else 0
                )
                self._finish_resume_audit(status="queued", current=False)
                return True
            if bool(getattr(solver, "running", False)) and not bool(
                getattr(solver, "_restore_apply_active", False)
            ):
                raise RuntimeError(
                    "checkpoint restore cannot mutate a running Solver outside "
                    "the post-setup restore transaction"
                )
            self._restore_payload(solver=solver, payload=payload)
            self.last_loaded_path = str(path)
            self.last_loaded_generation = int(getattr(solver, "generation", 0))
            self.latest_checkpoint_path = str(path)
            status = (
                "degraded"
                if int(self._last_resume_audit.get("issue_count", 0) or 0) > 0
                else "restored"
            )
            self._finish_resume_audit(status=status, current=True)
            return True
        except Exception as exc:
            if str(self._last_resume_audit.get("status", "")) not in {
                "error",
                "unavailable",
            }:
                self._record_resume_issue("checkpoint", "resume_error", exc)
                self._finish_resume_audit(status="error", current=False)
            raise

    def _begin_resume_audit(self, checkpoint: str) -> None:
        self._last_resume_audit = {
            "status": "restoring",
            "current": False,
            "trajectory_equivalent": False,
            "requested_checkpoint": str(checkpoint or "latest"),
            "restored_components": [],
            "skipped_component_count": 0,
            "issue_count": 0,
            "issues": [],
            "audit_truncated": False,
        }

    def _record_resume_issue(
        self,
        component: str,
        reason: str,
        error: BaseException | None = None,
    ) -> None:
        audit = self._last_resume_audit
        if not isinstance(audit, dict) or audit.get("status") == "not_attempted":
            self._begin_resume_audit("direct")
            audit = self._last_resume_audit
        audit["issue_count"] = int(audit.get("issue_count", 0) or 0) + 1
        audit["skipped_component_count"] = int(
            audit.get("skipped_component_count", 0) or 0
        ) + int(str(component) != "checkpoint")
        issues = list(audit.get("issues", []) or [])
        if len(issues) < self.RESUME_ISSUE_SAMPLE_LIMIT:
            issue: Dict[str, Any] = {
                "component": str(component)[:160],
                "reason": str(reason)[:160],
            }
            if error is not None:
                issue["error_type"] = type(error).__name__[:160]
                issue["message"] = str(error)[:512]
            issues.append(issue)
            audit["issues"] = issues
        else:
            audit["audit_truncated"] = True

    def _finish_resume_audit(self, *, status: str, current: bool) -> None:
        issue_count = int(self._last_resume_audit.get("issue_count", 0) or 0)
        self._last_resume_audit["status"] = str(status)
        self._last_resume_audit["current"] = bool(current)
        self._last_resume_audit["trajectory_equivalent"] = bool(
            current and issue_count == 0
        )

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

    def _collect_adapter_population_partitions(
        self,
        solver: Any,
    ) -> list[Dict[str, Any]]:
        adapter = getattr(solver, "adapter", None)
        getter = getattr(adapter, "get_population_partitions", None)
        if not callable(getter):
            return []
        partitions = tuple(getter() or ())
        ids = [str(partition.partition_id) for partition in partitions]
        if len(ids) != len(set(ids)):
            raise ValueError("Adapter exported duplicate population partition IDs")
        return [self._safe_copy(partition.as_dict()) for partition in partitions]

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

    def _collect_component_states(self, solver: Any) -> Dict[str, Any]:
        getter = getattr(solver, "checkpoint_components", None)
        if not callable(getter):
            return {}
        components = getter()
        if not isinstance(components, Mapping):
            raise TypeError("solver.checkpoint_components() must return a Mapping")
        out: Dict[str, Any] = {}
        for name, component in components.items():
            state_getter = getattr(component, "get_state", None)
            state_setter = getattr(component, "set_state", None)
            if not callable(state_getter) or not callable(state_setter):
                continue
            try:
                state = self._safe_copy(state_getter())
            except Exception:
                if bool(self.cfg.strict):
                    raise
                continue
            identity_getter = getattr(component, "checkpoint_identity", None)
            identity = None
            if callable(identity_getter):
                identity = identity_getter()
                if not isinstance(identity, Mapping):
                    raise TypeError(
                        f"checkpoint_identity() must return a Mapping: {name}"
                    )
            out[str(name)] = {
                "module": str(type(component).__module__),
                "class": str(type(component).__qualname__),
                "identity": self._safe_copy(identity),
                "state": state,
            }
        return out

    @staticmethod
    def _run_progress_state(solver: Any) -> RunProgressState:
        exporter = getattr(solver, "export_run_progress_state", None)
        if not callable(exporter):
            raise TypeError(
                "checkpoint target must expose export_run_progress_state()"
            )
        payload = exporter()
        if not isinstance(payload, Mapping):
            raise TypeError(
                "solver.export_run_progress_state() must return a Mapping"
            )
        return RunProgressState.from_dict(payload)

    @classmethod
    def _completed_logical_steps(cls, solver: Any) -> int:
        return int(cls._run_progress_state(solver).steps_completed)

    @staticmethod
    def _resume_cursor_from_payload(payload: Mapping[str, Any]) -> int:
        state = payload.get("solver_state")
        if isinstance(state, Mapping):
            progress = state.get("run_progress")
            if isinstance(progress, Mapping):
                return int(RunProgressState.from_dict(progress).steps_completed)
        cursor = payload.get("resume_cursor")
        if isinstance(cursor, int):
            return max(0, int(cursor))
        generation = state.get("generation", 0) if isinstance(state, Mapping) else 0
        return max(0, int(generation or 0))

    def _build_payload(self, *, solver: Any, reason: str) -> Dict[str, Any]:
        generation = int(getattr(solver, "generation", 0))
        run_progress = self._run_progress_state(solver)
        authority_mode = str(
            getattr(solver, "population_authority_mode", "single") or "single"
        ).strip().lower()
        if authority_mode not in {"single", "partitioned", "step_batch"}:
            raise ValueError(
                f"unsupported checkpoint population authority mode: {authority_mode}"
            )
        event_reader = getattr(
            solver,
            "get_last_evaluated_batch_snapshot",
            None,
        )
        if authority_mode == "partitioned" and not callable(event_reader):
            raise TypeError(
                "partitioned checkpoint target must expose "
                "get_last_evaluated_batch_snapshot()"
            )
        if callable(event_reader):
            event_pop, event_obj, event_vio = event_reader()
        else:
            event_pop = event_obj = event_vio = None
        has_event = any(
            value is not None for value in (event_pop, event_obj, event_vio)
        )
        last_evaluated_batch = (
            {
                "population": self._safe_copy(event_pop),
                "objectives": self._safe_copy(event_obj),
                "constraint_violations": self._safe_copy(event_vio),
            }
            if authority_mode == "partitioned" or has_event
            else None
        )
        event_exporter = getattr(
            solver,
            "export_evaluation_event_checkpoint_state",
            None,
        )
        evaluation_event = (
            event_exporter() if callable(event_exporter) else None
        )
        disposition_exporter = getattr(
            solver,
            "export_evaluation_disposition_checkpoint_state",
            None,
        )
        evaluation_disposition = (
            disposition_exporter()
            if callable(disposition_exporter)
            else None
        )
        if authority_mode == "partitioned":
            snap_pop = snap_obj = snap_vio = None
        else:
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
            "population_authority_mode": authority_mode,
            "population": self._safe_copy(snap_pop),
            "objectives": self._safe_copy(snap_obj),
            "constraint_violations": self._safe_copy(snap_vio),
            "last_evaluated_batch": self._safe_copy(last_evaluated_batch),
            "evaluation_event": self._safe_copy(evaluation_event),
            "evaluation_disposition": self._safe_copy(
                evaluation_disposition
            ),
            "pareto_solutions": self._safe_copy(getattr(solver, "pareto_solutions", None)),
            "pareto_objectives": self._safe_copy(getattr(solver, "pareto_objectives", None)),
            "pareto_population_snapshot": (
                None
                if getattr(solver, "pareto_population_snapshot", None) is None
                else self._safe_copy(
                    solver.pareto_population_snapshot.as_dict()
                )
            ),
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
            "run_progress": self._safe_copy(
                run_progress.as_dict()
            ),
        }
        export_candidate_population = getattr(
            solver,
            "export_candidate_population_checkpoint_state",
            None,
        )
        candidate_population = (
            export_candidate_population()
            if callable(export_candidate_population)
            else None
        )
        solver_state["candidate_population"] = self._safe_copy(
            candidate_population
        )
        export_candidate_partitions = getattr(
            solver,
            "export_candidate_population_partitions_checkpoint_state",
            None,
        )
        candidate_partitions = (
            export_candidate_partitions()
            if callable(export_candidate_partitions)
            else None
        )
        solver_state["candidate_population_partitions"] = self._safe_copy(
            candidate_partitions
        )
        solver_state["candidate_population_audit"] = {
            "available": candidate_population is not None,
            "schema": "blackbase.candidate_batch/v1",
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
            "resume_cursor": int(run_progress.steps_completed),
            "adapter_state": self._collect_adapter_state(solver),
            "adapter_population_partitions": (
                self._collect_adapter_population_partitions(solver)
            ),
            "stateful_components": self._collect_component_states(solver),
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
        authority_mode = str(
            state.get("population_authority_mode", "single") or "single"
        ).strip().lower()
        if authority_mode not in {"single", "partitioned", "step_batch"}:
            raise ValueError(
                f"unsupported checkpoint population authority mode: {authority_mode}"
            )
        last_evaluated = state.get("last_evaluated_batch")
        if authority_mode == "partitioned":
            if not isinstance(last_evaluated, Mapping):
                raise ValueError(
                    "partitioned checkpoint is missing last_evaluated_batch"
                )
            population = last_evaluated.get("population")
            objectives = last_evaluated.get("objectives")
            violations = last_evaluated.get("constraint_violations")
        else:
            population = state.get("population")
            objectives = state.get("objectives")
            violations = state.get("constraint_violations")

        full_event = state.get("evaluation_event")
        restore_full_event = getattr(
            solver,
            "restore_evaluation_event_checkpoint_state",
            None,
        )
        restore_event = getattr(solver, "restore_evaluation_event_arrays", None)
        if isinstance(full_event, Mapping) and callable(restore_full_event):
            restore_full_event(full_event)
        elif callable(restore_event):
            if isinstance(last_evaluated, Mapping):
                restore_event(
                    last_evaluated.get("population"),
                    last_evaluated.get("objectives"),
                    last_evaluated.get("constraint_violations"),
                )
            else:
                restore_event(None, None, None)
        restore_disposition = getattr(
            solver,
            "restore_evaluation_disposition_checkpoint_state",
            None,
        )
        if callable(restore_disposition):
            full_disposition = state.get("evaluation_disposition")
            restore_disposition(
                full_disposition
                if isinstance(full_disposition, Mapping)
                else None
            )

        has_numeric_state = all(
            value is not None for value in (population, objectives, violations)
        )
        if has_numeric_state:
            # Establish the numeric side first without publishing a Snapshot.
            # CandidateBatch restore validates against these exact values; one
            # final writer call below then publishes both views together.
            _set_field("population", population)
            _set_field("objectives", objectives)
            _set_field("constraint_violations", violations)
            restore_candidate_population = getattr(
                solver,
                "restore_candidate_population_checkpoint_state",
                None,
            )
            if callable(restore_candidate_population):
                try:
                    restore_candidate_population(state.get("candidate_population"))
                except Exception as exc:
                    self._record_resume_issue(
                        "solver.candidate_population",
                        "restore_failed",
                        exc,
                    )
                    try:
                        restore_candidate_population(None)
                    except Exception:
                        pass
                    if bool(self.cfg.strict):
                        raise
            restore_candidate_partitions = getattr(
                solver,
                "restore_candidate_population_partitions_checkpoint_state",
                None,
            )
            if callable(restore_candidate_partitions):
                restore_candidate_partitions(
                    state.get("candidate_population_partitions")
                )
            _set_field("population_authority_mode", authority_mode)
            writer = getattr(solver, "write_population_snapshot", None)
            if callable(writer):
                try:
                    writer(
                        population,
                        objectives,
                        violations,
                    )
                except Exception as exc:
                    self._record_resume_issue(
                        "solver.population_snapshot",
                        "publish_failed",
                        exc,
                    )
                    if bool(self.cfg.strict):
                        raise
            if authority_mode == "partitioned":
                _set_field("population", None)
                _set_field("objectives", None)
                _set_field("constraint_violations", None)
                _set_field("_candidate_population_batch", None)
                _set_field("_candidate_population_provenance", ())
                _set_field("_active_candidate_provenance", [])
        else:
            restore_candidate_population = getattr(
                solver,
                "restore_candidate_population_checkpoint_state",
                None,
            )
            if callable(restore_candidate_population):
                restore_candidate_population(state.get("candidate_population"))
            restore_candidate_partitions = getattr(
                solver,
                "restore_candidate_population_partitions_checkpoint_state",
                None,
            )
            if callable(restore_candidate_partitions):
                restore_candidate_partitions(
                    state.get("candidate_population_partitions")
                )
            _set_field("population_authority_mode", authority_mode)
            if authority_mode == "partitioned":
                partition_writer = getattr(
                    solver,
                    "write_partitioned_population_snapshot",
                    None,
                )
                if not callable(partition_writer):
                    raise TypeError(
                        "partitioned checkpoint target cannot publish partition authority"
                    )
                try:
                    partition_writer()
                except Exception as exc:
                    self._record_resume_issue(
                        "solver.population_partitions_snapshot",
                        "publish_failed",
                        exc,
                    )
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
        pareto_population_payload = state.get("pareto_population_snapshot")
        if isinstance(pareto_population_payload, Mapping):
            _set_field(
                "pareto_population_snapshot",
                PopulationSnapshot.from_dict(pareto_population_payload),
            )
        elif callable(getattr(solver, "update_pareto_solutions", None)):
            # Older checkpoints did not persist token-aligned Pareto identity.
            # Reconstruct from the already-restored authoritative CandidateBatch,
            # never by matching equal numeric rows.
            solver.update_pareto_solutions()

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
        restore_run_progress = getattr(
            solver,
            "restore_run_progress_state",
            None,
        )
        if callable(restore_run_progress):
            restore_run_progress(state.get("run_progress"))

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

    def _apply_adapter_population_partitions(
        self,
        solver: Any,
        raw_partitions: Any,
    ) -> None:
        if not raw_partitions:
            return
        adapter = getattr(solver, "adapter", None)
        setter = getattr(adapter, "set_population_partitions", None)
        if not callable(setter):
            error = TypeError(
                "checkpoint target Adapter cannot restore population partitions"
            )
            self._record_resume_issue(
                "adapter.population_partitions",
                "set_state_unavailable",
                error,
            )
            if bool(self.cfg.strict):
                raise error
            return
        from ...adapters.algorithm_adapter import PopulationPartition

        try:
            partitions = tuple(
                item
                if isinstance(item, PopulationPartition)
                else PopulationPartition.from_dict(item)
                for item in tuple(raw_partitions or ())
            )
            ids = [partition.partition_id for partition in partitions]
            if len(ids) != len(set(ids)):
                raise ValueError(
                    "checkpoint contains duplicate population partition IDs"
                )
            if setter(partitions) is False:
                raise ValueError(
                    "Adapter rejected checkpoint population partitions"
                )
        except Exception as exc:
            self._record_resume_issue(
                "adapter.population_partitions",
                "set_state_failed",
                exc,
            )
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

    def _apply_component_states(
        self,
        solver: Any,
        component_states: Any,
    ) -> set[str]:
        if not isinstance(component_states, Mapping):
            if component_states:
                error = ValueError("checkpoint stateful_components payload is invalid")
                self._record_resume_issue("stateful_components", "invalid_payload", error)
                if bool(self.cfg.strict):
                    raise error
            return set()
        getter = getattr(solver, "checkpoint_components", None)
        if not callable(getter):
            if component_states:
                error = ValueError(
                    "checkpoint contains stateful components but solver exposes none"
                )
                self._record_resume_issue(
                    "stateful_components",
                    "component_registry_unavailable",
                    error,
                )
                if bool(self.cfg.strict):
                    raise error
            return set()
        current = getter()
        if not isinstance(current, Mapping):
            error = TypeError("solver.checkpoint_components() must return a Mapping")
            self._record_resume_issue(
                "stateful_components",
                "invalid_component_registry",
                error,
            )
            raise error
        restored: set[str] = set()
        for raw_name, raw_payload in component_states.items():
            name = str(raw_name)
            component = current.get(name)
            if component is None:
                error = ValueError(f"checkpoint component is unavailable: {name}")
                self._record_resume_issue(name, "unavailable", error)
                if bool(self.cfg.strict):
                    raise error
                continue
            if not isinstance(raw_payload, Mapping):
                error = ValueError(f"checkpoint component payload is invalid: {name}")
                self._record_resume_issue(name, "invalid_payload", error)
                if bool(self.cfg.strict):
                    raise error
                continue
            expected_module = str(raw_payload.get("module", "") or "")
            expected_class = str(raw_payload.get("class", "") or "")
            actual_module = str(type(component).__module__)
            actual_class = str(type(component).__qualname__)
            if (expected_module and expected_module != actual_module) or (
                expected_class and expected_class != actual_class
            ):
                error = ValueError(
                    f"checkpoint component identity mismatch for {name}: "
                    f"saved={expected_module}.{expected_class}, "
                    f"current={actual_module}.{actual_class}"
                )
                self._record_resume_issue(name, "type_mismatch", error)
                if bool(self.cfg.strict):
                    raise error
                continue
            saved_identity = raw_payload.get("identity")
            identity_getter = getattr(component, "checkpoint_identity", None)
            if saved_identity is not None:
                if not callable(identity_getter):
                    error = ValueError(
                        f"checkpoint component identity contract is unavailable: {name}"
                    )
                    self._record_resume_issue(name, "identity_unavailable", error)
                    if bool(self.cfg.strict):
                        raise error
                    continue
                actual_identity = identity_getter()
                if not isinstance(actual_identity, Mapping):
                    raise TypeError(
                        f"checkpoint_identity() must return a Mapping: {name}"
                    )
                if self._safe_copy(dict(saved_identity)) != self._safe_copy(
                    dict(actual_identity)
                ):
                    error = ValueError(
                        f"checkpoint component configuration mismatch: {name}"
                    )
                    self._record_resume_issue(name, "configuration_mismatch", error)
                    if bool(self.cfg.strict):
                        raise error
                    continue
            setter = getattr(component, "set_state", None)
            if not callable(setter):
                error = ValueError(f"checkpoint component cannot restore state: {name}")
                self._record_resume_issue(name, "set_state_unavailable", error)
                if bool(self.cfg.strict):
                    raise error
                continue
            try:
                setter(raw_payload.get("state"))
                restored.add(name)
            except Exception as exc:
                self._record_resume_issue(name, "set_state_failed", exc)
                if bool(self.cfg.strict):
                    raise
        self._last_resume_audit["restored_components"] = sorted(restored)
        return restored

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
        if schema == cls.SCHEMA_V9:
            return payload
        if schema not in {
            cls.SCHEMA_V1,
            cls.SCHEMA_V2,
            cls.SCHEMA_V3,
            cls.SCHEMA_V4,
            cls.SCHEMA_V5,
            cls.SCHEMA_V6,
            cls.SCHEMA_V7,
            cls.SCHEMA_V8,
        }:
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
        if schema == cls.SCHEMA_V1:
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
        migrated.setdefault("stateful_components", {})
        migrated.setdefault("adapter_population_partitions", [])
        state.setdefault("candidate_population", None)
        state.setdefault("candidate_population_partitions", None)
        state.setdefault("pareto_population_snapshot", None)
        partition_payload = state.get("candidate_population_partitions")
        partitioned = bool(
            isinstance(partition_payload, Mapping)
            and tuple(partition_payload.get("partitions", ()) or ())
        )
        state.setdefault(
            "population_authority_mode",
            "partitioned" if partitioned else "single",
        )
        if str(state.get("population_authority_mode")) == "partitioned":
            state.setdefault(
                "last_evaluated_batch",
                {
                    "population": state.get("population"),
                    "objectives": state.get("objectives"),
                    "constraint_violations": state.get("constraint_violations"),
                },
            )
            state["population"] = None
            state["objectives"] = None
            state["constraint_violations"] = None
        else:
            state.setdefault("last_evaluated_batch", None)
        if "evaluation_event" not in state:
            legacy_event = state.get("last_evaluated_batch")
            if isinstance(legacy_event, Mapping) and all(
                legacy_event.get(key) is not None
                for key in ("population", "objectives", "constraint_violations")
            ):
                state["evaluation_event"] = {
                    "schema": "blackbase.evaluation_event/v1",
                    "event_id": (
                        f"migrated:{state.get('active_run_id') or 'unknown'}:"
                        f"{int(state.get('generation', 0) or 0)}"
                    ),
                    "candidate_codec": "blackbase.numeric_candidate_batch/v1",
                    "candidate_payload": {
                        "population": np.asarray(
                            legacy_event.get("population"), dtype=float
                        ).tolist(),
                    },
                    "feedback_codec": "nsgablack.numeric_optimization_feedback/v1",
                    "feedback_payload": {
                        "objectives": np.asarray(
                            legacy_event.get("objectives"), dtype=float
                        ).tolist(),
                        "constraint_violations": np.asarray(
                            legacy_event.get("constraint_violations"), dtype=float
                        ).tolist(),
                    },
                    "provenance": [],
                    "identity": {
                        "run_id": state.get("active_run_id"),
                        "logical_step": int(state.get("generation", 0) or 0),
                    },
                    "evaluation_count": int(
                        state.get("evaluation_count", 0) or 0
                    ),
                    "semantic_complete": False,
                    "metadata": {"migrated_from_schema": schema},
                }
            else:
                state["evaluation_event"] = None
        run_progress = state.get("run_progress")
        if isinstance(run_progress, Mapping):
            state["run_progress"] = RunProgressState.from_dict(
                run_progress
            ).as_dict()
        else:
            completed = int(state.get("generation", 0) or 0)
            state["run_progress"] = RunProgressState(
                steps_completed=completed,
                attempts_completed=completed,
                elapsed_seconds=0.0,
                deadline_remaining_seconds=None,
                run_id=state.get("active_run_id"),
            ).as_dict()
        state.setdefault(
            "candidate_population_audit",
            {
                "available": False,
                "schema": "blackbase.candidate_batch/v1",
                "reason": f"migrated_from_{schema}",
            },
        )
        migrated["schema"] = cls.SCHEMA_V9
        migrated["migrated_from_schema"] = schema
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
            raise ValueError("checkpoint is missing incumbent_selection audit state")

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

        resume_cursor = self._resume_cursor_from_payload(payload)
        self._apply_solver_state(solver, state, resume_cursor)
        restored_components = self._apply_component_states(
            solver,
            payload.get("stateful_components", {}),
        )
        if "adapter" not in restored_components:
            self._apply_adapter_state(solver, payload.get("adapter_state"))
        self._apply_adapter_population_partitions(
            solver,
            payload.get("adapter_population_partitions", ()),
        )
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
            "resume_audit": copy.deepcopy(self._last_resume_audit),
        }

