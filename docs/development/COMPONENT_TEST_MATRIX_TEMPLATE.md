# Component Test Matrix Template

For each new component, add at least four tests:

1. `smoke`: can load and run the minimal path.
2. `contract`: validates propose/update or hook behavior against declared contracts.
3. `checkpoint_roundtrip`: validates `get_state -> set_state` consistency at declared recovery level.
4. `strict_fault`: validates strict mode and failure path behavior.

Recommended naming:
- `tests/test_<component>_smoke.py`
- `tests/test_<component>_contract.py`
- `tests/test_<component>_checkpoint.py`
- `tests/test_<component>_strict_fault.py`
