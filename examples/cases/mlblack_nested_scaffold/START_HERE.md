# START_HERE

Run a tiny smoke test first:

```powershell
python examples/cases/mlblack_nested_scaffold/build_solver.py --generations 1 --batch-size 4 --fold-col test_fold_1
```

Run a fuller search:

```powershell
python examples/cases/mlblack_nested_scaffold/build_solver.py --generations 6 --batch-size 10 --fold-col test_fold_1
```

Key flags:
- `--mlblack-root`: path to mlblack repo root
- `--csv-path`: traffic table csv
- `--fold-col`: choose fold split (`test_fold_1` ... `test_fold_10`)
- `--run-dir`: case output root
