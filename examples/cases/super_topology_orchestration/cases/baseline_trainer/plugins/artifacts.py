"""Stage the baseline summary in the same transaction as the learned model."""

from mlblack.core.artifact_provider import CaseRuntimeArtifactProvider


class BaselineArtifacts(CaseRuntimeArtifactProvider):
    def begin_finalization(self, trainer, *, label="mlblack_result_finalization"):
        session = super().begin_finalization(trainer, label=label)
        try:
            session.publish_payload("summary", trainer.build_summary(), kind="ml-baseline")
        except BaseException:
            session.abort("summary_staging_failed")
            raise
        return session
