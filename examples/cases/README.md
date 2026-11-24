# examples/cases

This directory stores runnable example Projects. Each direct child is a
Project wrapper, and each runnable Solver/Trainer lives inside that Project as
a standard Case scaffold.

## 完整装配示例

[综合装配工作台](assembly_workbench/README.md) 用一个四 Case Project 展示完整 Problem／Pipeline／Unit／Adapter／Bias／Plugin 装配、两轮 GA→VNS→GA、MOEA/D 投影与两种精修器、Case 内并行、Project 并行／DAG、权威 Artifact 与真正内层 Case 调用。含详细中文逐层讲解、真实源码读本和运行结果。

[VNS / MOEA-D 普通函数与母池输入试作](pool_workflow_pilot/README.md) 展示 Pipeline 生成母池种子、Adapter 按需建立 Unit，以及普通函数组合变化操作。

[四个完整 Project 阅读指南](ASSEMBLED_PROJECTS_GUIDE_CN.md) 串联 GA＋VNS、MOEA/D 双层方向精修、SA 池驱动恢复、DE／SA 多 Case 并发。每个例子提供真实脚手架、全部本地源码、框架源码索引及已经保存的运行结果。

## Current Rule

Formal examples use the shared Project / Case / Scaffold / L0 substrate:

```text
examples/cases/<project>/
  project_config.py
  run_project.py
  README.md
  cases/
    __init__.py
    <case>/
      __init__.py
      README.md
      build_solver.py
      run_solver.py
      config.py
      problem/
      pipeline/
      adapter/
      bias/
      plugins/
      evaluation/
      runtime/
      solver/
```

`run_project.py` is the formal entrypoint. It reads `project_config.py`, asks
Project-level L0 for a `ResourceContext`, and then runs the selected Case(s).

Case-level `build_solver.py` remains the canonical assembly entry for one
Solver/Trainer. Case-level `run_solver.py` is a debug/inspection entry only.
Project and Case guidance lives in their respective `README.md`; duplicated
onboarding and registration documents are not part of the scaffold.

## Multi-Case Projects

Nested optimization, multi-solver, multi-trainer, and cross-framework workflows
must be expressed as multiple standard Cases under one Project:

```text
examples/cases/<project>/
  project_config.py      # stages, groups, resource requests
  run_project.py         # only formal run entry
  cases/
    outer_search/
    inner_trainer/
```

Project L0 owns resource authorization and grants. Cases declare requirements
and consume the effective grant; they do not allocate global resources by
themselves.
