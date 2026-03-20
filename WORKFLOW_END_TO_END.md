# WORKFLOW END TO END

这一页描述一个完整的优化项目从“问题定义”到“运行验证”的端到端流程。

---

## 1) 定义问题（Problem）

- 目标、约束、决策变量  
- 明确输出目标维度与约束维度  

模板参考：`problem/template_problem.py`

---

## 2) 设计表示与算子（Pipeline）

- 初始化、变异、修复  
- 保证可行解稳定输出  

模板参考：`pipeline/template_pipeline.py`

---

## 3) 选择搜索策略（Adapter）

- 选择单一策略或组合策略  
- 只在 Adapter 中放搜索逻辑  

模板参考：`adapter/template_adapter.py`

---

## 4) 接入能力扩展（Plugin）

- 记录、审计、checkpoint、追踪  
- 需要时可短路评估  

模板参考：`plugins/template_plugin.py`

---

## 5) 评估路径（L4）

- 支持精确评估与代理评估  
- 通过 provider 统一注册  

配置参考：`evaluation/config.py`

---

## 6) 组装与运行

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

---

## 7) 验证与回放

- `project doctor` 校验结构  
- `run_inspector` 检查装配  
- `snapshot/context` 可回放  

---

## 8) 常见检查点

- 是否保持四层边界  
- 大对象是否走 snapshot  
- 评估短路是否对齐 shape  

