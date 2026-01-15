# 文档清理计划

## 📊 分析结果

### 当前文档统计
- **总文档数**: 89个.md文件
- **docs/reports/**: 21个临时报告
- **experiments/**: 5个总结文档
- **reports/**: 3个临时报告
- **根目录**: 4个主要文档
- **其他模块**: 多个README和指南

---

## 🗑️ 建议删除的文档（42个）

### 1. docs/reports/ - 临时开发报告（21个）

这些文档都是开发过程中的临时报告，内容已被整合到其他文档中：

| 文件 | 原因 | 替代文档 |
|------|------|----------|
| `advisor_integration.md` | 临时集成报告 | `multi_agent/README.md` |
| `bayesian_analysis.md` | 临时分析文档 | `docs/user_guide/surrogate_*.md` |
| `bayesian_implementation.md` | 临时实现总结 | `docs/API_REFERENCE.md` |
| `bias_split.md` | 临时重构报告 | `docs/REORGANIZATION_REPORT.md` |
| `bias_standalone.md` | 临时重构报告 | `docs/REORGANIZATION_REPORT.md` |
| `cleanup_plan.md` | 临时计划文档 | `docs/PROJECT_CATALOG.md` |
| `import_fix_report.md` | 临时修复报告 | 已修复，不需要 |
| `import_verification_mechanism.md` | 临时技术文档 | 已过时 |
| `improvements.md` | 临时改进总结 | `docs/PROJECT_DETAILED_OVERVIEW.md` |
| `issues_analysis.md` | 临时问题分析 | 已解决 |
| `local_optimization.md` | 临时技术分析 | `docs/algorithms/*.md` |
| `module_compatibility.md` | 临时分析报告 | 已解决 |
| `nsga2_merge.md` | 临时合并报告 | 已完成 |
| `operators_as_biases_paradigm.md` | 临时设计文档 | `docs/FRAMEWORK_DESIGN_QA.md` |
| `operators_decision_analysis.md` | 临时决策文档 | 已决策完成 |
| `parallel_troubleshooting.md` | 临时故障文档 | 已修复 |
| `project_introduction.md` | 临时介绍文档 | `README.md` |
| `representation_pipeline_summary.md` | 临时总结文档 | `docs/REPRESENTATION_INDEX.md` |
| `research.md` | 临时研究文档 | `docs/RESEARCH_QA.md` |
| `search_methods_analysis.md` | 临时分析文档 | `multi_agent/README.md` |
| `search_methods_summary.md` | 临时总结文档 | `multi_agent/README.md` |

**删除命令**:
```bash
rm -rf docs/reports/
```

### 2. experiments/ - 临时总结文档（4个）

| 文件 | 原因 | 替代文档 |
|------|------|----------|
| `COMPLETION_SUMMARY.md` | 临时完成总结 | `README.md`实验章节 |
| `BUG_FIX_SUMMARY.md` | 临时bug修复总结 | 已修复，不需要 |
| `EXPERIMENT_README.md` | 临时实验说明 | `ADVANCED_EXPERIMENTS_README.md` |
| `ADVANCED_EXPERIMENTS_SUMMARY.md` | 临时高级实验总结 | `README.md`高级实验章节 |

**保留**: `ADVANCED_EXPERIMENTS_README.md`（使用指南）

**删除命令**:
```bash
cd experiments/
rm -f COMPLETION_SUMMARY.md BUG_FIX_SUMMARY.md EXPERIMENT_README.md ADVANCED_EXPERIMENTS_SUMMARY.md
```

### 3. reports/ - 临时报告（3个）

| 文件 | 原因 | 替代文档 |
|------|------|----------|
| `FINAL_COMPLETION_REPORT.md` | 临时完成报告 | `README.md` |
| `PROJECT_CLEANUP_REPORT.md` | 临时清理报告 | `README.md`或不需要 |
| `README_UPDATE_SUMMARY.md` | 临时更新总结 | `README.md` |

**删除命令**:
```bash
rm -rf reports/
```

### 4. 根目录过时文档（3个）

| 文件 | 原因 | 替代文档 |
|------|------|----------|
| `data/results/README.md` | 目录不存在或为空 | 不需要 |
| `examples/tutorials/README.md` | tutorials目录已删除 | `examples/demos/README.md` |
| `test/MOEAD_INTEGRATION_REPORT.md` | test/目录已删除 | 不需要 |

**删除命令**:
```bash
rm -f data/results/README.md
rm -f examples/tutorials/README.md
rm -f test/MOEAD_INTEGRATION_REPORT.md
```

### 5. 其他需要检查的文档（11个）

这些文档需要检查是否还需要：

| 文件 | 状态 | 操作 |
|------|------|------|
| `docs/DOCS_REORGANIZATION_REPORT.md` | 临时报告 | 删除 |
| `docs/REORGANIZATION_PLAN.md` | 临时计划 | 删除 |
| `docs/PROJECT_STRUCTURE_IMPROVEMENTS.md` | 临时改进文档 | 检查后决定 |
| `docs/VALIDATION_CHECKLIST.md` | 检查清单 | 检查是否需要 |
| `docs/algorithms/monte_carlo.md` | 算法文档 | 保留（有用） |
| `docs/algorithms/nsga2.md` | 算法文档 | 保留（有用） |
| `docs/user_guide/bias_system_legacy.md` | 遗留文档 | 删除（已有新版本） |
| `multi_agent/bias/SurrogateScoreBias.md` | 组件文档 | 保留 |
| `solvers/SurrogateUnifiedNSGAII.md` | 求解器文档 | 保留 |
| `bias/FunctionBiasTemplate.md` | 模板文档 | 保留 |
| `bias/algorithmic/AlgorithmicBiasTemplate.md` | 模板文档 | 保留 |

---

## ✅ 建议保留的核心文档

### 用户文档
- ✅ `README.md` - 主文档
- ✅ `START_HERE.md` - 导航文档
- ✅ `QUICKSTART.md` - 快速开始
- ✅ `CONTRIBUTING.md` - 贡献指南

### 核心文档（docs/）
- ✅ `API_GUIDE.md` - API指南
- ✅ `API_REFERENCE.md` - API参考
- ✅ `FRAMEWORK_OVERVIEW.md` - 框架概览
- ✅ `PROJECT_DETAILED_OVERVIEW.md` - 项目详细概览
- ✅ `PROJECT_CATALOG.md` - 项目目录
- ✅ `FRAMEWORK_DESIGN_QA.md` - 设计问答
- ✅ `RESEARCH_QA.md` - 研究问答
- ✅ `ADVANCED_EXPERIMENTS.md` - 高级实验
- ✅ `TYPE_HINTING_GUIDE.md` - 类型提示指南
- ✅ `DOCSTRING_GUIDE.md` - 文档字符串指南
- ✅ `CODE_QUALITY_IMPROVEMENT_PLAN.md` - 质量改进计划

### 索引文档
- ✅ `BIAS_INDEX.md` - 偏置索引
- ✅ `EXAMPLES_INDEX.md` - 示例索引
- ✅ `REPRESENTATION_INDEX.md` - 表征索引
- ✅ `TOOLS_INDEX.md` - 工具索引
- ✅ `TAGGED_INDEX.md` - 标签索引

### 架构文档
- ✅ `architecture/correct_module_structure.md` - 模块结构
- ✅ `architecture/multi_agent_system.md` - 多智能体系统
- ✅ `architecture/representation_pipeline.md` - 表征管线
- ✅ 其他架构文档

### 用户指南
- ✅ `user_guide/bias_baby_guide.md` - 偏置入门
- ✅ `user_guide/external_api_navigation.md` - API导航
- ✅ `user_guide/surrogate_workflow.md` - 代理工作流
- ✅ `user_guide/surrogate_cheatsheet.md` - 代理速查表
- ✅ `user_guide/optimization_strategies.md` - 优化策略
- ✅ `user_guide/parallel_evaluation.md` - 并行评估

### 实验文档
- ✅ `experiments/ADVANCED_EXPERIMENTS_README.md` - 高级实验使用指南

### 模块文档
- ✅ `multi_agent/README.md` - 多智能体系统
- ✅ `bias/surrogate/*.md` - 代理偏置文档

---

## 📋 清理执行计划

### 第1步：删除临时报告（高优先级）

```bash
# 删除docs/reports/
rm -rf docs/reports/

# 删除experiments/临时文档
cd experiments/
rm -f COMPLETION_SUMMARY.md
rm -f BUG_FIX_SUMMARY.md
rm -f EXPERIMENT_README.md
rm -f ADVANCED_EXPERIMENTS_SUMMARY.md

# 删除reports/
rm -rf reports/
```

### 第2步：删除过时文档

```bash
# 删除根目录过时文档
rm -f data/results/README.md
rm -f examples/tutorials/README.md
rm -f test/MOEAD_INTEGRATION_REPORT.md

# 删除docs/临时文档
rm -f docs/DOCS_REORGANIZATION_REPORT.md
rm -f docs/REORGANIZATION_PLAN.md
rm -f docs/PROJECT_STRUCTURE_IMPROVEMENTS.md
rm -f docs/user_guide/bias_system_legacy.md
```

### 第3步：清理空目录

```bash
# 检查并删除空目录
find . -type d -empty -delete
```

### 第4步：更新.gitignore

确保.gitignore忽略：
- `docs/reports/`
- `reports/`
- `data/results/`

---

## 📊 清理后的预期结果

### 文档数量对比

| 类别 | 清理前 | 清理后 | 减少 |
|------|--------|--------|------|
| 总文档数 | 89 | ~55 | ~34 (-38%) |
| docs/reports/ | 21 | 0 | -21 |
| experiments/*.md | 5 | 1 | -4 |
| reports/ | 3 | 0 | -3 |
| 其他临时文档 | 6 | 0 | -6 |

### 核心文档保留（~55个）

#### 必需文档（15个）
- README, START_HERE, QUICKSTART, CONTRIBUTING
- API指南、API参考、框架概览
- 设计问答、研究问答、项目目录
- 类型提示、文档字符串、质量改进

#### 索引文档（5个）
- BIAS_INDEX, EXAMPLES_INDEX, REPRESENTATION_INDEX, TOOLS_INDEX, TAGGED_INDEX

#### 架构文档（6个）
- 正确模块结构、多智能体系统、表征管线等

#### 用户指南（5个）
- 偏置入门、API导航、代理工作流等

#### 模块文档（~24个）
- 各模块的README和模板文档

---

## ✅ 清理完成后的好处

1. **减少混乱**: 删除38%的过时文档
2. **提高可维护性**: 只保留活跃文档
3. **降低认知负担**: 用户更容易找到需要的文档
4. **避免混淆**: 不再有多个版本的同一文档
5. **保持同步**: 文档与代码状态一致

---

**状态**: 🟡 待执行
**预计删除**: 42个文档文件
**预计保留**: ~55个核心文档
**清理时间**: ~5分钟
