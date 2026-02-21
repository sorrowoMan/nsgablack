# Migration Lab / 迁移实验室

This folder contains step-by-step migration workshops from traditional optimization scripts to NSGABlack architecture.
本目录提供“传统优化脚本 -> NSGABlack 架构”的逐步迁移工坊。

## Available Workshops / 当前工坊

- `ga_single_objective/`
  - `00_baseline.py`: pure Python/Numpy GA baseline（传统写法）
  - `01_refactor.ipynb`: step-by-step migration notebook（逐步改造）
  - `02_framework_final.py`: final framework-native implementation（框架最终版）
  - `03_diff.md`: mapping from baseline logic to framework layers（映射说明）

## Run / 运行方式

From the repository parent directory（在仓库上一级目录执行）:

```powershell
python nsgablack/examples/migration_lab/ga_single_objective/00_baseline.py
python nsgablack/examples/migration_lab/ga_single_objective/02_framework_final.py
python nsgablack/examples/migration_lab/nsga2_multi_objective/00_baseline.py
python nsgablack/examples/migration_lab/nsga2_multi_objective/02_framework_final.py
```

If your current directory is `nsgablack/`（如果你已进入 `nsgablack/`）:

```powershell
python examples/migration_lab/ga_single_objective/00_baseline.py
python examples/migration_lab/ga_single_objective/02_framework_final.py
python examples/migration_lab/nsga2_multi_objective/00_baseline.py
python examples/migration_lab/nsga2_multi_objective/02_framework_final.py
```
