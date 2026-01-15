# NSGABlack 代码质量改进指南

本文档总结NSGABlack框架的代码质量改进计划，包括测试、类型提示和文档字符串。

## 📊 当前状态

| 指标 | 当前值 | 目标值 | 状态 |
|------|--------|--------|------|
| 测试覆盖率 | 0% | 70% | 🔴 待开始 |
| 类型提示覆盖 | ~40% | 70% | 🟡 进行中 |
| 文档字符串覆盖 | ~60% | 90% | 🟡 进行中 |
| CI/CD配置 | ✅ 完成 | ✅ 完成 | ✅ 完成 |

## 🎯 改进目标

### 短期目标（1-2周）
- ✅ 配置测试框架（pytest）
- ✅ 配置CI/CD（GitHub Actions）
- ✅ 编写核心模块测试（bias, core, representation）
- 🔄 添加类型提示（核心模块）
- 📝 更新文档字符串（核心模块）

### 中期目标（1-2月）
- 扩展测试覆盖（70%+）
- 添加类型提示（所有公共API）
- 完善文档字符串（所有公共API）
- 添加性能测试
- 添加集成测试

### 长期目标（3-6月）
- 测试覆盖率90%+
- 类型提示100%
- 文档字符串100%
- 持续集成优化
- 自动化代码质量检查

## 📁 项目结构

```
nsgablack/
├── tests/                    # ✅ 新增：测试目录
│   ├── __init__.py
│   ├── conftest.py           # pytest配置
│   ├── test_bias.py          # 偏置系统测试
│   ├── test_solver.py        # 求解器测试
│   ├── test_representation.py # 表征系统测试
│   └── test_surrogate.py     # 代理模型测试
├── docs/
│   ├── TYPE_HINTING_GUIDE.md # ✅ 新增：类型提示指南
│   └── DOCSTRING_GUIDE.md    # ✅ 新增：文档字符串指南
├── .github/workflows/
│   └── test.yml              # ✅ 更新：CI/CD配置
└── pyproject.toml            # ✅ 更新：工具配置
```

## 🧪 测试系统

### 已创建的测试文件

#### 1. `tests/test_bias.py` - 偏置系统测试
- ✅ BiasModule基础功能测试
- ✅ 罚函数和奖函数测试
- ✅ 偏置计算测试
- ✅ 约束偏置场景测试
- ✅ 参数化测试

#### 2. `tests/test_solver.py` - 求解器测试
- ✅ BlackBoxProblem测试
- ✅ 求解器初始化测试
- ✅ 种群初始化测试
- ✅ 优化过程测试（慢速）
- ✅ 带偏置的求解器测试
- ✅ 可重复性测试

#### 3. `tests/test_representation.py` - 表征系统测试
- ✅ 连续变量表征测试
- ✅ 整数变量表征测试
- ✅ 排列变量表征测试
- ✅ 混合变量表征测试
- ✅ 约束处理测试

#### 4. `tests/test_surrogate.py` - 代理模型测试
- ✅ 代理训练器测试
- ✅ 代理管理器测试
- ✅ 不确定性采样测试
- ✅ 代理辅助优化测试（慢速）

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_bias.py -v

# 运行带标记的测试
pytest tests/ -m "unit"          # 仅单元测试
pytest tests/ -m "not slow"      # 排除慢速测试

# 生成覆盖率报告
pytest tests/ --cov=. --cov-report=html

# 查看覆盖率报告
# 打开 htmlcov/index.html
```

### 测试组织

测试使用以下标记分类：
- `@pytest.mark.unit`: 单元测试（快速）
- `@pytest.mark.slow`: 慢速测试（优化过程）
- `@pytest.mark.integration`: 集成测试
- `@pytest.mark.bias`: 偏置相关
- `@pytest.mark.surrogate`: 代理相关

## 🔍 类型提示

### 改进指南

详见 `docs/TYPE_HINTING_GUIDE.md`

### 关键改进点

1. **函数类型提示**
```python
# 之前
def evaluate(self, x):
    return sum(x**2)

# 之后
def evaluate(self, x: np.ndarray) -> float:
    return float(np.sum(x**2))
```

2. **类类型提示**
```python
class Solver:
    problem: 'BlackBoxProblem'
    population: List[np.ndarray]
    best_x: Optional[np.ndarray]
```

3. **复杂类型**
```python
from typing import Dict, List, Tuple, Optional, Callable

def optimize(
    callback: Optional[Callable[[float], None]] = None
) -> Tuple[np.ndarray, float]:
    ...
```

### 运行类型检查

```bash
# 检查所有代码
mypy .

# 检查特定模块
mypy bias/ core/ solvers/

# 生成HTML报告
mypy --html-report ./mypy-report .
```

## 📝 文档字符串

### 改进指南

详见 `docs/DOCSTRING_GUIDE.md`

### Google风格模板

```python
def function_name(arg1: str, arg2: int = 10) -> bool:
    """函数简短描述（一句话）。

    更详细的描述（可选）。

    Args:
        arg1: 参数1的描述。
        arg2: 参数2的描述，默认为10。

    Returns:
        返回值的描述。

    Raises:
        ValueError: 参数无效时抛出。

    Examples:
        >>> function_name("test", 20)
        True
    """
    pass
```

### 检查文档风格

```bash
# 安装pydocstyle
pip install pydocstyle

# 检查文档风格
pydocstyle bias/ core/ solvers/
```

## 🔄 CI/CD配置

### GitHub Actions工作流

已配置 `.github/workflows/test.yml`：

#### 1. 测试作业
- ✅ 多Python版本测试（3.8, 3.9, 3.10, 3.11）
- ✅ 多操作系统测试（Ubuntu, Windows, macOS）
- ✅ 测试覆盖率报告
- ✅ Codecov集成

#### 2. 代码质量作业
- ✅ Black代码格式检查
- ✅ isort导入排序检查
- ✅ flake8语法检查
- ✅ mypy类型检查
- ✅ bandit安全检查

#### 3. 文档作业
- ✅ API文档生成
- ✅ Sphinx文档构建
- ✅ 文档链接检查

#### 4. 集成测试作业
- ✅ 基本示例运行
- ✅ 安装测试

### CI徽章

在README中添加：

```markdown
[![Tests](https://github.com/sorrowoMan/nsgablack/actions/workflows/test.yml/badge.svg)](https://github.com/sorrowoMan/nsgablack/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/sorrowoMan/nsgablack/branch/main/graph/badge.svg)](https://codecov.io/gh/sorrowoMan/nsgablack)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
```

## 📋 改进清单

### 高优先级（立即开始）

- [x] 配置pytest测试框架
- [x] 配置mypy类型检查
- [x] 配置GitHub Actions CI/CD
- [x] 编写核心模块测试
  - [x] bias系统测试
  - [x] solver测试
  - [x] representation测试
  - [x] surrogate测试
- [ ] 为核心模块添加类型提示
  - [ ] `bias/bias.py` (部分完成)
  - [ ] `core/solver.py`
  - [ ] `core/base.py`
  - [ ] `solvers/*.py`
- [ ] 为核心模块更新文档字符串
  - [ ] `bias/bias.py`
  - [ ] `core/solver.py`
  - [ ] `core/base.py`

### 中优先级（1-2周内）

- [ ] 扩展测试覆盖
  - [ ] 多智能体系统测试
  - [ ] 代理模型详细测试
  - [ ] 表征约束测试
  - [ ] 集成测试
- [ ] 添加性能测试
- [ ] 添加边界情况测试
- [ ] 为工具模块添加类型提示
- [ ] 为工具模块更新文档字符串

### 低优先级（1-2月内）

- [ ] 达到70%测试覆盖率
- [ ] 为所有公共API添加类型提示
- [ ] 为所有公共API添加文档字符串
- [ ] 添加示例测试
- [ ] 添加回归测试

## 🚀 快速开始

### 1. 安装开发依赖

```bash
pip install -e .[dev]
```

### 2. 运行测试

```bash
# 快速测试（排除慢速）
pytest tests/ -m "not slow" -v

# 完整测试
pytest tests/ -v

# 带覆盖率
pytest tests/ --cov=. --cov-report=html
```

### 3. 类型检查

```bash
mypy bias/ core/ solvers/
```

### 4. 代码格式化

```bash
# 格式化代码
black .

# 检查格式
black --check .
```

### 5. 提交前检查

```bash
# 运行所有检查
pytest tests/ -v
mypy bias/ core/ solvers/
black --check .
pydocstyle bias/ core/ solvers/
```

## 📊 进度追踪

### 测试覆盖目标

| 模块 | 当前进度 | 目标 | 状态 |
|------|----------|------|------|
| bias/ | 20% | 70% | 🟡 |
| core/ | 15% | 70% | 🟡 |
| solvers/ | 10% | 70% | 🔴 |
| surrogate/ | 25% | 70% | 🟡 |
| multi_agent/ | 0% | 70% | 🔴 |
| utils/ | 5% | 70% | 🔴 |

### 类型提示目标

| 模块 | 当前进度 | 目标 | 状态 |
|------|----------|------|------|
| bias/ | 60% | 80% | 🟢 |
| core/ | 40% | 80% | 🟡 |
| solvers/ | 30% | 80% | 🟡 |
| surrogate/ | 40% | 80% | 🟡 |
| multi_agent/ | 20% | 80% | 🔴 |
| utils/ | 30% | 80% | 🟡 |

### 文档字符串目标

| 模块 | 当前进度 | 目标 | 状态 |
|------|----------|------|------|
| bias/ | 70% | 95% | 🟢 |
| core/ | 60% | 95% | 🟡 |
| solvers/ | 50% | 95% | 🟡 |
| surrogate/ | 60% | 95% | 🟡 |
| multi_agent/ | 40% | 95% | 🟡 |
| utils/ | 50% | 95% | 🟡 |

## 🎓 学习资源

### 测试
- [pytest官方文档](https://docs.pytest.org/)
- [pytest中文文档](https://pytest-chinese-doc.readthedocs.io/)

### 类型提示
- [Python类型提示](https://docs.python.org/3/library/typing.html)
- [mypy文档](https://mypy.readthedocs.io/)

### 文档字符串
- [Google Python风格指南](https://google.github.io/styleguide/pyguide.html)
- [Napolean文档扩展](https://sphinxcontrib-napoleon.readthedocs.io/)

### CI/CD
- [GitHub Actions文档](https://docs.github.com/en/actions)
- [Codecov文档](https://docs.codecov.com/)

## 💡 最佳实践

### 1. 测试驱动开发（TDD）

```python
# 1. 先写测试
def test_new_feature():
    result = new_function()
    assert result == expected_value

# 2. 实现功能
def new_function():
    return expected_value

# 3. 运行测试
pytest tests/test_new_feature.py -v
```

### 2. 渐进式类型提示

```python
# 阶段1：添加基本类型
def evaluate(x):
    return sum(x**2)

# 阶段2：添加返回类型
def evaluate(x) -> float:
    return sum(x**2)

# 阶段3：添加参数类型
def evaluate(x: np.ndarray) -> float:
    return float(np.sum(x**2))
```

### 3. 持续文档更新

```python
# 每次修改代码时同步更新文档
def function(arg):
    """简要描述。

    # 更新日期：2025-01-15
    # 更新内容：添加新参数
    """
    pass
```

## ✅ 成功标准

代码质量改进完成的标准：

- ✅ 所有CI/CD检查通过
- ✅ 测试覆盖率达到70%
- ✅ 所有公共API有类型提示
- ✅ 所有公共API有文档字符串
- ✅ mypy检查无错误
- ✅ pydocstyle检查无警告

---

**状态**: 🟢 进行中
**开始日期**: 2025-01-15
**预计完成**: 2025-02-28
**负责人**: sorrowoMan

**记住**: 代码质量是一个持续改进的过程，不要追求完美，重要的是持续进步！
