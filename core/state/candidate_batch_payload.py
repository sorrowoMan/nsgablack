"""Internal Snapshot encoding of the existing CandidateBatch protocol."""
from __future__ import annotations

import numpy as np
from blackbase.types import CandidateBatch, encode_shared_value


# Obtain the public protocol header without first expanding real numeric data
# into Python lists that would immediately be discarded again.
_BATCH_HEADER = {key: value for key, value in CandidateBatch.from_candidates(()).as_dict().items()
                 if key not in {"semantic_states", "numeric_matrix", "candidate_tokens"}}


def candidate_batch_snapshot_payload(batch: CandidateBatch) -> dict:
    """Keep both dense numeric views on the safe codec's typed ndarray path.

    Public as_dict() stays JSON-compatible.  Existing CandidateBatch and
    UnknownState readers already accept arrays in these numeric fields, so old
    list payloads and these payloads use the same protocol.  New Snapshots get
    their own typed content digest; a restored payload is never converted under
    an old identity.  SnapshotStore still detaches, validates, hashes and
    verifies every read and write.
    """
    return {
        **_BATCH_HEADER,
        "semantic_states": [dict(values=state.as_array(), metadata=encode_shared_value(
            state.metadata, path="unknown_state.metadata")) for state in batch.semantic_states],
        "numeric_matrix": np.array(batch.numeric_matrix, copy=True),
        "candidate_tokens": list(batch.candidate_tokens),
    }


__all__ = ["candidate_batch_snapshot_payload"]
