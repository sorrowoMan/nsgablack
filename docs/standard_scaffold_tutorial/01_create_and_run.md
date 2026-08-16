# 01. Create And Run

## 1) Create project

```powershell
python -m nsgablack project new my_project
cd my_project
```

## 2) Add cases by semantic role

```powershell
python -m nsgablack project add-case outer_search --type solver --framework nsgablack
python -m nsgablack project add-case inner_fitting --type trainer --framework mlblack
```

## 3) Add components

```powershell
# General component
python -m nsgablack project add-component --case outer_search --kind adapter --name nsga2_adapter

# Pipeline operator under mutate slot
python -m nsgablack project add-component --case outer_search --kind pipeline --slot mutate --name gaussian_mutate
```

`pipeline` remains one case-level entry. `--slot` only controls internal operator placement.

## 4) Validate and run

```powershell
python run_project.py --check --build-check
python -m nsgablack project doctor --path . --build --strict --format problem
python run_project.py
```
