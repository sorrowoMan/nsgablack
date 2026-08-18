# COMPONENT_REGISTRATION

This case declares local Catalog entries in `catalog/entries/<kind>.toml` shards.

Rules:
- register solver entry (`build_solver:build_solver`)
- register outer problem component
- register inner production solver component

Run:

```powershell
python -m nsgablack project doctor --path . --strict
```
