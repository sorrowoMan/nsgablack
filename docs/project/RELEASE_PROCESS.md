# RELEASE_PROCESS（版本语义与发布流程）

本文件描述 NSGABlack 的版本语义（SemVer）与推荐发布流程，目标是：
- 对外给出“哪些变更会破坏兼容”的预期
- 对内降低发布摩擦：tag 即可产出可安装包

## 1. 版本语义（SemVer）

版本号：`MAJOR.MINOR.PATCH`

- MAJOR：破坏性变更（Breaking）
  - 到期移除弃用 API
  - Stable API 参数/返回结构不兼容变更
  - 插件 hook 语义变更
- MINOR：向后兼容新增能力
  - 新增 wiring/plugin/adapter/representation
  - Provisional API 调整（尽量给弃用提示）
- PATCH：向后兼容的修复/小优化
  - bugfix、性能优化、文档修复、测试增强

## 2. 版本来源（setuptools_scm）

项目版本由 `setuptools_scm` 从 Git tag 推导（见 `pyproject.toml: dynamic = ["version"]`）。

约定：
- 发布 tag：`vX.Y.Z`（例如 `v0.3.0`）
- 不在代码里手写 `__version__`（由 `importlib.metadata.version("nsgablack")` 解析）

## 3. 发布前检查清单（Release Checklist）

1) 运行测试：`python -m pytest`
2) 更新 `CHANGELOG.md`：
   - 把 Unreleased 里的内容归档到本次版本号下
   - 标注 Breaking changes（如有）
3) 检查弃用：
   - 所有弃用必须包含 remove_in
   - Stable 文档与 catalog 指向新路径

## 4. 发布步骤（Git tag 驱动）

推荐流程（GitHub Actions 自动构建）：

1) 确保 main 分支通过 CI
2) 打 tag（本地）：
```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```
3) CI 构建产物：
   - sdist（源码包）
   - wheel（可安装包）
4) 产物会作为 Actions artifact（或 GitHub Release 附件）保存

如果未来要发布到 PyPI：
- 配置 `PYPI_API_TOKEN`（GitHub Secrets）
- 在 release workflow 中启用 `twine upload`

## 5. 变更记录（Changelog）

推荐使用 Keep a Changelog 的结构：
- Unreleased
- Added / Changed / Deprecated / Removed / Fixed / Security

文件：`CHANGELOG.md`

## 6. 迁移指南（Migration Guide）

当出现弃用/移除/破坏性变更时，建议按模板补一份“最小迁移说明”，避免用户靠猜。

- 模板：`docs/project/MIGRATION_GUIDE_TEMPLATE.md`
- 稳定入口清单：`docs/project/STABLE_API_SURFACE.md`
