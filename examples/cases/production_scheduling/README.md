# examples/cases/production_scheduling

Production scheduling case demo (project-local architecture).

## Structure

- `problem/`: problem semantics and constraints
- `pipeline/`: initializer/mutator/repair assembly
- `bias/`: soft preference module
- `adapter/`: case-local strategy adapters
- `solver/`: strict feasible solver control + compatibility entry
- `plugins/`: runtime plugins and export utilities
- `cli/`: argument parser
- `build_solver.py`: scaffold standard entry + real assembly (plugin registration zone)
- `solver/assembly.py`: compatibility module for legacy imports
- `solver/run_case.py`: CLI entrypoint
- `working_integrated_optimizer.py`: compatibility wrapper only

## Run

```powershell
python build_solver.py
python solver/run_case.py --parallel --parallel-backend thread --parallel-workers 8
```

## Baselines

Single-objective baselines (maximize total output only):

```powershell
python solver/run_case.py --solver baseline-greedy --single-objective
python solver/run_case.py --solver baseline-aco --single-objective --aco-ants 48
```
