# 文档整理计划

## 📊 当前文档分布

**根目录**: 32 个 .md 文件
**docs/**: 15 个 .md 文件
**总计**: 47 个文档文件

## 🎯 新的文档结构

```
docs/
├── README.md                    ← 项目概述（主入口）
├── QUICKSTART.md                ← 快速入门
├── CHANGELOG.md                 ← 变更日志
├── API_REFERENCE.md             ← API 参考
│
├── user_guide/                  ← 用户指南
│   ├── bias_system.md          ← 偏置系统使用
│   ├── multi_agent.md          ← 多智能体系统
│   ├── surrogate_assisted.md   ← 代理模型辅助
│   ├── parallel_evaluation.md  ← 并行评估
│   └── optimization_strategies.md ← 优化策略
│
├── architecture/                ← 架构文档
│   ├── module_structure.md     ← 模块结构
│   ├── bias_architecture.md    ← 偏置架构
│   └── design_patterns.md      ← 设计模式
│
├── algorithms/                  ← 算法说明
│   ├── nsga2.md                ← NSGA-II
│   ├── moead.md                ← MOEA/D
│   ├── vns.md                  ← 变邻域搜索
│   └── monte_carlo.md          ← 蒙特卡洛
│
├── development/                 ← 开发文档
│   ├── contributing.md         ← 贡献指南
│   └── code_style.md           ← 代码规范
│
└── reports/                     ← 技术报告
    ├── nsga2_merge.md          ← NSGA-II 合并报告
    ├── issues_analysis.md      ← 问题分析报告
    ├── library_structure.md    ← 库结构分析
    └── improvements.md         ← 改进总结
```

## 📋 文档移动计划

### 1. 用户指南 (user_guide/)

| 源文件 | 目标位置 | 操作 |
|--------|----------|------|
| docs/BIAS_V2_GUIDE.md | user_guide/bias_system.md | 移动 |
| docs/bias_system_guide.md | user_guide/ (合并到 bias_system.md) | 合并 |
| docs/PARALLEL_EVALUATION_GUIDE.md | user_guide/parallel_evaluation.md | 移动 |
| docs/OPTIMIZATION_STRATEGY_GUIDE.md | user_guide/optimization_strategies.md | 移动 |
| PARALLEL_EVALUATION_TROUBLESHOOTING.md | user_guide/parallel_evaluation.md | 合并 |

### 2. 架构文档 (architecture/)

| 源文件 | 目标位置 | 操作 |
|--------|----------|------|
| COMPLETE_LIBRARY_STRUCTURE.md | architecture/module_structure.md | 移动 |
| CORRECT_MODULE_STRUCTURE.md | architecture/module_structure.md | 合并 |
| NSGA2_BIAS_ARCHITECTURE.md | architecture/bias_architecture.md | 移动 |
| UNIFIED_NSGA2_BIAS_ARCHITECTURE.md | architecture/bias_architecture.md | 合并 |
| ALGORITHM_BIAS_PATTERN.md | architecture/bias_architecture.md | 合并 |
| MULTI_AGENT_SYSTEM.md | architecture/module_structure.md | 合并 |

### 3. 算法说明 (algorithms/)

| 源文件 | 目标位置 | 操作 |
|--------|----------|------|
| docs/README_nsgablack.md | algorithms/nsga2.md | 移动并重写 |
| docs/README_monte_carlo.md | algorithms/monte_carlo.md | 移动 |
| (需要创建) algorithms/moead.md | 创建 MOEA/D 文档 | 新建 |
| (需要创建) algorithms/vns.md | 创建 VNS 文档 | 新建 |

### 4. 开发文档 (development/)

| 源文件 | 目标位置 | 操作 |
|--------|----------|------|
| (需要创建) development/contributing.md | 贡献指南 | 新建 |
| (需要创建) development/code_style.md | 代码规范 | 新建 |

### 5. 技术报告 (reports/)

| 源文件 | 目标位置 | 操作 |
|--------|----------|------|
| NSGA2_MERGE_REPORT.md | reports/nsga2_merge.md | 移动 |
| ISSUES_ANALYSIS_REPORT.md | reports/issues_analysis.md | 移动 |
| COMPLETE_LIBRARY_STRUCTURE.md | reports/library_structure.md | 复制 |
| IMPROVEMENTS_SUMMARY.md | reports/improvements.md | 移动 |
| BIAS_SPLIT_SUMMARY.md | reports/bias_split.md | 移动 |
| BIAS_STANDALONE_SUMMARY.md | reports/bias_standalone.md | 移动 |
| ADVISOR_INTEGRATION_SUMMARY.md | reports/advisor_integration.md | 移动 |
| MODULE_COMPATIBILITY_REPORT.md | reports/module_compatibility.md | 移动 |
| RESEARCH_STATEMENT.md | reports/research.md | 移动 |

### 6. 根目录保留的文档

| 文件 | 保留位置 | 原因 |
|------|----------|------|
| README.md | README.md | 主 README |
| QUICKSTART.md | QUICKSTART.md | 快速开始 |
| API_GUIDE.md | API_GUIDE.md | API 指南（或移到 docs/） |
| CHANGELOG.md | CHANGELOG.md | 变更日志 |
| PROJECT_INTRODUCTION.md | (合并到 README.md) | 合并 |
| README_nsgablack.md | (删除或合并) | 重复 |

### 7. 待删除的重复文档

| 文件 | 原因 |
|------|------|
| docs/README.md | 与根目录 README.md 重复 |
| docs/QUICKSTART.md | 与根目录 QUICKSTART.md 重复 |
| docs/README_nsgablack.md | 移动到 algorithms/ |
| README_nsgablack.md | 已有新的版本 |
| CLEANUP_ACTION_PLAN.md | 已完成，归档到 reports/ |
| CURRENT_SEARCH_METHODS_SUMMARY.md | 归档到 reports/ |
| ENHANCED_SEARCH_GUIDE.md | 归档到 user_guide/ 或删除 |
| SEARCH_METHODS_ANALYSIS.md | 归档到 reports/ |
| docs/BIAS_README.md | 被 BIAS_V2_GUIDE.md 替代 |
| docs/BAYESIAN_OPTIMIZATION_ANALYSIS.md | 归档到 reports/ |
| docs/BAYESIAN_IMPLEMENTATION_SUMMARY.md | 归档到 reports/ |
| docs/LOCAL_OPTIMIZATION_ANALYSIS.md | 归档到 reports/ |

## 📝 需要创建/合并的文档

### 需要合并
1. **bias_system.md** - 合并 BIAS_V2_GUIDE.md + bias_system_guide.md
2. **bias_architecture.md** - 合并多个架构文档
3. **module_structure.md** - 合并结构相关文档
4. **parallel_evaluation.md** - 合并指南和故障排除

### 需要新建
1. **algorithms/moead.md** - MOEA/D 算法文档
2. **algorithms/vns.md** - VNS 算法文档
3. **development/contributing.md** - 贡献指南
4. **development/code_style.md** - 代码规范

## 🔄 执行步骤

1. ✅ 创建目录结构
2. ⏳ 移动文件到对应目录
3. ⏳ 合并重复文档
4. ⏳ 创建新文档
5. ⏳ 更新 README.md 中的链接
6. ⏳ 删除根目录的重复文档
7. ⏳ 更新其他文件中的文档链接

## 📊 预期结果

- **整理前**: 47 个文档，分散在 2 个目录
- **整理后**: ~30 个文档， organized in 6 个子目录
- **删除重复**: ~17 个文档
- **净减少**: ~17 个文件（36%）
