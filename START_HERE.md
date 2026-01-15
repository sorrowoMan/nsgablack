# START_HERE — NSGABlack 入口地图

一句话记住：**问题接口 + 表征管线 + 偏置策略 + 求解器入口**。

---

## 1) 新问题最短路径（10 分钟跑通）

1. 定义问题接口  
   - `core/base.py`
2. 选择表征管线（变量类型）  
   - `utils/representation/base.py`
   - `docs/REPRESENTATION_INDEX.md`
3. 选择偏置（策略/规则/代理控制）  
   - `bias/bias.py`
   - `docs/user_guide/bias_baby_guide.md`
4. 选择求解器入口  
   - 单机 NSGA-II：`core/solver.py`
   - 代理辅助：`solvers/surrogate.py`、`solvers/surrogate_interface.py`
   - 多智能体：`solvers/multi_agent.py`
5. 冒烟验证（确认框架可用）  
   - `examples/validation_smoke_suite.py`

---

## 2) 我该选哪个入口？

- **标准多目标优化**：`core/solver.py`  
- **昂贵评估/代理加速**：`solvers/surrogate.py`、`surrogate/`、`docs/user_guide/surrogate_workflow.md`  
- **多智能体协作搜索**：`solvers/multi_agent.py`、`multi_agent/README.md`  
- **算法/业务偏置驱动**：`bias/`、`docs/user_guide/bias_system.md`  
- **想快速看 API 入口**：`docs/user_guide/external_api_navigation.md`  

---

## 3) 常用“找不到就看这里”

- 项目全局索引：`docs/PROJECT_CATALOG.md`  
- 工具索引：`docs/TOOLS_INDEX.md`  
- 偏置索引：`docs/BIAS_INDEX.md`  
- 表征索引：`docs/REPRESENTATION_INDEX.md`  
- 示例索引：`docs/EXAMPLES_INDEX.md`  
- 详尽说明书：`docs/PROJECT_DETAILED_OVERVIEW.md`  
- 标签化目录：`docs/TAGGED_INDEX.md`  

---

## 4) 常用示例（先跑这些）

- 表征管线全集：`examples/representation_comprehensive_demo.py`  
- TSP 表征与求解：`examples/tsp_representation_pipeline_demo.py`  
- 多智能体 + 偏置快速跑通：`examples/multi_agent_bias_quickstart.py`  
- 代理优化示例：`examples/bayesian_optimization_example.py`  
- 基准对比（ZDT/DTLZ + IGD/HV）：`examples/benchmark_zdt_dtlz_igd_hv.py`  
- 全模块冒烟验证：`examples/validation_smoke_suite.py`  

---

## 5) 常用工具（懒人优先）

- 生成目录索引：`tools/build_catalog.py`  
- 生成 API 文档：`tools/generate_api_docs.py`  

---

## 6) 记忆法（防忘）

**P-R-B-S**：  
Problem（问题接口）→ Representation（表征）→ Bias（偏置）→ Solver（求解器）  

只要记住这条链路，就能快速在项目里定位。  
