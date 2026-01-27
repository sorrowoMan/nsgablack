# NSGABlack 模块结构规范（对齐当前架构）

这份文档原本用于“从旧结构收敛到新结构”的整理。当前仓库已经完成核心迁移：

- 旧 `solvers/` / experimental / deprecated/legacy 已从仓库清理（降低维护成本；如需追溯请查看 git 历史）
- 核心求解器与组合逻辑收敛到 `core/` + `core/adapters/`
- 代理/并行/实验口径/协同调度等能力：建议走 Plugin/Suite（能力层），不污染 solver 底座

如果你要理解“当前每个目录装什么”，直接看：
- `docs/architecture/module_structure.md`
- `docs/CORE_STABILITY.md`

如果你要理解“怎么拆算法”，看：
- `DECOMPOSITION_RULES.md`
- `docs/development/DECOMPOSITION_CHECKLIST.md`

---

## 设计约束（写代码时遵守）

1) 底座保持纯净：`core/` 不内置高级能力；能力通过 Adapter/Plugin/Bias/Representation/Suite 接入  
2) 策略逻辑优先 Adapter 化：`propose/update` 是最小闭环  
3) 约束优先分层：硬约束放 repair/可行解构造，软约束放 bias  
4) 必配组合必须提供 Suite：用 `utils/suites/attach_*` 固化事实标准，避免漏配  
5) 可发现性必须可追溯：加入 `catalog`（或 `catalog/entries.toml`）并声明 companions
