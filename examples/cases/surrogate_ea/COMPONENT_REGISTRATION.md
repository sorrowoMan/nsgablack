# COMPONENT_REGISTRATION

This file defines the local project registration contract.

## Why register components
- Enable Catalog and Run Inspector discovery
- Keep `build_solver.py` and `project_registry.py` aligned
- Make context I/O traceable

## What should be registered
- problems, pipelines, biases, adapters, plugins
- solver assembly entries

## Where to register
- `project_registry.py` for dynamic entries
- `catalog/entries.toml` for static entries

## Minimal entry fields
- `key`, `kind`, `title`, `import_path`
- `tags`, `summary`
- `context_requires`, `context_provides`, `context_mutates`, `context_cache`, `context_notes`
- `use_when`, `minimal_wiring`, `required_companions`, `config_keys`, `example_entry`

## Validation
```powershell
python -m nsgablack project doctor --path . --build --strict
python -m nsgablack project catalog list --path .
```
