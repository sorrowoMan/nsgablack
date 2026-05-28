# START_HERE

## 1) Health Baseline
```powershell
python -m nsgablack project doctor --path . --build
```

## 2) Define the Core Layers
- `problem/`: objective + constraints
- `pipeline/`: init/mutate/repair
- `bias/`: soft preferences (optional)

## 3) Wire the Assembly
- `build_solver.py` is the only assembly entry
- parameters in registries; selection in build_solver

## 4) Run
```powershell
python run_solver.py --check
python run_solver.py
```

## 5) Optional
```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```
