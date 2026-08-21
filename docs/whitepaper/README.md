# Black Framework Stack 白皮书

本目录只保留正在维护的 V6 分卷草稿：

- [V6 目录与论证路线](v6/CONTENTS.md)
- [迁移与完成状态](v6/MIGRATION_STATUS.md)
- [卷一：基础与边界](v6/volume_01_foundations/README.md)
- [卷五：组合](v6/volume_05_composition/README.md)
- [卷七：项目实现](v6/volume_07_project_implementation/README.md)

V3、V4、V5、旧合订稿、旧 manifest 和旧生成器已经删除。它们描述过多轮已被源码替代的边界，继续留在现行文档树会制造第二套权威；如需考古，请查看 Git 历史。

## 写作规则

- 只以当前三仓源码、测试、AGENTS 和正式 Scaffold 为事实依据。
- `blackbase` 只描述共享 substrate 与公共协议。
- `nsgablack` 只描述优化/搜索语义和唯一 Solver 控制面。
- `mlblack` 描述 ML 语义扩展，不虚构第二套 Trainer 循环或 Adapter 层。
- 愿景、建议和已实现能力必须明确区分。
- 示例只引用标准 Project / Case / Scaffold，不引用私有脚本和兼容入口。
- 章节在进入 V6 前必须重新核对源码；不能把旧稿机械迁移成新版本。

V6 尚未完成时，不生成“正式合订版”，避免不完整草稿被误认为发布文档。
