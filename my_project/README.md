# my_project

**中文说明**
NSGABlack 本地项目骨架。

## 目录结构 / Structure
- `problem/`: 问题定义 / problem definition
- `pipeline/`: 表示与硬约束 / representation + hard constraints
- `bias/`: 软偏好 / soft preference
- `adapter/`: 策略编排（可选）/ strategy orchestration (optional)
- `plugins/`: 工程能力（可选）/ engineering capabilities (optional)
- `data/`: 输入数据 / input data
- `assets/`: 输出产物 / outputs

## 推荐流程 / Recommended Flow
1. 阅读 `START_HERE.md`.
2. 阅读 `COMPONENT_REGISTRATION.md`.
3. 运行 `python -m nsgablack project doctor --path . --build`.
4. 用 `build_solver.py` 作为唯一装配入口。

## 组件模板 / Copy Templates
- `problem/template_problem.py`
- `pipeline/template_pipeline.py`
- `bias/template_bias.py`
- `adapter/template_adapter.py`
- `plugins/template_plugin.py`

建议做法：先复制模板并重命名，再改逻辑和契约字段。

## 入口文件 / Entry Files
- `build_solver.py`: 装配 problem/pipeline/bias/strategy
- `project_registry.py`: 项目本地 Catalog 注册
- `COMPONENT_REGISTRATION.md`: 注册组件的 why/what/how
