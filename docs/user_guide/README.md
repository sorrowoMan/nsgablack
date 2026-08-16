# docs/user_guide

用户指南只保留“当前架构下仍推荐使用”的操作路径。旧的单目录 scaffold、私有 workflow、旧 inner solver 入口、直接示例脚本入口都应迁到标准 Project / Case / Scaffold 口径后再作为推荐路径。

## Key Guides

- `PROJECT_SCAFFOLD.md`: create Project -> Case -> Standard Scaffold projects.
- `RUN_INSPECTOR.md`: UI inspection/search workflow.
- `CONTEXT_CONTRACTS.md`: requires/provides/mutates contracts.
- `PLUGIN_SELECTION.md`: plugin decision guide (when to use which plugin).
- `DB_EVENT_LOGGING.md`: MySQL event logging schema and rollout plan.

## Current Project Rules

- Start formal runs from `run_project.py`.
- Use `project_config.py` for stages, groups, dependencies, and Project L0 resource grants.
- Use `cases/<case>/build_solver.py` as the canonical case assembly entry.
- Keep `run_solver.py` as an independent debug entry only.
- Do not put full example scaffolds in repository-root `my_project/`.
