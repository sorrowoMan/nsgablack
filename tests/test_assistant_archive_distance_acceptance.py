"""Exercise the exact saved mutant; never provide these inputs to the model."""
import hashlib
import json
from pathlib import Path

import pytest

from nsgablack.catalog import assistant_archive_distance_acceptance as upgraded
from nsgablack.catalog import assistant_codex_acceptance as harness
from nsgablack.catalog.assistant_codex_math_repair import freeze_oracle
from nsgablack.catalog.assistant_novel_acceptance import TARGET, spec_identity

ROOT = Path(upgraded.__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/user_guide/evidence/codex-math-repair-20261124"


@pytest.mark.parametrize("relative,passes", [("archive/repaired.py", True), ("coverage-gap/seed.py", False)])
def test_original_recorded_source_under_additive_oracle(relative, passes):
    source = (EVIDENCE / relative).read_text(encoding="utf-8")
    digest = hashlib.sha256(source.encode()).hexdigest()
    result = upgraded.execute_candidate({"source": source, "path": TARGET, "code_sha256": digest,
        "check": {"status": "needs_runtime_validation", "code_sha256": digest}})
    assert result["executed"] is True and result["code_sha256"] == digest
    assert result["validation_identity"] == upgraded.spec_identity()
    if passes:
        assert result["status"] == "passed", result
        assert result["behavior"]["checks"] == 38
        assert result["behavior"]["baseline_checks"] == 30
        assert result["behavior"]["additional_checks"] == 8
        assert result["formal_case"]["committed_steps"] == 2
    else:
        assert result["status"] == "failed" and result["failed_stage"] == "behavior", result
        assert result["error_type"] == "AssertionError"
        assert "nearest-reference distance ranking differs" in result["error"]
        assert "formal_case" not in result


def test_new_profile_does_not_relabel_or_mutate_old_standard():
    old = json.loads((EVIDENCE / "summary.json").read_text(encoding="utf-8"))
    assert freeze_oracle() == old["oracle_before"] == old["oracle_after"]
    assert upgraded.spec_identity() != spec_identity()
    assert harness._binding(upgraded.IDEA, upgraded.PROFILE)["validation_identity"] == upgraded.spec_identity()
    assert harness._binding(upgraded.IDEA)["validation_identity"] == spec_identity()
    with pytest.raises(ValueError, match="requires_archive_task"):
        harness._binding("center_reflection_expansion", upgraded.PROFILE)
