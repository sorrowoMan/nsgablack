# START_HERE

## 1. Add your first case

```powershell
python -m nsgablack project add-case my_first_solver --type solver
```

## 2. Edit the case

Open `cases/my_first_solver/build_solver.py` and implement `build_solver()`.

## 3. Validate

```powershell
cd cases/my_first_solver
python run_solver.py --check
```

## 4. Run (from project root!)

```powershell
cd ../..  # back to project root
python run_project.py
```

## 5. Health check

```powershell
python -m nsgablack project doctor --path . --build --strict
```
