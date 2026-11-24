# 用 Skill 和 MCP 继续框架工作

Skill 提供职责、工作方式与查证顺序；MCP 提供当前框架和工程的真实工具。模型由宿主负责，MCP 不再调用另一个 AI。共同基础仍来自 `catalog/skills/framework-experiment-guide/FOUNDATIONS.md`，不另复制一份框架语义。

## Codex 的日常路径与验收

日常使用是在安装了两份框架Skill、已注册`black-framework`的Codex新会话里，打开你的Project，直接描述算法改动，例如“给种群成员增加年龄，新成员为0，幸存成员加1，再调整生存选择”。AI先读取框架基础和保存的Project状态，再查实际接口，修改组件，通过宿主终端或明确绑定的验证器测试，依据同一轮错误继续修复。无需另配OpenAI API key；Codex登录和API服务配置是两个独立入口。

`framework_context.framework_source` 给出实际MCP/API源码根、代表性文件SHA和归属身份。同版本号不代表同一工作树；本机的Desktop仓库和Codex工作树确实存在源码差异。应核对Project实际运行所导入的框架，不把A目录的查询结果当成B目录的运行证据。指纹仅覆盖列出的代表文件，不宣称锁定整棵源码树。`versions`来自安装发行版元数据，`source_package_version`来自实际源码的pyproject，二者不符会明确标记；本机隔离导入曾读到0.3.19元数据而实际源码为0.4.1，不能按旧元数据猜接口。可在MCP启动命令增加`--expected-framework-root C:/path/nsgablack`，加载了其他目录就拒绝启动。

本机接入排查发现：全局`codex`是0.147.0，服务明确拒绝它使用配置的`gpt-6-astra`；当前桌面应用自带0.171.0-alpha.13可用。验证直接使用桌面配套客户端，不替换模型、不覆盖全局安装。CLI首次没有继承Windows已有代理，发生连接超时；验收进程显式沿用用户已有网络配置后连接成功，没有修改系统代理。最小化启动配置曾丢弃既有Project信任并阻断MCP调用；最终保留用户配置，仅本次授权已指定的框架工具，同时禁用其他MCP服务。不要为解决接线问题给全局终端或全部MCP无限权限。

原生工具现在声明只读/非破坏/封闭范围提示；绑定真实代码验证器的`check_project_edit`明确不是只读工具。提示不能代替实际授权。全局注册仍默认静态检查，开发验收才为当前进程显式绑定固定验证器。AGENTS较大时，CLI会按`project_doc_max_bytes`截断；验收临时使用98304字节预算，保留当前约67KB的职责与边界说明，不修改全局值。

可重复的开发验收入口（必须选择当前可用的Codex可执行文件，输出目录必须全新）：

```powershell
python -I -m nsgablack.catalog.assistant_codex_acceptance --run age_population_unit --output ".pytest_cache/codex-acceptance/age-001" --timeout-seconds 420 --existing-windows-proxy
```

默认优先使用当前桌面应用配套Codex客户端，模型跟随用户Codex配置；仍可用`--codex`和`--model`明确指定。本验收入口要求已登录ChatGPT且使用默认OpenAI提供方，未满足就停止，不自动改用API key。`--existing-windows-proxy`只适用于Windows已经启用的代理；正常继承代理环境变量时省略。其他固定任务是`center_reflection_expansion`和`archive_maximin_survivor`；不加`--run`只列任务，不启动模型。每个任务从已有正式Project复制隔离副本，模型通过原生MCP调用原验证器，自己提交和修复源码，最后将同一份通过源码写入该副本。宿主不补算法实现，也不修改数学期望；420秒时限和45次工具上限不代表无限重试。

实际Project放在独立TEMP目录，缓存目录只保存宿主日志。Windows的隔离账户会成为新文件Owner，只有`OWNER RIGHTS`的模板可能使原用户无法回读；初始化副本时仅对该新Project明确保留发起用户的读写权限，不向Everyone授权，也不改变源仓库权限。CodeX结束后，宿主自动重新启动原生MCP、重新打开Project读取目标文件，将回读摘要、实际文件SHA和最后一次通过收据绑定。任一项不一致或无法读取都不能交付为通过。源码文件和完整Project实际位置记录在报告里。

输出保留事件、工具结果、最终回答和报告；`client_completed`只说明客户端结束，组件交付由`review.json`自动核对最后一次`edit_result`、实际文件字节、验证器身份和MCP回读。`--resume-thread`可在新输出目录续验原会话，保留原失败，不能把环境修复后的续验改称首次成功。这里复用此前冻结的数学任务，属于Codex入口的真实开发验收，不改写此前DeepSeek成绩，也不宣称模型已永久内化框架。日常新算法由Codex沿用原生编辑、终端和框架工具开发；这个固定任务验收器用于重复检查接入路径。

2026-11-24真实Codex验收：中心反射change、参考档案maximin选择、成员年龄Unit三类组件均通过正式验证和落盘/回读核对。年龄任务先前的缓存写入失败原样保留，后续仍使用原会话和原样源码；档案与反射文件的权限交接也由各自原Codex会话完成。三个数学实现都在首次源码提交时通过，因此本轮不声称验证了数学错误后的自主修复。最终13项针对性回归通过，过程中另有重叠的元数据/交付复查，不累加。完整记录和三份原样源码见[验收总表](evidence/codex-mcp-20261124/summary.json)。

全局注册已限定Python隔离导入`-I`和预期源码根，避免从其他聊天工作目录加载同名包；只读工具采用`default_tools_approval_mode="writes"`，真实写/执行工具仍需相应授权。没有给全局终端关闭sandbox，也没有开启默认代码执行验证器。从fb38工作树启动的新Codex会话已用这份全局注册真实取得基础、Project保存状态与schema，同时明确报告实际源码仍绑定Desktop仓库；这不等于fb38不同源码已通过算法验收。`-I`要求框架装在该解释器或虚拟环境内；仅依赖user-site或PYTHONPATH的安装应先选择正确解释器。

### 数学错误后的同会话自主修复

2026-11-24另行完成两项真实修复验收，记录在[数学修复总表](evidence/codex-math-repair-20261124/summary.json)。这是**明确注入故障后的修复实验**，不是模型自发写错，也不改写上文三项首次提交通过的结果。

- 中心反射算子：现有实现错误地把被反射父点也计入中心，实际断言得到`[1, -2]`而期望`[3, -4]`。同一Codex读取真实错误后，自行修正中心计算，通过20项行为检查。
- 档案maximin选择：每选出一个成员后，距离递推错误地保留较大距离。另一项独立任务中的Codex先原样收到`greedy recurrence, feasibility or stable occurrence ordering differs`，再自行修正递推，通过30项行为检查。每项任务从失败到交付均只有原来的一个Codex会话，没有其他AI补代码。

两项都通过正式Case builder、L0 grant和`Solver.run`：各提交2步、评估7次，批次为`[4, 3]`，保留4个成员，原始反馈与Problem一致。宿主只预先注入单表达式故障，没有提供故障位置、修复建议或正确实现；Codex自行提交修正、核对`edit_result`并写入Project。宿主随后用新的原生stdio MCP连接回读，确认实际文件SHA、最后通过源码SHA、执行源码SHA完全一致。两项的模型配置及本地会话记录均为`gpt-6-astra`，这不是服务端模型身份的独立认证。

开始前冻结了原来三个验收模块的完整文件哈希、数学摘要与`validation_identity`；结束后逐项相同。数学摘要为`aa1a36ae499053bd18ef9c22bbf77a8947fa0f5048279171cb344959a08763df`。首次源码检查必须真实执行同一故障种子并在行为断言失败；只有宿主预检失败、静态拒绝、导入失败、没有落盘或回读不一致，都不能记为数学修复通过。新增证据核对器另有针对性回归，结果见总表。

复跑时先用`catalog.assistant_codex_math_repair.prepare_seed`生成新的故障目录，再用`preflight_seed`确认它能触发**原有**数学断言；不能在预检未检出时仍宣称修复成功。之后在全新输出目录运行：

```powershell
python -I -m nsgablack.catalog.assistant_codex_acceptance --run center_reflection_expansion --seed-source "你的故障目录/seed.py" --output "你的新输出目录" --timeout-seconds 420 --existing-windows-proxy
```

结束后由`catalog.assistant_codex_math_repair.review_repair(输出目录, 故障目录)`核对失败、修复、交付与固定标准。档案任务使用`archive_maximin_survivor`。每项实验使用新会话以避免带入先前正确答案；任务内部不换会话、不换模型、不委托AI。故障生成器依赖此次保留的历史源码及其精确哈希，属于源码仓库中的开发验收工具，不是普通安装包必备能力。

**本轮还发现一处测试覆盖盲区**：另一份档案故障仅把初始参考距离从`min`改成`max`，居然通过原有30项检查和正式Case。该样本与原始收据保存在总表的`coverage_gap`中，没有计为修复成功。本轮没有修改标准来补测，而是保留问题，另选会被既有断言检出的递推故障完成实验。因此，两项结果证明了这两种错误的同会话修复闭环，不能证明数学验收完备，也不能证明AI已永久内化框架。

本轮实际接入和验收的源码根是`C:/Users/hp/Desktop/nsgablack`；隔离Project路径见各报告。`fb38`工作树的不同源码没有因此获得通过证明。没有部署服务器、修改线上数据或使用OpenAI API key。

### 距离盲区的增强验收与原会话续验

上一节的已知漏检现已补测，旧记录不改写。新增`archive-distance-v2`：保留原30项检查与正式Case，追加8项最近／最远参考距离会选出不同成员的断言，同时覆盖候选顺序、参考顺序、选1或2个成员。新增数据只存在于宿主验证器，不放进模型提示或Skill。原验收模块不改动，新标准有独立数学摘要与`validation_identity`，在模型运行前冻结。

2026-11-24已用**原来那份漏检源码的相同字节**完成真实续验：续接上一轮档案任务的同一个Codex线程，先原样执行收到`nearest-reference distance ranking differs`，再由它自行把初始参考距离计算由`max`修正为`min`。随后38项行为检查、正式Case、文件落盘与原生MCP回读均通过。宿主没有写修复代码或提供正确实现。旧的67份验收文件逐字节保持一致；新记录另存[增强验收总表](evidence/codex-distance-v2-20261124/summary.json)。本轮针对性回归结果见该总表，不与上轮测试数相加。

开发验收入口现在默认`--validation-profile current`：档案任务采用增强标准，另外两个任务保留其原标准。只有明确重放旧标准时才传`--validation-profile baseline`；旧通过不自动转换成新标准通过。也可显式传`--validation-profile archive-distance-v2`。复跑相同错误用`prepare_distance_seed`生成独立目录；若要求续接某一原会话，在种子清单记录`expected_thread_id`并通过`--resume-thread`续接，核对器会拒绝换线程或把宿主预检算作模型失败。

本轮运行期间框架源码发生变化，原Codex会话另收到一次`ai_framework_mismatch`；它自行刷新`framework_context`并重新`open_project`后继续，未绕过来源验证。这次工具拒绝与数学断言失败分别记录。回归也有一次同类版本变化失败，原输出保留，稳定后最终19项通过；不把失败静默改成成功，也不累加多轮重叠测试数。

## 让AI开场就有框架基础

“不用重新介绍框架”和“模型权重中已经学会框架”是两件事。当前`FOUNDATIONS.md`是核心职责、典型组合和不变量的唯一共同说明；网页入口已将正文放进系统提示。本轮让原生Codex**验收驱动**也在启动模型前复用`framework_system_prompt`提供同一份正文，并记录版本、SHA和启动前加载标记。这改变模型的输入，不是训练模型；不能从一次续验推断所有新会话都理解了全部框架。

基础说明约6.7KB，应该让AI先知道Pool、Unit、Adapter、Pipeline、Bias、Plugin和L0分别负责什么，再理解改change、增加成员字段、精修和嵌套的方向。AI不应每次先读整库才能讨论这些概念。当前工程状态、版本变化与精确API参数则继续通过现有Project工具和`framework_api`查证；这些事实会变化，不能当作永远正确的模型记忆。

此前只保证了验收驱动的基础加载；本节后续的“日常启动安装”已补齐本机普通Codex新会话。它复用全局`AGENTS.md`，没有修改Codex应用的系统提示或所有用户Project。不要把“已安装Skill”误认为其全部正文必定在启动时加载。官方[Skill说明](https://learn.chatgpt.com/docs/build-skills)说明了按需加载机制，[自定义指导](https://learn.chatgpt.com/docs/customization/overview)区分了AGENTS、Skill与MCP的用途。

如果目标进一步变成“不给上下文也掌握这套知识”，就涉及模型训练与训练样本覆盖，本轮没有这种操作，也没有证明当前Codex订阅模型能够由用户训练。可先积累经测试的完整开发任务：自然语言想法、正确装配、错误诊断、修复、运行证据，并用未参与编写的新任务检验泛化；不能用已见过的源码通过率代替这个判断。当前最直接的改进是稳定的公共语义、启动时提供核心知识、按版本查询接口和真实测试反馈，而不是再增加一个替AI写代码的模型。

### 日常启动安装与同步

框架已安装在当前Python环境时，可显式安装日常指导；不调用模型，不导入Case或创建Unit：

```powershell
python -I -m nsgablack.catalog.codex_bootstrap --install
python -I -m nsgablack.catalog.codex_bootstrap --check
```

默认不带`--install`只检查。安装器在当前`CODEX_HOME/AGENTS.md`维护一个有起止标记的基础段，正文原样来自共用`FOUNDATIONS.md`，保留段外个人指导；基础变动后`--check`会报告过期，由显式安装同步。源根、版本与SHA随段保存，安装副本不成为另一份语义权威。非空`AGENTS.override.md`会遮蔽全局AGENTS，安装器明确拒绝并保留原文件，不擅自覆盖个人override。

安装器把指导读取预算至少提高到98304字节，避免本仓较长AGENTS挤掉其他规则。若已有`black-framework`注册，则在其原有参数后加入宿主授权的`--include-current-project`，保留既有根目录、模型、权限、其他MCP和插件。它不会凭空注册一个不存在的MCP，也不开启默认代码执行验证器。每次实际变更前，在用户私有目录保留旧指导和配置；公开验收记录只存摘要和允许变更的字段，不复制私有配置。

MCP默认能识别宿主工作目录所属的最近标准Project，嵌套到Case子目录也可识别，标识为`current:.`。显式`--project-root`仍限定原授权范围；只有再提供`--include-current-project`才加入当前Project，不移除旧根、不把兄弟目录一并加入，也不让模型传路径扩展范围。发现和读取保持静态：读取保存的设计与装配状态，实际Case构建与执行仍需用户授权和正式入口。

本机已安装并核对配置差异：仅修改`project_doc_max_bytes`及`black-framework`的上述宿主参数。原全局AGENTS为空，现已保存共用基础段。新会话会按Codex的[原生AGENTS发现规则](https://learn.chatgpt.com/docs/agent-configuration/agents-md)加载；旧的长期运行MCP进程需重新连接才使用新参数和服务源码。

### 真正空白会话的新任务验证

2026-11-24另开真实Codex新会话，没有resume旧线程，任务提示没有重复注入基础正文。原生会话记录证明：第一条AI响应之前，Codex已收到与安装段一致的AGENTS知识；第一条响应直接判断仅替换change、无须新Unit或Problem，之后才查当前接口和工程状态。

新任务是“带死区的双亲对称混合”：坐标差严格大于1时双方各向对方移动四分之一，否则保持自身坐标，最后限幅。宿主事先冻结数学标准，未提供参考实现。该同一会话独立编写组件、查接口、测试和落盘；首次源码提交通过21项行为检查及正式Case（2次提交、批次`[4,3]`、7次评估、4个成员），通过源码、实际文件和MCP回读摘要一致。这是新任务首次通过，不能改称新增数学纠错证明；先前的自主纠错记录仍独立保留。

还通过本机实际注册命令从新Project的Case子目录启动原生stdio MCP，自动发现`current:.`并读到保存设计；默认验证器未启用。首轮探针暴露旧注册仅含显式examples根的问题，补充宿主opt-in后完成复验。范围与完整记录见[日常启动验收](evidence/codex-native-startup-20261124/summary.json)。本轮验证源码仍为Desktop仓库，不代表fb38不同源码通过；也不是所有新算法或任意未来会话都正确的证明。

最终28项针对性回归通过；中途两项测试夹具访问路径错误的原输出保留，修正夹具后重新验证，没有改数学标准。两个Catalog profile的公共静态审计无问题，但import与参数均标为未动态检查。额外根目录全仓Doctor扫描运行约8分钟后停止，未产生完整报告，不计为通过，也不把Catalog范围结果冒充全仓检查完成。

### 日常入口的后续边界修复

安装器现支持`32_768`、带正号或十六进制等合法TOML整数写法，完整替换预算值，避免局部文本替换把`32_768`误变成`98304768`。配置说明字符串里的同名示例不当作设置。MCP参数支持多行数组，保留原注释、参数及字符串中的`]`和`#`；已经登记的其他服务不会因名称碰巧相同而被添加框架参数。

显式启用当前Project时，若`current`名称已绑定另一目录，服务现在明确拒绝冲突，要求重命名显式根；不再把另一个工程悄悄当成当前工程。`--check`确认的是基础指导与受管配置是否同步，真实MCP连通和工程读取仍通过独立探针验收。

上轮Doctor未完成的原因也已定位：`results/`中9589份生成源码被当作生产源码重复检查，私有调用规则又先遍历缓存后过滤。生成结果排除统一归BlackBase的`doctor_scope`，nsgablack的遍历改为先剪枝；55个Project、90个Case的发现数量保持。该私有调用检查从诊断记录的约87.85秒降到本轮约2.02秒；全仓严格Doctor本轮34.95秒产出完整报告，但返回码2，仍有22个错误、11个警告，不能称为全仓通过。多数错误集中在`runtime_cost_probe`的脚手架缺失及`algorithm_transparency`的构建入口导入。本轮改动文件无对应诊断；完整清单、测试与范围见[后续修复记录](evidence/native-entry-hardening-20261124/summary.json)。此前未完成或通过的历史记录均不改写。

## OpenAI 模型接入

原生 MCP 不限定 DeepSeek 或 OpenAI；宿主取得工具 schema 后，把模型的正式函数调用交给 MCP，再把真实结果送回同一段对话即可。源码查询、检查和验证继续由原工具执行。网页 Project 协作复用 `ProjectAssistantRuntime` 的同一循环，通过 `provider="openai"` 选择官方 Responses API，不新增 AI 救场或第二套执行器。

可信宿主的私有配置示例（不要提交仓库，也不要把真实密钥贴进本指南）：

```json
{
  "provider": "openai",
  "api_key": "YOUR_PRIVATE_API_KEY",
  "model": "gpt-6.2-sol",
  "max_output_tokens": 4096,
  "timeout_seconds": 60,
  "reasoning_effort": "low"
}
```

沿用 `lab_service --role assistant --ai-config <私有配置路径> --state-path <原请求台账>`；OpenAI 使用默认 `--project-tool-protocol native`，显式传 json 会拒绝，不自动降级。模型名是宿主配置，示例不证明账号拥有相应模型权限。私有配置只接受所列字段，不允许改写 OpenAI endpoint，不读取其他提供商或 Codex 订阅凭据。

Responses 传输使用 `store=false`，在私有调用历史保留加密推理项、精确函数调用 ID 和工具结果；最终对用户仍交付原有 JSON 和版本绑定收据。现有请求次数、工具次数、源码与结果大小限制、静态检查、固定运行验证和最终交付门禁继续有效。一次传输只做一次 HTTP 调用；超时、地区拒绝、额度不足或限流均不自动重试或切到其他模型。无工具的最终阶段只请求 JSON，不再开放函数调用。工具保留原可选字段，由宿主按真实 schema 校验，不把所有可选参数强制改成必填。

连接外部模型前应独立检查当前网络可达性、服务区域及授权；不要把连接失败直接判定为密钥错误。

`tests/test_catalog_lab_openai_provider.py` 检验 Responses 协议，以及真实 stdio MCP + 原固定验证器的失败、修复和最终交付。模型响应是测试桩，代码机械重放此前已留存的两份模型源码；运行验证是真实的。这属于离线接入回归，不是新的 OpenAI 算法生成或同模型自主修复成功证明。真实模型闭环仍需在受支持的运行环境用明确调用预算验收。

本轮16项新测试、260项既有相关回归通过；Catalog范围Doctor为0错误、0警告、4条信息，未发现Case故未做Case构建。default与framework-core均能查询MCP入口。详见[本轮离线验收记录](evidence/openai-mcp-20261124.offline.json)。

## 启动

安装可选依赖：

```powershell
python -m pip install -e ".[framework-mcp]"
python -I -m nsgablack.catalog.mcp_server --project-root examples=C:/path/nsgablack/examples/cases
```

第二条命令是 stdio MCP 进程，标准输出属于协议，不是交互式终端。宿主配置决定可读范围；可重复传入 `--project-root 名称=目录`，目录是一个标准 Project 或其直接父目录。源码环境默认发现正式示例；普通安装包没有示例时仍可使用框架基础、Catalog和API，Project列表为空，待宿主指定工程根目录。

Codex 注册示例（建议使用该环境 Python 的绝对路径）：

```powershell
codex mcp add black-framework -- C:/path/python.exe -I -m nsgablack.catalog.mcp_server --project-root examples=C:/path/nsgablack/examples/cases
```

注册后在能加载该配置的新会话使用框架实验引导 Skill。已经打开的会话是否刷新工具列表取决于宿主；注册成功不等于当前聊天已热加载。MCP 连接本身也不会把全部资料自动装入模型上下文，Skill 和服务初始化说明会引导先调用 `framework_context`。

两份原生宿主 Skill 的维护版本在 `catalog/agent_skills/`，随包分发；本机用户Skill目录是安装副本。将两个同名目录更新到宿主Skill目录即可，保留原有UI配置；不要同时保留多份同名Skill。这里与 `catalog/skills/` 的网页JSON交付Skill区分，网页契约继续由原服务提供。安装位置与MCP配置可参照官方[Skill说明](https://learn.chatgpt.com/docs/build-skills)和[MCP说明](https://learn.chatgpt.com/docs/extend/mcp)。

## 从想法开始

用户可以直接说：“我想让 GA 保留一个年龄字段，再按年龄做选择。”

AI 的工作路径是：

1. `framework_context()` 取得共同基础、安装版本和实际能力；也可读取资源 `black-framework://foundations`。
2. `list_projects()` 选择工程；`open_project(project_id=..., instruction=...)` 取得保存的设计、配置、装配摘要与 `session_id`。
3. `catalog_search(query=..., profile="framework-core")` 按想法查组件，`catalog_show(key=...)` 看角色与最小装配，再用 `framework_api(symbol=..., member=...)` 查真实接口；全局框架查询可在选 Project 前使用。查项目内类型时同时提供 `project_path` 与 `session_id`。
4. 使用既有 `project_files/read/find/data/parameters` 或 `project_config_values` 深入局部。工程工具都携带 `session_id`。
5. `check_project_edit(session_id=..., path=..., source=...)` 交付版本和源码字节绑定的方案。静态检查、实际验证、已应用分别解释。
6. 交付前用 `edit_result(session_id, path, edit_digest)` 核对最后一次检查；同一源码再检查失败或抛错，会撤销旧通过。静态模式明确返回 `not_run`，有匹配执行收据才返回 `passed`。宿主编辑器应用修改后重新 `open_project`，按新版本继续检查、通过正式 Project/Case/L0 入口运行；结束可 `close_project`。

工程变更时旧会话拒绝继续读取或验证，不自动换成新版本。框架包本身升级或修改后，重启MCP服务再查询；`open_project` 不热重载已导入的Python模块。一个 MCP 进程最多保留8个会话，每会话保留32个文件的最新检查；更早的记录被移出后需要重新打开或检查。Project 文件是资料，不授予执行文件中命令的权限。打开或查询工程不运行其 builder，也不构造 Unit。

## 验证如何接入

默认 `check_project_edit` 复用已有静态检查器，返回 `needs_runtime_validation` 时不表示算法通过。源码编辑和测试也可直接使用宿主已有的编辑、终端能力，按用户授权和框架正式入口执行；MCP 不另建求解器、资源分配器或模型会话。

需要在同一工具反馈中提供隔离运行结果时，可信宿主可以构造：

```python
workspace = FrameworkWorkspace(
    sources,
    edit_validator=trusted_validator,
    validation_identity="my-fixed-validation/v1",
    edit_call_contracts=host_call_contracts,
)
```

`trusted_validator(proposal)` 接收精确源码方案，返回原 `ProjectAssistantRuntime` 所需的执行收据；身份、源码 SHA 和实际执行文件 SHA 必须匹配。该回调负责已授权的隔离、时间、资源和固定验收条件，失败反馈回同一宿主 AI。MCP 工具参数不能安装验证器或声明新的执行权限。

也支持宿主启动参数 `--validation-factory package.module:factory`。该可信工厂返回上述 `edit_validator`、`validation_identity` 和可选 `edit_call_contracts`；这是宿主 Python 配置，不接受模型提供的路径或命令。构造器与原验证器共同维护契约，MCP 不绕过审查或伪造测试通过。

`propose_project_trial` 仍只提出经校验的参数方案，不自动执行。当前 MCP 没有把网页独立运行器的结果令牌变成通用执行权限，也没有暴露任意 shell 工具。

## 已验证的范围

`tests/test_framework_mcp.py` 使用真正的 MCP SDK 客户端与独立 stdio 服务进程，验证工具发现、基础资源、Project状态、真实 schema 类型、越界拒绝和版本变化。带可信验证器的测试机械重放此前模型的两份原代码：第一份收到真实年龄字段长度错误，第二份原字节通过行为、正式 Case、部分接纳和回滚检查。

这是原生 MCP 接线与既有源码的回归，新增模型调用为0，不把它计为新模型盲测或改变此前2/3成绩。此前证据见 [AI协作验收](PROJECT_AI_COLLABORATION_ACCEPTANCE_CN.md)。

2026-11-24 本机验收：MCP最终6项测试通过；此前检查器与MCP联合48项通过，Project来源回归46通过、1项跳过（Windows符号链接权限），范围重叠不相加。真实注册命令通过legacy stdio握手，发现16个工具并读取GA/VNS工程保存状态；见[注册探针](evidence/framework-mcp-20261124.registered.json)与[实际验证收据](evidence/framework-mcp-20261124.validation.json)。干净目录构建wheel后，在源码树外导入，验证两份Skill、MCP入口与本指南随包存在，并能在没有示例Project时启动；见[安装包记录](evidence/framework-mcp-20261124.wheel.json)。

本机使用原生CLI只增加 `black-framework` 配置。第一次全量配置相等断言未通过，未保留前值，故不将原因断言为CLI迁移或其他软件；随后在同一进程做移除／重加对照，其他配置路径两次均相等，新条目也一致。没有尝试回滚无法归因的外部配置变化。两份已安装Skill与维护源逐字一致，按UTF-8运行Skill校验通过。服务注册不等于当前聊天已热加载，需在能读取新配置的会话中使用。
