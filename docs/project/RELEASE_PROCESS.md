# RELEASE_PROCESS（版本语义与发布流程）

本文件描述 NSGABlack 的版本语义（SemVer）与推荐发布流程，目标是：
- 对外给出“哪些变更会破坏兼容”的预期
- 对内降低发布摩擦：tag 即可产出可安装包

## 1. 版本语义（SemVer）

版本号：`MAJOR.MINOR.PATCH`。

- `1.0.0` 及以后遵循标准 SemVer：破坏性变更进入 MAJOR，向后兼容能力进入
  MINOR，向后兼容修复进入 PATCH。
- `0.x` 是稳定版之前的演进期。MINOR 可以承载已经明确记录的破坏性迁移；必须在
  CHANGELOG 标为 `BREAKING`、提供迁移说明，并在不破坏新安全边界的前提下保留弃用
  兼容桥。PATCH 仍只允许向后兼容的修复、小优化、文档和测试增强。
- 涉及 authority、evidence 或事务完整性的旧行为若无法安全兼容，必须失败关闭，不能为
  维持旧行为恢复绕过路径；这种变化至少提升 `0.x` 的 MINOR，并写明例外原因。

## 2. 版本来源

构建与安装包版本由 `pyproject.toml` 的 `project.version` 明确声明；
`nsgablack/__init__.py` 的 `__version__` 是源码直接运行时的兼容镜像，两者必须同步。
已安装分发包可通过 `importlib.metadata.version("nsgablack")` 读取版本。

约定：
- 发布 tag：`vX.Y.Z`（例如 `v0.3.0`）
- tag、`project.version` 与 `nsgablack.__version__` 必须完全一致
- 发布前同时核对 BlackBase 与 MLBlack 的依赖版本区间

## 3. 发布前检查清单（Release Checklist）

1) 运行测试：`python -m pytest`
2) 同步更新 `project.version`、`nsgablack.__version__`，并确认 README 与发布 tag 一致
3) 更新 `CHANGELOG.md`：
   - 把 Unreleased 里的内容归档到本次版本号下
   - 标注 Breaking changes（如有）
4) 检查弃用：
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
