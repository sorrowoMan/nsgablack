# 贡献指南

感谢您对 nsgablack 项目的关注！我们欢迎任何形式的贡献。

## 如何贡献

### 报告问题

- 在提交 Issue 前，请先搜索现有问题
- 使用清晰简洁的标题描述问题
- 提供详细的复现步骤和环境信息
- 如果可能，附上最小可复现代码

### 提交代码

1. **Fork 项目**
   ```bash
   git clone https://github.com/sorrowoMan/nsgablack.git
   cd nsgablack
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **编写代码**
   - 遵循现有代码风格
   - 添加必要的文档和注释
   - 确保代码通过测试

4. **提交更改**
   ```bash
   git add .
   git commit -m "Add: your feature description"
   ```

5. **推送并创建 PR**
   ```bash
   git push origin feature/your-feature-name
   ```

### 代码规范

- 使用 `black` 格式化代码
- 遵循 PEP 8 规范
- 为新功能添加测试
- 更新相关文档

### Legacy / Solver-control-first（必须遵守）

- `core/solver.py` 视为 **Legacy 兼容入口**，不再作为新增功能首选接入点。
- 新运行期能力必须优先走 Solver 控制面路径（`core.blank_solver.SolverBase` 控制面方法、Adapter context/snapshot projection、Plugin hook）。
- 禁止在新组件中直接镜像写入 `solver.population/objectives/constraint_violations/best_x/best_objective/...`。
- `project doctor --strict` 会检查“绕过 Runtime 直接写 solver 状态”的代码并报错。

### Catalog 注册边界（必须遵守）

- 框架级组件（`nsgablack.*`）必须进入全局 Catalog。
  - 为什么：框架级能力面向全项目复用，必须保证“可发现（search）+ 可审计（doctor/inspector）+ 可复现（统一入口）”。
  - 约束：`project doctor --build --strict` 下，框架级未注册会报错并阻断。
- 项目级组件（非 `nsgablack.*`）可不注册。
  - 为什么：项目内快速试验允许先实现后整理，避免早期过度治理影响迭代速度。
  - 行为：doctor 会输出 `project-component-unregistered` 信息并列出未注册组件，不阻断。

### 示例/测试契约规范（必须遵守）

- 示例文件（`examples/`）和测试中的可复用组件（adapter/pipeline/bias/plugin）也必须显式声明契约字段：
  - `context_requires`
  - `context_provides`
  - `context_mutates`
  - `context_cache`
  - `context_notes`
- `bias` 类还应显式声明：
  - `requires_metrics`
  - `metrics_fallback`
  - `missing_metrics_policy`
- 原则：示例和测试是“标准用法展示”，不能用“省略契约”的写法误导后续开发。

### 贡献类型

我们欢迎以下类型的贡献：

- 🐛 Bug 修复
- ✨ 新功能开发
- 📚 文档改进
- 🧪 测试用例
- 🎨 代码重构
- ⚡ 性能优化
- 🔧 工具和脚本

## 开发指南

### 项目结构

```
nsgablack/
├── core/           # 核心模块
├── bias/           # 偏置系统
├── representation/ # 表示/算子/修复（RepresentationPipeline）
├── utils/          # 工具与插件（Plugin/Suite/并行/评估等）
├── catalog/        # 可发现性（search/show/list）
├── examples/       # 示例代码
├── tests/          # pytest 测试（权威回归口径）
├── docs/           # 文档
├── tools/          # 工程脚本（构建索引/生成 API 文档等）
# deprecated/       # 已清理（如需追溯请查看 git 历史）
```

### 运行测试

```bash
# 运行所有测试
pytest -q

# 运行一个最短示例（可手动挑选更多）
python examples/end_to_end_workflow_demo.py
```

### 添加新偏置

1. 在 `bias/algorithmic/` 或 `bias/domain/` 中创建新文件
2. 实现偏置类，继承基础接口
3. 在 `bias/__init__.py` 中注册
4. 添加示例和测试

## 许可证

提交代码即表示您同意将贡献以 MIT 许可证发布。
