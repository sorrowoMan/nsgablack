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
   git clone https://github.com/your-username/nsgablack.git
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
├── solvers/        # 求解器
├── bias/           # 偏置系统
├── utils/          # 工具函数
├── examples/       # 示例代码
└── test/           # 测试文件
```

### 运行测试

```bash
# 运行所有测试
python -m pytest test/

# 运行验证脚本
python examples/validation_smoke_suite.py
```

### 添加新偏置

1. 在 `bias/algorithmic/` 或 `bias/domain/` 中创建新文件
2. 实现偏置类，继承基础接口
3. 在 `bias/__init__.py` 中注册
4. 添加示例和测试

## 许可证

提交代码即表示您同意将贡献以 MIT 许可证发布。
