"""Publish model and nested training evidence through one finalization session."""

from mlblack.core.artifact_provider import CaseRuntimeArtifactProvider


class NestedTrainingArtifacts(CaseRuntimeArtifactProvider):
    def begin_finalization(self, trainer, *, label="mlblack_result_finalization"):
        session = super().begin_finalization(trainer, label=label)
        try:
            session.publish_payload(
                "training_summary", trainer.build_summary(), kind="nested-training-summary",
            )
        except BaseException:
            session.abort("summary_staging_failed")
            raise
        return session
