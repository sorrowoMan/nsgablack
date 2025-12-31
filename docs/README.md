# NSGABlack 文档中心

欢迎来到 NSGABlack 文档中心！这里包含了框架的完整文档。

## 📚 快速导航

### 快速开始
- [快速入门指南](../QUICKSTART.md) - 10分钟上手 NSGABlack
- [API 参考](API_REFERENCE.md) - 完整的 API 文档
- [API 指南](API_GUIDE.md) - 详细的 API 使用指南

### 用户指南
- [偏置系统使用](user_guide/bias_system.md) - 如何使用偏置系统
- [偏置系统遗留文档](user_guide/bias_system_legacy.md) - 旧版偏置系统文档
- [并行评估](user_guide/parallel_evaluation.md) - 并行评估使用指南
- [优化策略](user_guide/optimization_strategies.md) - 优化策略选择
- [增强搜索方法](user_guide/enhanced_search.md) - 增强搜索方法指南

### 架构文档
- [模块结构](architecture/module_structure.md) - 完整的代码库结构
- [正确的模块结构](architecture/correct_module_structure.md) - 模块组织规范
- [NSGA-II 偏置架构](architecture/nsga2_bias_architecture.md) - NSGA-II 与偏置系统
- [统一偏置架构](architecture/unified_bias_architecture.md) - 统一的偏置架构
- [算法偏置模式](architecture/algorithm_bias_pattern.md) - 算法偏置设计模式
- [多智能体系统](architecture/multi_agent_system.md) - 多智能体系统架构

### 算法说明
- [NSGA-II](algorithms/nsga2.md) - NSGA-II 算法详解
- [蒙特卡洛方法](algorithms/monte_carlo.md) - 蒙特卡洛优化方法

### 开发文档
*(待完善)*
- 贡献指南
- 代码规范

### 技术报告
- [NSGA-II 合并报告](reports/nsga2_merge.md) - 代码合并详细报告
- [问题分析报告](reports/issues_analysis.md) - 代码库问题分析
- [改进总结](reports/improvements.md) - 改进工作总结
- [偏置系统拆分](reports/bias_split.md) - 偏置模块拆分报告
- [偏置系统独立](reports/bias_standalone.md) - 偏置系统独立化
- [Advisor 集成](reports/advisor_integration.md) - Advisor 模块集成
- [模块兼容性](reports/module_compatibility.md) - 模块兼容性报告
- [研究陈述](reports/research.md) - 研究背景和目标
- [清理计划](reports/cleanup_plan.md) - 代码清理计划
- [搜索方法总结](reports/search_methods_summary.md) - 搜索方法总结
- [搜索方法分析](reports/search_methods_analysis.md) - 搜索方法详细分析
- [项目介绍](reports/project_introduction.md) - 项目背景介绍
- [并行故障排除](reports/parallel_troubleshooting.md) - 并行评估问题解决
- [贝叶斯分析](reports/bayesian_analysis.md) - 贝叶斯优化分析
- [贝叶斯实现](reports/bayesian_implementation.md) - 贝叶斯优化实现
- [局部优化](reports/local_optimization.md) - 局部优化分析

### 其他
- [变更日志](../CHANGELOG.md) - 版本更新记录
- [文档整理计划](REORGANIZATION_PLAN.md) - 文档重组计划

## 🎯 按角色查找文档

### 初学者
1. 从 [快速入门指南](../QUICKSTART.md) 开始
2. 阅读 [API 参考](API_REFERENCE.md) 了解基本接口
3. 查看 [用户指南](user_guide/) 学习高级功能

### 算法研究者
1. 阅读 [架构文档](architecture/) 了解系统设计
2. 查看 [算法说明](algorithms/) 了解具体算法实现
3. 参考 [技术报告](reports/) 了解设计决策

### 贡献者
1. 阅读 [架构文档](architecture/) 了解代码结构
2. 查看 [开发文档](development/) 了解贡献规范（待完善）
3. 参考 [技术报告](reports/) 了解实现细节

## 📖 文档结构

```
docs/
├── README.md                   # 本文档
├── API_GUIDE.md                # API 使用指南
├── API_REFERENCE.md            # API 参考
│
├── user_guide/                 # 用户指南
│   ├── bias_system.md         # 偏置系统
│   ├── parallel_evaluation.md # 并行评估
│   └── optimization_strategies.md # 优化策略
│
├── architecture/               # 架构文档
│   └── module_structure.md    # 模块结构
│
├── algorithms/                 # 算法说明
│   ├── nsga2.md               # NSGA-II
│   └── monte_carlo.md         # 蒙特卡洛
│
├── development/                # 开发文档（待完善）
│
└── reports/                    # 技术报告
    ├── nsga2_merge.md         # NSGA-II 合并报告
    └── issues_analysis.md     # 问题分析
```

## 🔍 快速搜索

- **找不到 API？** 查看 [API 参考](API_REFERENCE.md)
- **遇到问题？** 检查 [技术报告](reports/) 中的故障排除文档
- **想了解架构？** 阅读 [架构文档](architecture/)
- **想贡献代码？** 参考 [开发文档](development/)（待完善）

## 📝 文档贡献

文档是持续改进的。如果你发现文档有错误或需要补充，请贡献！

---

**最后更新**: 2025-12-31
**文档版本**: v2.0
