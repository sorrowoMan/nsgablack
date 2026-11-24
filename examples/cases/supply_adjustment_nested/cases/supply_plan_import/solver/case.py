"""只读旧文件权威，向本 Case 的正常 finalization 发布新的候选输入。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from blackbase.resources import (
    ArtifactAuthority, ArtifactBinding, ArtifactPublicationError,
    FilesystemArtifactPublicationLedger, FilesystemArtifactStore, coerce_resource_context,
)
from ..problem.plan import prepare_candidate_plan


class SupplyPlanImportCase:
    def __init__(self, *, old_authority, old_binding, resource_context=None, production_case_dir=None):
        self.old_authority = (old_authority if isinstance(old_authority, ArtifactAuthority)
                              else ArtifactAuthority.from_dict(old_authority))
        self.old_binding = (old_binding if isinstance(old_binding, ArtifactBinding)
                            else ArtifactBinding.from_dict(old_binding))
        if self.old_authority.backend != "filesystem" or self.old_binding.ref.backend != "filesystem":
            raise ValueError("supply plan import explicitly supports a read-only filesystem source authority")
        self.production_case_dir = production_case_dir
        self.resource_context = coerce_resource_context(resource_context)
        self.case_runtime = None

    def set_resource_context(self, value):
        self.resource_context = coerce_resource_context(value)
        return self

    def get_resource_context(self):
        return self.resource_context

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        return self

    def run(self):
        if self.case_runtime is None or self.case_runtime.artifact_publisher is None:
            raise RuntimeError("supply plan import requires the formal Case artifact runtime")
        self.case_runtime.checkpoint()
        if not Path(self.old_authority.root).is_dir():
            raise ArtifactPublicationError("the explicit old filesystem authority is not mounted")
        receipt = self.old_binding.publication
        # Deliberately use the public filesystem readers. The process HTTP
        # profile belongs to the new authority and remains unchanged. No old
        # Publisher is constructed, so no recovery/scavenge or publication can
        # occur under the historical authority.
        ledger = FilesystemArtifactPublicationLedger(self.old_authority,
            project_run_id=receipt.project_run_id, case_run_id=receipt.case_run_id)
        if not ledger.verify(receipt):
            raise ArtifactPublicationError("old supply plan failed its original publication ledger verification")
        content = FilesystemArtifactStore(self.old_authority.root).read_verified(self.old_binding.ref, max_bytes=8 * 1024**2)
        plan = prepare_candidate_plan(json.loads(content), self.old_binding,
                                      production_case_dir=self.production_case_dir)
        self.case_runtime.checkpoint()
        return {"schema": "supply_adjustment_nested.candidate_plan/v1", **plan,
                "identity": self.case_runtime.identity.as_dict(),
                "derived_from": {"authority": self.old_authority.as_dict(),
                                 "binding": self.old_binding.as_dict(),
                                 "sha256": "sha256:" + hashlib.sha256(content).hexdigest()}}

    def export_case_result(self, output):
        ref = self.case_runtime.publish_artifact("candidate_plan", output, serializer="json", kind="supply-candidate-plan")
        return {"status": "succeeded", "artifact_refs": {"candidate_plan": ref.as_dict()},
                "imported_source": {"scenario_digest": output["scenario_digest"],
                                    "derived_from": output["derived_from"], "evaluations": 0}}
