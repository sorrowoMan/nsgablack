# COMPONENT_REGISTRATION

This case provides `project_registry.py` with local Catalog entries.

Rules:
- register solver entry (`build_solver:build_solver`)
- register outer problem component
- register inner evaluation model component

Run:

```powershell
python -m nsgablack project doctor --path . --strict
```
