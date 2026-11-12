"""Read-only, bounded evidence for the example's process-isolated Case pools."""
from nsgablack.context_keys import KEY_SOLUTION_WORKING_POOL


def describe_pool(solver, *, limit=128):
    pool = solver.solution_pool
    refs = pool.select()
    sample = refs[:limit]
    members = []
    if sample:
        batch = pool.read(sample)
        raw, violations = pool.read_raw_feedback(sample)
        provenance = pool.read_provenance(sample)
        dimension = int(batch.numeric_matrix.shape[1])
        for index, ref in enumerate(sample):
            members.append({"ref": ref.as_dict(), "stamp": pool.stamp_for(ref).as_dict(),
                "values": batch.numeric_matrix[index].tolist(),
                "raw_objectives": raw[index].tolist(),
                "raw_violation": float(violations[index]),
                "parent_token": (provenance[index] or {}).get("parent_token")})
    else:
        dimension = int(solver.dimension)
    workspace = getattr(solver.adapter, "working_pool", None)
    workspace_refs = () if workspace is None else pool.subpool_refs(workspace)
    return {"pool_id": pool.pool_id, "run_id": pool.run_id,
        "case_run_id": solver.case_runtime.identity.case_run_id,
        "clock": pool.timestamp.as_dict(), "dimension": dimension,
        "committed_steps": int(solver.generation),
        "evaluation_count": int(solver.evaluation_count),
        "accepted_count": len(refs), "evidence_complete": len(refs) <= limit,
        "working_pool": workspace,
        "working_members": [ref.as_dict() for ref in workspace_refs[:limit]],
        "has_working_pool_context": bool(solver.get_context().get(KEY_SOLUTION_WORKING_POOL)),
        "members": members}
