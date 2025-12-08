# 更新日志

所有重要的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.1.0] - 2025-12-07

### 🎉 重大变更 - 偏置系统重构

#### 📦 模块化分离
- **偏置库分离**: 成功将偏置库从单一大文件分离为专门的模块化架构
- **双重架构**: 引入算法偏置(Algorithmic Bias)和业务偏置(Domain Bias)的分离设计
- **解决导航问题**: 响应用户反馈"翻起来太麻烦"，现在相关功能集中管理

#### 🆕 新增文件
- `utils/bias_base.py` - 基础类定义 (BaseBias, AlgorithmicBias, DomainBias, OptimizationContext)
- `utils/bias_library_algorithmic.py` - 算法偏置库 (641行)
- `utils/bias_library_domain.py` - 业务偏置库 (892行)
- `utils/bias_v2.py` - 重构的主要接口和管理器 (519行)

#### 🚀 新功能
- **算法偏置类型**: DiversityBias, ConvergenceBias, ExplorationBias, PrecisionBias, AdaptiveDiversityBias, MemoryGuidedBias等
- **业务偏置类型**: ConstraintBias, PreferenceBias, ObjectiveBias, EngineeringDesignBias, FinancialBias, MLHyperparameterBias等
- **模板系统**: 预定义配置模板 (basic_engineering, financial_optimization, machine_learning)
- **便捷函数**: 快速创建特定领域偏置管理器
- **动态权重调整**: 根据优化状态自动调整偏置权重
- **配置管理**: 支持偏置配置的保存和加载

#### ✅ 改进
- **导航便利性**: 算法偏置和业务偏置分别管理，便于查找和修改
- **模块化设计**: 每个模块职责单一，支持插件式扩展
- **向后兼容**: 保持原有API接口，现有代码无需修改

#### 📚 文档更新
- 更新 README.md - 新偏置系统使用示例
- 重写 API_REFERENCE.md - 偏置系统v2.0完整文档
- 更新 QUICKSTART.md - 快速入门指南
- 创建 `examples/bias_v2_simple_example.py` - 新系统使用示例
- 创建 `test_bias_split.py` - 功能测试脚本
- 创建 `BIAS_SPLIT_SUMMARY.md` - 完成总结文档

#### 🧪 测试验证
- 所有导入功能正常工作
- 偏置计算功能验证通过
- 创建并运行了完整的示例程序
- 确认向后兼容性保持

## [v1.0.0] - 2024-12-07

### 🎉 主要更新

#### 🐛 Bug 修复
- **修复了导入问题** - 所有示例文件现在可以直接运行，无需额外配置
- 解决了相对导入超出顶层包的问题
- 统一了项目内所有模块的导入策略

#### 📚 文档完善
- **全新的 README.md** - 包含完整的使用指南和 API 文档
- 新增 **快速入门指南** (`docs/QUICKSTART.md`) - 5分钟上手教程
- 新增 **API 参考文档** (`docs/API_REFERENCE.md`) - 详细的 API 文档
- 添加了常见使用场景示例

#### 🚀 改进的功能
- 优化了模块导入结构，提高项目的可复用性
- 增强了偏置模块的灵活性
- 改进了错误处理和调试信息

#### 🔧 技术改进
- 采用 try/except 双重导入策略，支持包导入和直接运行
- 统一了代码风格和文档规范
- 优化了项目结构，提高可维护性

### ✨ 核心功能

#### 多目标优化 (NSGA-II)
- 支持任意数量的目标函数
- 自动 Pareto 前沿分析
- 可配置的精英保留策略
- 多样性维护机制

#### 代理模型辅助优化
- 支持高斯过程 (GP)、径向基函数 (RBF)、随机森林 (RF) 等代理模型
- 智能采样策略
- 有效减少昂贵函数的评估次数

#### 偏置引导优化
- 可扩展的奖励和惩罚函数系统
- 内置常用的偏置函数库
- 支持约束优化
- 历史信息引导

#### 其他求解器
- 变邻域搜索 (VNS)
- 蒙特卡洛优化
- 机器学习引导的初始化

### 📁 项目结构

```
nsgablack/
├── core/                     # 核心算法模块
├── solvers/                 # 专门求解器
├── utils/                   # 工具模块
├── ml/                      # 机器学习模块
├── meta/                    # 元优化
├── docs/                    # 📚 文档
└── examples/                # 示例代码
```

### 🎯 快速开始

```bash
# 运行任何示例
python examples/bias_example.py

# 查看快速入门
cat docs/QUICKSTART.md

# 查看 API 文档
cat docs/API_REFERENCE.md
```

---

## [v0.9.x] - 之前版本

### 功能
- 基础 NSGA-II 实现
- 代理模型辅助优化
- 蒙特卡洛方法
- 偏置模块

### 问题
- 导入路径配置复杂
- 文档不完善
- 示例文件难以直接运行

---

## 贡献者

- 感谢所有提供反馈和建议的用户
- 欢迎提交 Issue 和 Pull Request

## 路线图

### v1.1.0 (计划中)
- [ ] 支持更多优化算法 (PSO, DE, CMA-ES)
- [ ] 增强可视化功能
- [ ] 支持并行化优化
- [ ] 添加更多内置问题

### v1.2.0 (计划中)
- [ ] Web 界面
- [ ] Jupyter Notebook 教程
- [ ] 性能基准测试
- [ ] 自动超参数调优