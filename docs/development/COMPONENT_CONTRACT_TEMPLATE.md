# Component Contract Card Template

Use this card when adding a project component (adapter, pipeline, bias, plugin).

## 1. Identity
- Component key:
- Kind:
- Source path:
- Owner:

## 2. Responsibility
- Must do:
- Must not do:

## 3. I/O Contract
- Input shape/types:
- Output shape/types:
- Side effects:

## 4. Context Contract
- `context_requires`:
- `context_provides`:
- `context_mutates`:
- `context_cache`:
- `context_notes`:

## 5. Recovery Contract
- Implements `get_state`/`set_state`: yes/no
- `state_recovery_level`: `L0`/`L1`/`L2`
- Recovery boundary notes:

## 6. Mode Boundary
- Prove mode boundary (if any):
- Heuristic mode boundary (if any):

## 7. Stop Condition
- Explicit stop/short-circuit behavior:
