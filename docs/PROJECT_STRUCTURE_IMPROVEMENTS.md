# 项目结构改进方案

## 📋 当前问题汇总

### 🔴 严重问题

1. **根目录文件散乱**
   - 5个示例脚本（demo_*.py）
   - 4个测试脚本（test_*.py）
   - 8个历史记录文件（*_history.json）
   - 2个图片文件（*.png）
   - 1个临时文件（kk）

2. **examples 目录污染**
   - 混入了 blackbox_CantileverBeam_history.json
   - 应该只存放示例代码

3. **缺少标准项目文件**
   - ❌ LICENSE 文件（已创建）
   - ❌ CONTRIBUTING.md（已创建）
   - ❌ ADOPTERS.md（可选，用于展示使用方）

### ⚠️ 次要问题

4. **目录结构不完整**
   - 缺少 `examples/demos/` 用于存放演示脚本
   - 缺少 `data/results/` 用于存放实验结果
   - 缺少 `docs/api/` 用于API文档

5. **Git 历史污染**
   - .gitignore 配置较晚，历史文件已提交
   - 需要从 Git 历史中移除这些文件

---

## ✅ 改进方案

### 方案 A: 逐步清理（推荐）

#### 第一步：创建目录结构

```bash
mkdir -p examples/demos
mkdir -p examples/tutorials
mkdir -p data/results
mkdir -p data/experiments
mkdir -p data/visualizations
mkdir -p docs/api
mkdir -p docs/tutorials
```

#### 第二步：移动文件

```bash
# 移动示例脚本
mv bias_system_demo.py examples/demos/
mv demo_tsp.py examples/demos/
mv demo_using_my_classes.py examples/demos/
mv final_bias_demo.py examples/demos/
mv real_bias_demo.py examples/demos/

# 移动测试脚本
mv test_advisor_*.py test/
mv test_enhanced_search.py test/

# 移动结果文件
mv *_history.json data/results/
mv *.png data/results/

# 清理 examples 目录
mv examples/*_history.json data/results/
```

#### 第三步：更新 .gitignore

在 .gitignore 中添加：

```gitignore
# Project organization
data/results/
data/experiments/
data/visualizations/
*.history.json
*.png
!docs/**/*.png

# Temporary files
*.tmp
*.temp
kk
```

#### 第四步：清理 Git 历史

```bash
# 从 Git 历史中移除已忽略的文件
git rm -r --cached *_history.json
git rm -r --cached *.png
git rm -r --cached examples/*_history.json
git commit -m "chore: remove data files from git history"
```

---

### 方案 B: 使用自动化脚本（更简单）

已创建脚本：`scripts/organize_project.py`

**使用方法：**

```bash
python scripts/organize_project.py
```

该脚本会自动：
1. 创建所有需要的目录
2. 移动文件到正确位置
3. 清理临时文件
4. 更新 .gitignore
5. 为各目录创建 README 说明

---

## 📁 整理后的项目结构

```
nsgablack/
├── .github/               # GitHub 配置
│   └── workflows/
├── core/                  # 核心模块
│   ├── base.py
│   ├── solver.py
│   └── problems.py
├── solvers/              # 求解器实现
├── bias/                 # 偏置系统
│   ├── algorithmic/      # 算法偏置
│   ├── domain/           # 领域偏置
│   └── managers/         # 偏置管理器
├── utils/                # 工具函数
│   ├── representation/   # 表征管线
│   └── visualization.py
├── multi_agent/          # 多智能体系统
├── surrogate/            # 代理模型
├── examples/             # 示例代码
│   ├── demos/           # 演示脚本（新）
│   │   ├── bias_system_demo.py
│   │   ├── demo_tsp.py
│   │   └── ...
│   ├── tutorials/       # 教程（新）
│   │   └── README.md
│   ├── algorithmic_biases_demo.py
│   ├── bayesian_optimization_example.py
│   └── validation_smoke_suite.py
├── test/                # 测试文件
│   ├── test_advisor_*.py
│   └── test_enhanced_search.py
├── data/                # 数据目录
│   ├── results/         # 实验结果（新）
│   │   ├── *_history.json
│   │   └── *.png
│   ├── experiments/     # 实验数据（新）
│   └── visualizations/  # 可视化图表（新）
├── docs/                # 文档
│   ├── api/            # API 文档（新）
│   ├── tutorials/      # 教程文档（新）
│   ├── FRAMEWORK_OVERVIEW.md
│   └── VALIDATION_CHECKLIST.md
├── scripts/             # 工具脚本
│   └── organize_project.py
├── .gitignore
├── LICENSE             # ✨ 新增
├── CONTRIBUTING.md     # ✨ 新增
├── README.md
├── QUICKSTART.md
├── CHANGELOG.md
├── pyproject.toml
└── requirements.txt
```

---

## 🎯 改进效果

### 整理前
- ❌ 根目录混乱，15+ 散乱文件
- ❌ examples 目录被结果文件污染
- ❌ 数据文件分散在多处
- ❌ 缺少标准项目文件

### 整理后
- ✅ 根目录整洁，只保留必要文件
- ✅ examples 目录纯净，只含示例代码
- ✅ 数据集中管理在 data/ 目录
- ✅ 完善的项目文件体系
- ✅ 清晰的目录结构

---

## 📊 额外建议

### 1. 添加 CI/CD

创建 `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: python examples/validation_smoke_suite.py
```

### 2. 完善文档结构

```
docs/
├── api/              # API 文档（自动生成）
├── tutorials/        # 分步教程
│   ├── 01-quickstart.md
│   ├── 02-bias-system.md
│   ├── 03-representation.md
│   └── 04-multi-agent.md
├── FRAMEWORK_OVERVIEW.md
├── VALIDATION_CHECKLIST.md
└── ARCHITECTURE.md   # 架构设计文档
```

### 3. 添加 Makefile

创建 `Makefile` 简化常用操作：

```makefile
.PHONY: test clean install docs

test:
	python examples/validation_smoke_suite.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.history.json' -delete

install:
	pip install -r requirements.txt

docs:
	@echo "Generating docs..."
	# 这里可以添加文档生成命令
```

### 4. 改进 pyproject.toml

确保包含完整的元数据：

```toml
[project]
name = "nsgablack"
version = "0.1.0"
description = "基于偏置系统的多智能体 NSGA-II 多目标优化框架"
readme = "README.md"
requires-python = ">=3.8"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
keywords = ["optimization", "NSGA-II", "multi-agent", "bias-system"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
]
```

---

## 🚀 执行步骤

### 方式 1: 手动执行（适合小步改进）

```bash
# 1. 创建目录
mkdir -p examples/demos examples/tutorials data/results

# 2. 移动文件
# ... 按上面的命令逐个移动

# 3. 更新 Git
git add .
git commit -m "chore: reorganize project structure"
```

### 方式 2: 自动脚本（推荐）

```bash
# 1. 运行整理脚本
python scripts/organize_project.py

# 2. 检查结果
git status

# 3. 提交更改
git add .
git commit -m "chore: reorganize project structure

- Move demo scripts to examples/demos/
- Move test files to test/
- Move result files to data/results/
- Add LICENSE and CONTRIBUTING.md
- Update .gitignore
"
```

---

## 📝 后续维护建议

1. **定期清理**
   - 每周清理一次根目录的临时文件
   - 确保 examples/ 目录不混入结果文件

2. **文档同步**
   - 目录结构变化时及时更新 README.md
   - 保持示例代码与文档一致

3. **CI 检查**
   - 通过 CI 确保不提交不该提交的文件
   - 使用 pre-commit hooks 检查文件规范

4. **版本管理**
   - 使用语义化版本号
   - 在 CHANGELOG.md 中记录结构变更

---

生成时间: 2024-01-01
