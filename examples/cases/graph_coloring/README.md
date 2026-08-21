# graph_coloring

这是一个遵循统一 **Project -> Case -> Standard Scaffold** 结构的 nsgablack 示例 Project。

## 运行

~~~powershell
python examples/cases/graph_coloring/run_project.py --check
python examples/cases/graph_coloring/run_project.py
~~~

默认 Project 配置是可执行的 smoke profile；更大的研究规模应通过 Case 配置或显式组件覆盖启用。

## 编排边界

- **run_project.py**：Project 级统一入口。
- **project_config.py**：阶段、Case 顺序、L0 资源请求和组件覆盖。
- **cases/**：可独立装配、检查并由 Project 调用的标准 Case。
- Project L0 负责资源授权；Case 只消费生效后的 **ResourceContext**。

## Cases

- `graph_coloring`

每个 Case 的算法语义、Problem、Pipeline、Adapter 和 Plugin 组合请查看对应 Case 目录。
