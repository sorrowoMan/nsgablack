"""Declared optimization-control extension points, independent of ML internals."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from .state.step_outcome import StepOutcome


class SolverSemanticExtension:
    """Semantic hooks cannot replace step execution or its commit decision.

    Before-step failures abort the attempt. After-commit failures retain the
    committed outcome, are reported to the run loop, and stop the run only after
    committed progress and lifecycle notifications have been recorded.
    """
    name = "semantic_extension"

    def prepare_run(self, solver: Any) -> None:
        """Reset semantic projections before setup and queued restore."""

    def setup(self, solver: Any) -> None:
        """Initialize semantics before Adapter setup; errors abort the run."""

    def project_context(self, solver: Any, context: dict[str, Any]) -> Mapping[str, Any]:
        return context

    def checkpoint_components(self, solver: Any) -> Mapping[str, Any]:
        """Stable component names; replacing an existing owner is forbidden."""
        return {}

    def should_execute_step(self, solver: Any, step_index: int) -> bool:
        """May stop a step but cannot bypass the shared deadline or progress."""
        return True

    def cleanup_components(self, solver: Any) -> Mapping[str, Callable[[], Any]]:
        """Independent cleanup operations, attempted even if another fails.

        Operations must tolerate partial setup. Discovery must not acquire or
        release resources; names are local to this extension.
        """
        return {}

    def before_step(self, solver: Any) -> None:
        pass

    def after_step_committed(self, solver: Any, outcome: StepOutcome) -> None:
        pass


class CommittedStepError(RuntimeError):
    def __init__(self, outcome: StepOutcome, failures: list[tuple[str, BaseException]]):
        if not outcome.committed:
            raise ValueError("CommittedStepError requires a committed outcome")
        self.failures = tuple(failures)
        self.outcome = outcome.with_metadata(post_commit_errors=[
            {"participant": name, "error_type": type(exc).__name__, "message": str(exc)}
            for name, exc in failures
        ])
        super().__init__("committed step extension failed: " + "; ".join(
            f"{name}: {exc}" for name, exc in failures))
