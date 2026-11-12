# 框架助手训练与评测语料

这是一套**离线、可追溯的种子语料工具**，用于开始训练与评测专门理解
blackbase + nsgablack + mlblack 的助手。它不调用 DeepSeek 或任何其他模型，不读取
服务端请求账本，不上传用户聊天，不训练模型，也不运行 Case。

首轮种子共 20 题：训练 12、验证 3、旧 test 分集 5。它们是按当前源码与契约编写的
`authored_fixture`，不是从真实用户聊天导出的记录。来源状态统一为
`agent_source_checked`；尚未经过独立人审或这些题对应的运行验收。这个数量适合检查
数据流程和建立评测起点，不足以据此声称微调能产生生产级收益。

## 1. 语料学习什么

训练集关注整体职责、Unit 按需建立与复用、GA 最终成员精英池、MOEA/D 投影任务与
VNS、Bias 的软评分和原始硬约束、ctx 与 Pool、Plugin 生命周期、修复和接纳对齐、
ML Codec 与搜索 Unit、多轮用户决定修订，以及合法的在线装配编辑和缺少问题公式时
的澄清行为。

验证集关注动态步骤预算、错误证据解读，以及自然语言问题公式的完整交付。

旧 test 分集关注未进入首轮训练集的组合难点：BO 模型/观测/采集的职责判断、每成员 sigma 与局部索引、
递归投影视图身份、跨 Case 资源与引用 scope、durable evidence 恢复。训练和测试可以
共享必要的框架事实；不共享同一 `family` 的题目及答案。这里隔离的是任务族，不是
要求测试时把框架知识也隐藏起来。

这五题现已用于首轮微调失败分析，因此已成为**开发诊断题**，不再是未见验收或封存测试。
原 cases.json 的 split、旧导出和旧实验保持原样，保留历史可追溯性；文件仍叫 test.jsonl
不表示它重新获得独立测试资格。新训练不会把这五条问答或参考答案拼入训练输入。
新的验收应另写并记录模型、提示和数据冻结时间；本轮补充数据也不声称严格盲测。

每题在 `cases.json` 中显式记录：

- `id`、`family`、`split`：稳定题目身份、任务族与用途。
- `instruction`：自然用户请求；可附真实协议形状的设计笔记和短历史。
- `answer`、可选 `answer_action`：参考说明，以及种子或表达式草案的确定性构造。
- `rubric`：预期交付类型、需要独立判断的语义要点和不得作出的推断。
- `source_checks`：人工可复核的源码/文档路径与唯一锚点。

只判断命中几个关键词不能证明语义正确。本模块**没有关键词语义打分器**，也不把参考
答案经 JSON 校验通过称为模型答对。

## 2. 导出

在当前 nsgablack 源码工作区及已安装该版本的环境中执行：

```powershell
python -m nsgablack.catalog.assistant_dataset export .pytest_cache/assistant-corpus-20261024
python -m nsgablack.catalog.assistant_dataset validate .pytest_cache/assistant-corpus-20261024
```

输出目录必须不存在或为空；工具不会覆盖已有数据版本。

来源校验需要同版本的 AGENTS、源码和架构文档。仅安装普通 wheel、没有这些源码材料
时，导出或加载将明确拒绝，不能把缺失资料默认为已核对。模型训练只读取已经导出的
标准 messages JSONL，不依赖本模块或 nsgablack；独立评测与来源复核才需要这份源码。

输出包含四个文件：`train.jsonl`、`validation.jsonl`、`test.jsonl`、`metadata.json`。

三个 JSONL 都采用 Hugging Face conversational 形式，每行只有 `messages`：

```json
{"messages":[{"role":"system","content":"当前内置系统提示与引导总纲"},{"role":"user","content":"真实生产 packet 的 JSON 字符串"},{"role":"assistant","content":"合规六字段或含 design_notes 的 JSON 字符串"}]}
```

这里展示的是结构说明，实际导出的内容不会替换成上述占位文本。

`system` 和 `user` 通过生产代码的 `build_assistant_packet()` 与
`assistant_messages()` 生成，与实际助手保持相同的 prompt、在线能力表、装配定义、
引导上下文和有界源码检索。导出过程不通过 AssistantManager.submit，不预留模型请求。

`assistant` 是按真实 `validate_draft()` 校验过的参考 envelope；其通过只表示字段、
参数、证据 ID 和交付形状合法，返回状态仍为 `not_run`。

## 3. 参考答案与输入必须分开

`metadata.json` 保存每例的 rubric、来源锚点与摘要、文件 hash、题目行号、消息/packet/
参考答案摘要、当前 prompt 和 guide 版本，以及分集声明。

`rubric`、题目 split、参考答案和预期装配不进入 user packet。模型推理时只传
`record["packet"]`，或 `record["messages"][:2]`；不能把整个 record 当成请求。

```python
from nsgablack.catalog.assistant_dataset import load_exported_records

records = load_exported_records(".pytest_cache/assistant-corpus-20261024", split="test")
for record in records:
    packet = record["packet"]
    # generator.generate(packet) 是单独的推理操作；本模块不会自动调用。
    reference = record["reference_answer"]
    rubric = record["rubric"]
```

`load_exported_records()` 先校验整个导出包，再返回指定 split。
`test.jsonl` 的 assistant 列是供离线评测与人审使用的参考答案；它存在于磁盘并不代表
权限隔离的保险箱。训练入口必须**只选 train.jsonl**，验证时可选 validation.jsonl；
不能把目录中的所有 JSONL 直接拼起来训练。若测试题已用于反复调 prompt 或训练，应
升格为开发集并另外设计新的测试任务族，不能继续称其为未见测试。

## 4. 来源与漂移

来源固定到 nsgablack 仓库内的允许文本文件，记录完整文件 SHA-256；题目锚点记录
精确行号和八行上下文。检索证据也固定到它读取的文件摘要。导出包含语料工具、种子、
生产 packet/prompt/guide/装配/检索模块的版本来源。

`validate` 会检查：

1. JSON 唯一键和有限值、消息角色、真实助手 envelope 合法性。
2. 题目 ID、实际输入和消息重复；同一 family 不能跨 split。
3. JSONL、metadata、消息和参考答案摘要与行号一致。
4. 当前文件与导出时来源摘要一致，锚点仍唯一且上下文没有漂移。
5. 参考答案、rubric 没有混入模型 packet；元数据没有把未做的人审/运行写成完成。

摘要保证内容关联和漂移可发现，**不是作者签名或语义正确性的密码学证明**。任务族名称
由作者维护，机器不能可靠识别两个不同名称其实是同一语义任务；扩充时仍须独立审查
近似重复、语义泄漏和答案事实。

只要相关源码、guide、prompt 或语料发生变化，旧包将被拒绝作为“当前版本”加载。
保留旧文件用于历史对照，重新核对并导出新目录；不能只改元数据 hash 把旧答案冒充新版本。

## 5. 长上下文与显存

本 profile 是 `workbench_conversation`，保留完整生产输入，不把它静默改成短问答。
当前每例 user packet 约三万多字符，还要加系统提示、答案和具体分词器的会话模板。
`metadata.json` 记录每条消息的字符数和 UTF-8 字节数；`token_count` 与 `tokenizer`
明确为 null，因为本工具不加载分词器，不能用字符数冒充真实 token 数。

训练前必须使用实际 tokenizer 和 chat template 计算总长度，并检查助手答案和结束符
是否完整保留。不能把 max_length 设成 4096 后静默截断：那很可能只留下系统提示和部分
能力表，丢掉请求甚至整个答案。应先增加合理的序列长度、降低 batch、使用合适设备，
或另行设计并独立评测短的 cognition profile。后者是不同训练分布，不能直接宣称等同于
当前完整 packet 模型。8GB 本机显存是否可训练需由正式 ML preflight 和实际试验判断。

## 6. API 与后续扩充

公开函数：

```python
load_cases() -> tuple[dict, ...]
build_record(case) -> dict
export_dataset(output_dir, *, cases=None) -> dict
validate_dataset(output_dir) -> dict
load_exported_records(output_dir, *, split="test") -> tuple[dict, ...]
```

`build_record()` 返回 `id/family/split/profile/messages/packet/reference_answer/rubric/provenance`。
metadata 的 `cases` 项另含 `line`、三个内容摘要、消息长度和未计算的 tokenizer 信息。
`validate_dataset()` 只报告 protocol、source_integrity、family_separation；semantic 保持
`pending_independent_review`，model_execution/training 保持 `not_run`。

扩充建议按真实协作难度补题：多轮撤销与保留决定、错装配后依据结构诊断修正、合法
边界下的完整 Project、修复与部分接纳对 Unit 字段的影响、错误的源资料和过期 API 的
识别。每题先核对实际源码，标明静态或运行依据，再加入对应任务族；不要把未经核对
的模型自答大规模灌成正确答案。

实际微调、模型/优化器、LoRA 权重和推理产物由 mlblack 管理；共享 Project、资源授权
和 Artifact 协议由 blackbase 管理。本模块只拥有框架助手的领域语料与导出边界。

## 7. 首轮之后的短认知补充数据

`cognition_practice.json` 是独立的新数据文件，配套模块为 `assistant_practice.py`。
它不修改首轮 cases.json 或旧实验。新数据 56 题：**48 条训练、8 条验证，没有 test 分集**。
其中 17 条检查错误方案、16 条推演具体流程、13 条直接解释、10 条回应用户纠正。
“反例”指用户提出错误做法，由助手给出正确纠正；不会把错误助手答案标成正向训练目标。

训练题覆盖候选稳定身份与精确版本、视图父子拓扑与非级联删除、投影只应用一次、
同/跨 Case 和 L0 授权、持久恢复的阶段分支、BO 的软评分与采样决策、观测与活动成员、
成员字段局部映射，以及修复、提交和编排边界。题目包含数值相等但不同路径、同名视图
重建、具体行映射、已有决策却目标无效等不同场景，避免只把同一句问题机械改写。
验证题组合这些边界，单独 family，不加入训练；共享必要概念不意味着测试模型拥有了
独立研究证明。

恢复样本尤其不使用“invalid 一律 abandoned”的简化：

- reserved 阶段 Event 暂不可读：deferred；该阶段 Event 校验无效：可归档 abandoned。
- Event 已确认为 event_ready，但没有 durable 决策：以 decision_not_durable 归档。
- 已有 durable intent 的 decision_ready：可完整验证则幂等补结算；不可读或目标语义
  无效时保留 deferred，不能抹掉已有决定再求值。

这些结论按当前源码和现有恢复行为测试静态核对。source_checks 中引用测试函数是
定位证据，**不是声称本次已运行全部运行时测试**。所有新样本仍为 agent_source_checked、
independent_review=pending、human_review=not_done；数据结构检查不等于语义人审。

```powershell
python -m nsgablack.catalog.assistant_practice export .pytest_cache/assistant-practice-20261025
python -m nsgablack.catalog.assistant_practice validate .pytest_cache/assistant-practice-20261025
```

默认输出：

- train.jsonl、validation.jsonl：每行 `{id, messages}`，短 system/user/assistant 会话。
- grounding.jsonl：每行 `{sample_id, split, context, source_refs}`，供明确启用检索的训练或
  评测按 `(split, id)` 严格绑定；不会改写 plain 消息。
- metadata.json：原始问题、rubric、样本来源、行号、消息摘要、检索摘要与待审核状态。
- manifest.json：文件和来源摘要、48/8 计数、旧五题开发诊断状态及本轮尚未执行训练的声明。

grounding 使用真实 `build_framework_facts(question)`，输入只来自原始用户问题；不拿
rubric、参考答案或 source_checks 反选事实。它保存实际检索条目 ID、源文件摘要、行号
和精确摘录。训练入口显式选择 plain 或加入该 context，并为派生训练文件记录摘要；
模型评测同样可做无事实/有事实对照。需要纯离线 plain 包时传 `--no-grounding`，两种
模式都不会调用模型、GPU 或服务器。

原始问题与目标答复保持短而完整，不自动截断。真实 token 数由训练 tokenizer 计算；
即使加了短事实，仍要先执行 ML preflight 检查长度、答案标签与资源条件。不能把短认知
效果当成完整实验台 JSON 协议或自由代码装配已经可用。
