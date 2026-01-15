# NSGABlack 文档结构概览

最后更新：2025-01-15
清理状态：✅ 已完成（删除42个过时文档）

---

## 📊 文档统计

| 指标 | 数量 |
|------|------|
| **总文档数** | 56个 |
| **根目录** | 4个 |
| **docs/** | 22个 |
| **架构文档** | 6个 |
| **算法文档** | 2个 |
| **用户指南** | 5个 |
| **模块文档** | 17个 |

---

## 🗂️ 文档分类

### 1. 用户文档（根目录）

```
nsgablack/
├── README.md                    # 主文档（完整框架介绍）
├── START_HERE.md                # 导航文档（快速入口）
├── QUICKSTART.md                # 快速开始指南
└── CONTRIBUTING.md              # 贡献指南
```

**用途**：用户首次接触项目时阅读的文档

**阅读顺序**：
1. START_HERE.md（2分钟）
2. QUICKSTART.md（5分钟）
3. README.md（30分钟，详细了解）

---

### 2. 核心文档（docs/）

#### 2.1 框架文档

```
docs/
├── README.md                                # 文档总览
├── FRAMEWORK_OVERVIEW.md                    # 框架概览
├── PROJECT_DETAILED_OVERVIEW.md             # 项目详细概览
├── PROJECT_CATALOG.md                       # 项目目录
├── FRAMEWORK_DESIGN_QA.md                   # 设计问答
├── RESEARCH_QA.md                           # 研究问答
├── ADVANCED_EXPERIMENTS.md                  # 高级实验文档
└── REORGANIZATION_REPORT.md                 # 重构报告
```

**用途**：理解框架设计思想和架构

#### 2.2 API文档

```
docs/
├── API_GUIDE.md                             # API使用指南
└── API_REFERENCE.md                         # API参考手册
```

**用途**：查找API接口和使用方法

#### 2.3 索引文档

```
docs/
├── BIAS_INDEX.md                            # 偏置系统索引
├── EXAMPLES_INDEX.md                        # 示例索引
├── REPRESENTATION_INDEX.md                  # 表征系统索引
├── TOOLS_INDEX.md                           # 工具索引
└── TAGGED_INDEX.md                          # 标签索引
```

**用途**：按标签查找功能

#### 2.4 质量指南

```
docs/
├── CODE_QUALITY_IMPROVEMENT_PLAN.md         # 代码质量改进计划
├── TYPE_HINTING_GUIDE.md                    # 类型提示指南
├── DOCSTRING_GUIDE.md                       # 文档字符串指南
└── DOCUMENTATION_CLEANUP_PLAN.md            # 文档清理计划
```

**用途**：贡献者开发和维护指南

---

### 3. 架构文档（docs/architecture/）

```
docs/architecture/
├── correct_module_structure.md               # 正确的模块结构
├── multi_agent_system.md                     # 多智能体系统
├── representation_pipeline.md                # 表征管线
├── algorithm_bias_pattern.md                 # 算法偏置模式
├── module_structure.md                       # 模块结构
├── nsga2_bias_architecture.md                # NSGA-II偏置架构
└── unified_bias_architecture.md              # 统一偏置架构
```

**用途**：深入理解系统架构

---

### 4. 算法文档（docs/algorithms/）

```
docs/algorithms/
├── monte_carlo.md                            # 蒙特卡洛算法
└── nsga2.md                                  # NSGA-II算法
```

**用途**：了解实现的算法

---

### 5. 用户指南（docs/user_guide/）

```
docs/user_guide/
├── bias_baby_guide.md                        # 偏置系统入门
├── bias_system.md                            # 偏置系统完整指南
├── external_api_navigation.md                # 外部API导航
├── optimization_strategies.md                # 优化策略
├── parallel_evaluation.md                    # 并行评估
├── surrogate_workflow.md                     # 代理工作流
└── surrogate_cheatsheet.md                   # 代理速查表
```

**用途**：学习如何使用框架

---

### 6. 模块文档

#### 6.1 偏置模板（bias/）

```
bias/
├── FunctionBiasTemplate.md                   # 函数偏置模板
├── algorithmic/AlgorithmicBiasTemplate.md    # 算法偏置模板
├── domain/DomainBiasTemplate.md              # 领域偏置模板
└── surrogate/                                # 代理偏置文档
    ├── PhaseScheduleBias.md
    ├── SurrogateBiasContext.md
    ├── SurrogateBiasTemplate.md
    ├── SurrogateControlBias.md
    └── UncertaintyBudgetBias.md
```

**用途**：开发自定义偏置

#### 6.2 多智能体系统（multi_agent/）

```
multi_agent/
├── README.md                                 # 多智能体系统文档
└── bias/
    └── SurrogateScoreBias.md                 # 代理评分偏置
```

**用途**：使用多智能体系统

#### 6.3 求解器文档（solvers/）

```
solvers/
└── SurrogateUnifiedNSGAII.md                 # 代理辅助NSGA-II文档
```

#### 6.4 示例文档

```
examples/
├── demos/README.md                           # 演示示例说明
└── ...
```

#### 6.5 实验文档

```
experiments/
└── ADVANCED_EXPERIMENTS_README.md            # 高级实验使用指南
```

---

## 📚 文档使用指南

### 对于新用户

**快速开始**（10分钟）：
1. 阅读 `START_HERE.md` - 了解项目结构
2. 阅读 `QUICKSTART.md` - 运行第一个示例
3. 浏览 `README.md` - 了解框架全貌

**深入学习**（1小时）：
1. 阅读 `docs/FRAMEWORK_OVERVIEW.md` - 理解框架设计
2. 阅读 `docs/user_guide/bias_baby_guide.md` - 学习偏置系统
3. 运行 `examples/` 中的示例

### 对于开发者

**贡献代码**：
1. 阅读 `CONTRIBUTING.md` - 贡献指南
2. 阅读 `docs/CODE_QUALITY_IMPROVEMENT_PLAN.md` - 代码质量标准
3. 阅读 `docs/TYPE_HINTING_GUIDE.md` - 类型提示指南
4. 阅读 `docs/DOCSTRING_GUIDE.md` - 文档字符串指南

**开发新功能**：
1. 查看 `docs/PROJECT_CATALOG.md` - 项目目录
2. 查看 `docs/architecture/` - 架构文档
3. 查看 `bias/*/Template.md` - 开发模板

### 对于研究者

**理解框架**：
1. 阅读 `README.md` - 框架诞生故事
2. 阅读 `docs/FRAMEWORK_DESIGN_QA.md` - 设计问答
3. 阅读 `docs/RESEARCH_QA.md` - 研究问答
4. 阅读 `docs/ADVANCED_EXPERIMENTS.md` - 实验验证

---

## 🎯 快速查找

### 我想...

**学习偏置系统**
→ `docs/user_guide/bias_baby_guide.md`
→ `docs/BIAS_INDEX.md`

**使用代理模型**
→ `docs/user_guide/surrogate_workflow.md`
→ `docs/user_guide/surrogate_cheatsheet.md`

**理解多智能体系统**
→ `multi_agent/README.md`
→ `docs/architecture/multi_agent_system.md`

**查找API**
→ `docs/API_REFERENCE.md`
→ `docs/API_GUIDE.md`

**添加新偏置**
→ `bias/FunctionBiasTemplate.md`
→ `bias/algorithmic/AlgorithmicBiasTemplate.md`

**运行实验**
→ `experiments/ADVANCED_EXPERIMENTS_README.md`
→ `docs/ADVANCED_EXPERIMENTS.md`

**贡献代码**
→ `CONTRIBUTING.md`
→ `docs/CODE_QUALITY_IMPROVEMENT_PLAN.md`

---

## 📖 文档维护

### 文档更新原则

1. **保持同步**：代码变更时同步更新文档
2. **单一来源**：每个概念只有一个权威文档
3. **交叉引用**：使用相对链接关联相关文档
4. **清晰简洁**：避免冗余，保持文档简洁

### 临时文档处理

开发过程中的临时文档应：
1. 使用描述性名称（包含`_REPORT.md`, `_PLAN.md`等）
2. 放在`docs/reports/`目录（已被.gitignore忽略）
3. 完成后整合到主文档并删除

### 文档清理

定期（每季度）检查文档：
- 删除过时内容
- 合并重复文档
- 更新失效链接
- 修正错误信息

---

## 🔗 文档链接

### 内部链接

使用相对路径链接：
```markdown
[偏置系统](bias/bias.py)
[API文档](docs/API_REFERENCE.md)
```

### 外部链接

- **GitHub**: https://github.com/sorrowoMan/nsgablack
- **PyPI**: （待发布）
- **ReadTheDocs**: （待配置）

---

## 📝 文档状态

| 类别 | 状态 | 备注 |
|------|------|------|
| 用户文档 | ✅ 完整 | 4个核心文档 |
| 框架文档 | ✅ 完整 | 覆盖所有主要概念 |
| API文档 | ✅ 完整 | API指南和参考 |
| 架构文档 | ✅ 完整 | 6个架构文档 |
| 用户指南 | ✅ 完整 | 7个实用指南 |
| 模块文档 | ✅ 完整 | 每个主要模块有文档 |
| 示例文档 | ✅ 部分 | 示例代码有注释 |

---

## ✅ 清理成果

### 删除的文档（42个）
- docs/reports/ - 21个临时报告
- experiments/ - 4个临时总结
- reports/ - 6个临时报告
- docs/ - 5个过时文档
- 根目录 - 3个过时文档
- test/ - 1个过时文档
- data/results/ - 1个过时文档
- examples/tutorials/ - 1个过时文档

### 保留的文档（56个）
- 所有核心用户文档
- 所有API和框架文档
- 所有架构和算法文档
- 所有实用指南和索引
- 所有模块文档

### 清理效果
- **文档数量**: 89 → 56 (-37%)
- **删除行数**: 14,001行
- **文档清晰度**: 大幅提升
- **维护难度**: 显著降低

---

**最后更新**: 2025-01-15
**维护者**: sorrowoMan
**文档版本**: 2.0
