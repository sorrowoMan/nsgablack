"""Project declared proposal rows through one final admission disposition.

These are pending trial coordinates, not population-member operations. The
existing step transaction owns rollback; no additional state is retained here.
"""
from collections.abc import Mapping
import numpy as np


def _rows(value, count, indices, *, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, (list, tuple, np.ndarray)):
        raise TypeError("pending proposal fields must be row sequences")
    if isinstance(value, np.ndarray) and value.ndim == 0:
        raise ValueError("pending proposal fields require a row axis")
    if len(value) != count:
        raise ValueError("pending proposal fields do not align with proposed_count")
    if isinstance(value, np.ndarray):
        return np.array(value[list(indices)], copy=True)
    selected = [value[i] for i in indices]
    return tuple(selected) if isinstance(value, tuple) else selected


def project_pending_proposals(adapter, disposition):
    """Validate every declared field before installing any projected rows."""
    unit = adapter.algorithm_unit
    fields = tuple(adapter.admission_unit_fields)
    if unit is None:
        if disposition.proposed_count:
            raise ValueError("pending proposals require their owning Unit")
        return
    optional = tuple(getattr(adapter, "optional_admission_unit_fields", ()))
    count, indices = disposition.proposed_count, disposition.accepted_indices
    updates = {name: _rows(getattr(unit, name), count, indices, optional=name in optional)
               for name in fields}
    columns = {}
    for name in getattr(adapter, "proposal_column_fields", ()):
        value = getattr(adapter, name)
        if value is None:
            columns[name] = None
        elif not isinstance(value, Mapping):
            raise TypeError("pending proposal columns must be a Mapping")
        else:
            projected = {key: _rows(rows, count, indices) for key, rows in value.items()}
            columns[name] = projected if indices else None
    for name, value in updates.items():
        setattr(unit, name, value)
    for name, value in columns.items():
        setattr(adapter, name, value)
