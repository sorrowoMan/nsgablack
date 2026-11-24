---
name: framework-experiment-guide
description: Co-design optimization problems and algorithms in the blackbase, nsgablack and mlblack stack; use actual contracts to choose reusable components or necessary extensions, preserve user decisions, and guide assembly and real validation.
---

# 框架实验引导

用户可以从问题、算法思想、算子、Unit 或编排任意入口开始。依据他的思路推进；尚未给出完整 Problem 不妨碍先讨论算法结构，执行前再补齐必要定义。每次只澄清影响下一步的关键问题。

## 先读取真实框架

原生 `black-framework` MCP 可用时，先调用 `framework_context` 取得同版本基础认识与实际能力；这不是模型永久记忆。算法讨论先用 `catalog_search` / `catalog_show` 按思想定位已有组件，再用 `framework_api` 查接口。涉及具体工程时用 `list_projects` 选取，再用 `open_project(project_id, instruction)` 读取已保存设计与装配状态；工程工具携带返回的 `session_id`。源码变动导致旧会话失效时重新打开，不拼接旧收据。缺少MCP时沿下述源码/CLI路径工作，不编造工具结果。

`framework_api` 返回当前签名、字段、静态值/返回契约；定向查询需要的成员，未知部分继续查证。`check_project_edit` 默认静态检查，有可信宿主验证器时才含实际 `validation`。收到失败后由当前AI修改自己的代码并重验，最终交付先用 `edit_result(session_id, path, edit_digest)` 核对当前文件最后一次检查，再绑定最新源码和通过收据；不能把静态通过或其他版本通过当作当前成功。源码编辑与正式运行复用宿主已有工具和Project/Case/L0，不再启动另一个AI。该流程不额外授权模型调用、执行或部署。

安装与验证器配置按当前仓库 `docs/user_guide/FRAMEWORK_MCP_CN.md`；MCP连接本身不保证宿主自动加载全部资料。

遵循当前仓库 AGENTS.md，框架分工与正式操作按 [ai-framework-operator](../ai-framework-operator/SKILL.md)。以当前源码、契约、Catalog 和正式示例作为依据；不要按算法名称猜接口。可用 `catalog/lab_framework.py` 的只读检索查找原文位置，源码依据不构成执行证明。

- 操作插槽、完整 change 与 Pool 选择：`docs/architecture/ADAPTER_OPERATION_BOUNDARIES_CN.md`、`ADAPTER_OPERATOR_BINDINGS_CN.md`。
- Unit 的新增成员字段与联动：`docs/architecture/UNIT_MEMBER_OPERATIONS_CN.md`；按需创建与持久 codec：`adapters/unit_backed.py`、`units/contracts.py`。
- 池交接、精修与编排：`docs/architecture/SOLUTION_POOL_CN.md`、`NATURAL_SEARCH_PLANS_CN.md`。
- Bias、Plugin、事务和资源边界：`docs/architecture/RUNTIME_CONTRACTS_CN.md` 及实际组件声明。

这些相对路径以实际框架仓库为根，优先使用当前工作区；只有安装包时通过MCP定向查证。ML 语义进入 mlblack，跨 Case 编排与 L0 进入 blackbase。


核对 `framework_context.framework_source` 的实际源码根与代表文件指纹，并与宿主实际运行导入位置一致；同版本号不等于同一工作树。MCP注册入口应使用隔离Python导入或稳定运行目录，避免被当前Project同名包遮蔽；加载了另一份框架时不能把查询和运行证据混用。

## 跟随想法作判断

先明确用户要改变的行为与输入输出，再查可复用结构。仅替换交叉通常复用种群 Unit；新增每成员状态时再检查 member_fields、成员变更维护和 codec 是否足够。不得因为算法新就默认新建 Unit。实际 Adapter 启用时才创建运行 Unit。

Pool 承载精确候选引用与区域；Unit 承载算法结构和关系；Adapter 决定搜索行为。软评分归 Bias，明确禁止候选或移动须在搜索/选择规则落实；日志和 checkpoint 复用 Plugin 生命周期。按用途判断，不把一切都塞进插件。

保留用户确认的设计、待决问题与尚未实现的部分。建议必须经用户确认才能写成已确认决定。关联实际 Project 的 DESIGN.md 或实验台工作区数据，不能只依赖短聊天。

## 使用与实现

网页协作时，使用调用方提供的版本化实验台 Skill。`assembly_catalog()` 是当前在线执行绑定范围；源 Catalog 更广，存在条目不代表网页可运行。网页响应遵守调用方 JSON 契约。

在本地直接协作时，按用户要求交付解释、设计文档或实现，不套用网页 JSON 输出格式。用户授权实现后，在所属仓库或正式 Project/Case 落最小改动，接原有运行入口；必要时实现算子、Unit、Adapter 或 Provider，再做与不变量对应的测试。状态扩展关注 repair、部分接纳、成员替换、回滚和恢复，不重造执行循环。

区分已装配、已开发、已执行及仅建议。这个 Skill 不增加权限；遵守本次任务的实际授权，也不自动调用付费模型或发布服务。
