# Catalog 独立只读部署

## 详细用法与变化用法

主干组件的用法区继续绑定同一完整主例和实质扩展：12项原先仅有主例的卡片补有搜索编排、偏好/观察、候选修复和成员状态三组指南。
变体说明具体文件、替换内容、运行入口和结果检查；临时Project副本的本地验证与发布镜像的固定独立收据分别记录。
Composite文档卡不再重复嵌入同一builder的Python片段，该源码仍在原Project的source_files摘要闭包内，不因文档分层丢失依据。
资料统计只在一次计算内复用共享指南的纯解析；各组件的缺项、记录和输出仍独立，不建立跨请求的陈旧缓存。

用法页保留全部关联组件：前五项直接显示，其余按数量展开。点击后可在当前页签返回原组件。
“教程中提到的用法”只从当前教程明确写出的 Markdown 文档链接，匹配索引中该目标教程的首个主来源；
共享 builder/report 续章不反向建立归属。入口只显示当前 profile、scope 与数据源实际收录的组件，
它是阅读导航，不声明替代等价、执行兼容或必选依赖，也不导入组件或创建 Unit。

`catalog_fixed_candidate` 是独立二维数值小 Project：默认候选 `[0.25, 0.75]`，原始目标为 `0.625`，
只提交一步并求值一次。发布时通过固定 CPU allowlist 在新副本运行，核对实际池反馈、Case 结果及 L0 授权后才生成收据；
它不与 ML 闭式拟合 Project 混用，不增加浏览器在线执行入口。

AI整理使用`catalog-tutorial-reviewed-zh-v11`：模型只生成详细tutorial，原八个短说明字段从该教程派生，避免重复输出摘要、猜关系键或混淆嵌套结构；两类内容一起保存在既有知识库JSON中。详细内容包括具体场景、准备、文件落点、完整代码、执行过程、结果检查和有代码的延拓，优先写一至两种有实际用途的变化。正文不再限制约700字，也不再禁止示例代码；代码仅展示，不在网页执行。旧八字段记录仍可在接口页查看，但不会冒充新版详细教程。每个教程及变体核对来源ID、Python语法、占位内容和运行声明后，再由另一次关闭推理模式的独立AI请求核对真实接线、消费者、阶段与变体；复核否决或资料不足的内容不发布，可以按具体问题修正一次。publisher写入独立`note.tutorial_review`，生成者不能自行提交此字段。同版人工教学说明可以作为正式Case接线和通用Project入口的来源；新变体的关键接口仍须有依据，不为复核重复展开整个框架内核。非完整响应只记录结束原因与计数，不保存模型原文或凭据。这些检查仍不能证明算法效果。

资料通过明确执行的隔离writer任务生成，模型与writer凭据不进入reader。`runtime.py curate` 要求 `--execute` 与明确的 `--keys`，同步和网页刷新不启动付费。任务仍提供至少12288输出token、120秒单请求等待，原私密配置文件保留。响应截断或格式/来源错误不作为成功记录；可以作一次有明确原因的格式修正，网络结果不明确时不自动重复付费请求。服务器整理任务已停止并取消timer开机启用，发布网页不会恢复它；入口保护的实际发布版本见 [部署记录](DEPLOYED_CN.md)。

`auto_curate.py`允许两种受核对的发布清单：三服务发布的`service.json`，或reader-only发布的`release-manifest.json`。后者必须与实际网页镜像中的源码摘要一致，才可使用该镜像整理；缺少清单或摘要不符仍拒绝。部署host launcher时使用本次发布的同版`auto_curate.py`，保留现有state、writer授权和模型配置，不能仅更新网页后声称自动整理仍有效。

Catalog 的组件浏览仍为只读。“装配实验台”按“定义问题／装配算法／运行结果”三步提供自然语言问题定义、手动自由装配与全程 AI 引导，经独立 worker 进行小预算运行；网页容器不直接执行算法。三种服务的授权分别配置，见下文。

本目录部署只读 Catalog 网页，并提供独立索引发布命令；网页不运行优化或训练任务。

## 实验台的独立运行服务

`?view=lab` 打开装配实验台。配方只是可编辑起点；手动选组件、参数、Pool 输入输出及 serial/multi/repeat 嵌套计划，保存为 `nsgablack.lab.assembly/v1`。本版在线绑定六族 NSGA-II、MOEA/D、VNS、SA、DE、PatternSearch，以及目录中声明的问题、管线、软偏好和 Pareto 档案；不表示全部 Catalog 组件均可自动装配，BO/CMA-ES/MAP-Elites 等尚未开放此绑定。未知参数、任意代码/import/命令/文件或服务地址拒绝。

自定义 `problem.expression` 声明 1～8 个具名连续变量、逐变量有限边界、1～2 个带 min/max 的目标、0～8 个带 relation/rhs/tolerance 的硬约束。公式解释器仅遍历允许的算术 AST，不执行 Python；`repr.problem_uniform` 与问题修复使用实际逐变量边界。最大化表达式保留原方向，算法评分使用 `-f`，页面结果另显示 `f`；边界修复不代替一般约束求解，违反量按原定义保留。整数、排列、文件／数据库、仿真器、训练模型及远程 API Problem 尚无在线绑定，AI 应澄清或指出正式 Project 扩展入口，不能伪装支持。

全程引导固定加载镜像中的 `catalog/skills/framework-experiment-guide/SKILL.md`，由 `catalog.lab_guide.read_guide()` 发布 id/version/sha256/stages；三个 UI 入口与 assistant capabilities 核对同一版本。该 Skill 是发布源文件，必须进入源码 manifest，不能来自浏览器路径或运行时下载。当前阶段、最近六条有限对话和已提交 worker 作业的白名单摘要通过 `guide_context` 传入，参与请求幂等摘要但不写入持久额度账本。历史与摘要仍是输入资料；不能覆盖系统规则或作为执行授权。结果解读须核对 `matches_current`，不把旧装配的结果当作当前证据。

框架资料从固定白名单的真实源码与契约按问题提取，附路径、行号和内容摘要；最多六条契约与六条组件、总量不超过 32 KiB。方向投影评分、最终成员与硬接纳的区别、成员操作索引与修复边界、计划提交计数使用相关的专门片段，不为此执行组件、复制一套注册表或建立第二个计划计数器。检索资料只支持解释，不扩大在线装配能力。运行前动态次数没有完整依据时只作有条件估计，运行后核对当前 trial 的 committed 步数。

手动文档与 AI 草案共用 `normalize_assembly` 和 Problem 校验器；源码预览、ZIP 与运行复用同一个正式脚手架导出实现，实际执行复用原有 Adapter/Unit/PoolTask/Router/事务/Project L0。AI 可交付完整草案、澄清问题或只读建议；草案先展示变更，必须显式 Apply，基线摘要变化则拒绝应用旧草案。只读建议无可应用定义；Apply 不自动执行，只有另行点击试跑才提交任务。组件浏览不会调用模型或启动运行。使用说明见 [Catalog 实验台](../../docs/architecture/CATALOG_LAB_CN.md)。

托管 reader 通过固定变量 `NSGABLACK_LAB_CLIENT_CONFIG=/run/secrets/lab-client.json` 接入试跑服务，通过独立的 `NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG=/run/secrets/lab-assistant-client.json` 接入 AI 草案服务。两个 JSON 各自仅有 `url` 与 `token`；目的地固定为内部服务的 HTTP 主机和端口，token 分别生成，不复用。reader 保留 SELECT 及既有 simon 鉴权，不获得 writer、模型配置、宿主工作区或 Docker socket。浏览器不能指定服务、配置路径或命令。

worker 在独立容器执行 `python -m nsgablack.catalog.lab_service --host 0.0.0.0 --port 8622 --config /run/secrets/lab-worker.json`，其私密 JSON 仅有同一 `token`。使用 UID 10001、只读根文件系统、256 MiB `/tmp`、1 CPU、768 MiB 内存、128 pids、cap-drop ALL 与 no-new-privileges。worker 只接专用 `--internal` 网络，不发布主机端口；网页额外连接该内部网络。不要给 worker 挂载 Catalog reader、writer、AI 配置或完整 automation 目录。

AI assistant 是第三个独立容器，执行 `python -m nsgablack.catalog.lab_service --role assistant --host 0.0.0.0 --port 8623 --config /run/secrets/lab-assistant-worker.json --ai-config /run/secrets/deepseek.json --state-path /run/assistant-state/reservations.json`。它仅持有 AI 私有 token、只读模型配置和专用额度目录写权限，不挂载数据库凭据、运行 worker 授权、宿主源码或 Docker socket。保留只读根文件系统和资源限制，端口只在内部服务网络可达；另需固定模型 HTTPS 出站。模型 key 不进入 reader、试跑 worker 或导出的 Project。缺少 assistant 配置时手动装配和试跑继续可用，缺少运行配置时托管 reader 仅预览/下载，不在网页进程回退执行。

AI 编辑按用户要求不设每日次数上限，后续发布不得擅自重新启用；这不代表模型供应商的余额或实际接口限制。`requests_per_utc_day/remaining/resets_at` 均为 null，`reserved_today` 仅统计请求，不阻断使用。请求在模型调用前原子写入持久去重记录；文件锁拒绝两个进程同时使用同一记录。同一请求重发或服务重启不重复调用，结果过期会明确报告。记录只存身份、摘要和时间，不存提示词、装配值、回复或 key；目录必须持久挂载，不得挂到 reader，升级不清空历史。现有单并发、至多两个未完成请求是处理队列机制，不是每日配额。原 DeepSeek 后端固定官方 HTTPS；新的兼容模型后端由服务端显式配置 HTTPS 或本机回环 HTTP，见[模型后端配置](ASSISTANT_MODEL_BACKENDS_CN.md)。两者均禁环境代理和跳转，一次调用最多 60 秒/4096 输出 tokens/256 KiB 响应，不自动重试。本段只描述交互编辑服务，后台 Catalog 资料整理另按其任务策略执行。

回复校验失败保留 `ai_draft_invalid/ai_base_mismatch` 等原有错误码；由本地校验产生的错误另带 `nsgablack.lab.assistant_diagnostics/v1` 诊断，只有固定枚举的 stage/path/reason。Manager 再核对允许列表，网页显示对应的固定中文说明。不得把未知字段名、异常原文、模型回复或凭据装入诊断；原始响应仍不持久化。诊断用于定位失败阶段，不能反推此前未记录的失败原因，也不触发自动重试。

先在相同固定源码镜像中执行 `python /opt/catalog/verify_lab.py --worker-only`，验证正式 Project 运行：原四种配方、GA→SA→GA、MOEA/D 方向精修、并行后局部搜索、嵌套方向视图，以及新增自定义 Problem，共九个场景。新场景使用最大化目标、不同变量边界和故意不可行的硬约束，独立重算 `raw_objectives/display_objectives/raw_violations`，防止把运行成功误记为问题可行。再对候选 reader 执行 `python /opt/catalog/verify_lab.py`，验证两个服务的只读 capabilities、固定 Skill 版本、双 profile 的三步页面与真实运行结果。该脚本不提交 AI 请求；页面预览拦截模型生成、AI 提交和 Unit 构造，读取真实 AI 能力与额度前后须保持预留不变。真实自然语言问题生成由单独的受控验收显式执行，保存结构校验、显式应用及运行证据。继续执行原有 source、UI、search、knowledge、examples、navigation 验收。

队列串行执行，最多三项未完成任务，每次 60 秒；运行器独立校验正式 L0、Case 身份、Artifact 发布记录和原始目标。刷新页面不重复提交，网络响应丢失时重试复用同一请求身份。记录暂存在 worker 内存，完成约一小时或超过 16 条会淘汰，重启后不可恢复；不能把它当成持久实验记录系统。下载 Project 和运行 JSON 保存结果。

reader、runner 与 assistant 各自固定并记录源码镜像，三个服务的 `assembly_catalog` 和所使用的公共运行契约必须一致；影响装配或运行协议的改动须同步升级 runner。仅修改 UI、AI 资料或提示词且不改变这些契约时，可保留已经验证的 runner。reader 与 assistant 的 Skill 元数据必须相同，先验候选，再切换原 reader；原 simon 鉴权和网关路径不需要改变。回退时只停本次服务并定向恢复相应客户端/网络，保留原 AI 整理状态和数据库；不要回滚任一 AI 用量预留账。

镜像包含当前 nsgablack／blackbase／mlblack 源码、公开文档和标准 examples 的源文件。它包含未提交的新 `.py/.toml`；manifest 的逐文件摘要比 Git HEAD 更准确地标识本次部署。

三仓均通过 `pip install --no-deps --no-build-isolation -e` 安装到镜像内源码，同时设置 `PYTHONPATH=/opt/src/nsgablack:/opt/src/blackbase/src:/opt/src`。editable 安装保留依赖及版本 metadata，避免物理安装的包子目录遮蔽已核验源码。网页、CLI 与独立验收脚本因此读取同一份 Catalog，包含 `default` 的完整 docs/examples 分片；镜像验收还必须逐项确认实际模块路径来自 `/opt/src`。

## 打包与构建

在本机执行：

```powershell
python deployment/catalog/package_context.py
```

结果在 `.pytest_cache/catalog-deploy/`：上传用 `.tar.gz` 和可单独查看的 manifest。默认从相邻 `blackbase/` 读取 `src/pyproject.toml/README.md`，可通过 `--blackbase` 显式指定；相邻 mlblack 源码通过 `--mlblack` 指定。

脚本采用目录和后缀白名单；排除 `.env*`、所有 `db.toml*`、密钥/证书、Git、venv、缓存、数据、结果、checkpoint、`.blackbase`、报告附件，以及安装会重建的 `*.egg-info`、`*.dist-info`、`.eggs` 元数据。`.case`、模板和当前 Catalog TOML 会保留。单文件上限 2 MiB、源码总量上限 64 MiB；越限明确失败，不默默塞入大对象。不会读取本机部署密钥。

在服务器专用新目录解包；先核对传输文件 SHA-256，再构建一个独立标签：

```bash
mkdir -p catalog-context
tar -xzf catalog-context-<stamp>-<digest>.tar.gz -C catalog-context
cd catalog-context
docker build -t nsgablack-catalog:<digest> .
```

`requirements-web.txt` 固定本机当前已验证的 Web 与基础数值依赖及其运行闭包，另固定独立构建工具 wheel 0.45.1；Python 3.12 Linux 的实际可安装性仍以本次 Docker 构建和 `pip check` 为准。没有 Ray、RAG、Torch、embedding 模型、编译工具链或本机环境副本。pip 禁用下载缓存。构建复用已经核对的基础镜像，记录 `docker image inspect python:3.12-slim` 的实际 ID；需要更新基础镜像时再显式拉取。

镜像内 manifest 位于 `/opt/catalog/release-manifest.json`，逐项记录源码的 `/opt/src/...` 路径；执行 `python /opt/catalog/verify_release.py --require-hosted` 核验文件摘要、实际模块来源、版本及中文查询。模块必须从这份源码树加载，即使 wheel 副本摘要相同也不能代替源码路径。`--manifest ... --context-root ...` 仅供源码已经从该 context 目录加载的本地验收；脚本不扫描任意宿主机目录。

## 独立运行与访问

默认界面为 `default/all`，只展示 framework Catalog，`source-mode=off`，不连接现有 DB。`NSGABLACK_CATALOG_HOSTED=1` 启用受限部署面，锁住来源及路径参数，并隐藏本地源码操作。容器内绑定 `0.0.0.0:8501`，主机只映射 `127.0.0.1:8615`。

以下资源和网络只属于这个新容器；创建前先核对名称没有被已有业务占用：

```bash
docker network create nsgablack-catalog-net
docker run -d --init --name nsgablack-catalog \
  --network nsgablack-catalog-net \
  --publish 127.0.0.1:8615:8501 \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=256m \
  --memory 1g --cpus 1 --pids-limit 128 \
  --security-opt no-new-privileges:true --cap-drop ALL \
  --restart unless-stopped \
  nsgablack-catalog:<digest>
```

镜像以 UID/GID 10001 运行，HOME 为 `/tmp/catalog`；只有临时目录可写。运行时无需挂载工作区、Docker socket、密钥、数据库目录或宿主机配置。

从自己的电脑开 SSH 隧道，私钥路径由操作者在本机指定，不放入打包目录：

```bash
ssh -N -L 8616:127.0.0.1:8615 <user>@<host>
```

随后打开 `http://127.0.0.1:8616`。不新增公网端口，不修改现有业务代理。

健康检查为 `/_stcore/health`。健康仅表示 Streamlit HTTP 可用；部署验收还要实际检索“贝叶斯引导／替换采集函数／种群扩展字段”，检查默认口径与边界说明，并验证 URL 不能切换到本机 Project/DB 路径。

标准 examples 只供 Catalog 导航和源代码检查。私有数据及模型权重不在发布闭包；ML 目录展示不表示可选 Torch/JAX/TensorFlow 等后端已经安装，跨框架示例仍须满足其运行依赖。

## 停止与回退

停止预览执行 `docker stop nsgablack-catalog`；恢复同一版本执行 `docker start nsgablack-catalog`。需要切换镜像时先记录当前镜像标签，再仅移除这个已停止的容器，用上述独立运行参数和目标标签重建。源码包、manifest 和 `verification.json` 保留在 `/opt/framework-catalog/releases/`；`current` 指向已验收的发布目录。不要清理共享服务器的其他容器、镜像或网络。

## 员工看板与数据库部署

以上是独立源码预览模式。当前员工看板部署和实际版本见 [DEPLOYED_CN.md](DEPLOYED_CN.md)。看板模式使用相同源码镜像，但从独立 MySQL 库读取已发布索引：

- 权威定义：nsgablack 原生目录，以及通过 `NSGABLACK_CATALOG_PROVIDERS=mlblack=mlblack.catalog.registry:get_catalog` 显式配置的 ML 公开目录。ML 组件保持自己的契约和用法，key 以 `mlblack.` 命名空间区分，metadata.catalog_framework 标明归属；本地不配置仍可独立使用 NSGA Catalog。
- 数据库不供手工维护第二份组件定义；所有来源联合后只同步一次。migration 10 保存语义 metadata，源码摘要 v3 将其纳入核对，旧 reader 只校验、不修改表。
- 物化：`python /opt/catalog/runtime.py sync`，通过 `NSGABLACK_CATALOG_WRITER_CONFIG` 指向服务器私有 JSON。只同步 default 全集一次，然后核对 default/framework-core 的 key 与完整语义摘要。
- 网页：`NSGABLACK_CATALOG_HOSTED_SOURCE=database`，`NSGABLACK_CATALOG_READER_CONFIG=/run/secrets/catalog-reader.json`。JSON 字段为 backend/mysql、host、port（整数）、database、user、password。配置文件只读挂载，凭据不进镜像、URL 或日志。读者只有该库 SELECT；同步账号权限仅限该库。
- `runtime.py serve` 设置数据库 `only` 与只读模式，缺少配置直接失败。浏览器参数不能改数据库、切换项目或退回源码。源码 registry 仍用于声明身份及版本核对。
- `STREAMLIT_SERVER_BASE_URL_PATH=apps/framework-catalog`；同前缀健康检查由 `runtime.py health` 完成。该检查不代表数据库查询或账号鉴权通过。

网页后台仅绑定宿主 `127.0.0.1:8619`。`gateway.conf` 的独立 Nginx 监听普通 `127.0.0.1:8080` 与可信 Catalog 专用 `127.0.0.1:8615`。普通工作台业务流量转 Dashboard 后台8089（容器内仍8080）；可信8615只提供Catalog，不额外开放普通工作台。每个 Catalog HTTP 请求和 WebSocket 握手调用既有 `/api/workspace/app-access`：普通鉴权使用8089，可信鉴权使用8086。普通客户端的 Tailscale 身份头不进入鉴权或工作台后台。应用条目使用 `allowed_users=["simon"]`、`requires_account=true`；角色管理员不能绕过账号名单。只转发鉴权必需 Cookie/可信身份头；Streamlit 只收到自己的 XSRF Cookie，不收到工作台 Cookie 或身份头。保留 CORS/XSRF。既有 WebSocket 的持续会话不会因后续退出登录即时断开。

左侧分类用于完整浏览，切换时清除旧搜索条件；结果中的分类建议保留当前关键词。字段筛选从对应分类的URL初始化，之后由界面状态维护，不能在重跑时反复覆盖用户操作。部署后执行 `verify_search_filters.py`，用真实reader核对双profile的全部分类计数及取消／清空、分类切换、搜索跳转、重置场景；网页验收不调用模型或构建Unit。

Tailscale Serve 在既有 8080 listener 追加精确路径，原根路径及其他监听保持原值。Serve 剥挂载前缀，目标 URL 也带同前缀：

```bash
tailscale serve --bg --http=8080 --set-path=/apps/framework-catalog/ \
  http://127.0.0.1:8615/apps/framework-catalog/
```

上线前在服务器运行 `python3 verify_gateway.py`（与 gateway.conf 同目录），使用隔离模拟账号验证两个入口、匿名、其他账号、鉴权故障、授权 HTTP/WS、身份头隔离、原工作台上传与跳转；它不创建生产账号。再验证用户实际使用的同源工作台入口、实际读者权限和数据库摘要。仅验证 Tailscale 地址不足以证明18080等SSH工作台入口可用。升级源码后必须重新同步索引；不创建自动同步定时任务。

部署前备份工作台动态应用清单、两个归属清单、边界检查器和 Serve 状态；按键合并，禁止整文件覆盖服务器配置。`frontdoor.py plan/apply/rollback` 是服务器root执行的受控端口切换工具，不在应用容器运行；它校验精确容器ID，保留原镜像与全部声明配置，在私有目录保存恢复状态并自动回退失败。它不能代替工作台真实登录后的页面验收。

生产 `.env` 应显式设 `TRS_DASHBOARD_PORT=127.0.0.1:8089`，未来发布克隆当前绑定；容器内8080与可信8086保持原值。只下线 Catalog 时禁用应用条目，保留前置网关运行。该网关同时承接普通工作台8080，直接停止它会中断整个普通入口。完整回退须恢复原容器端口并定向恢复 `.env` 的端口键，详见部署记录；数据库和凭据保留供对账，不删除业务数据。旧无鉴权预览容器不能通过保留的 Serve 路径重新暴露。


## AI 资料整理任务

镜像构建离线生成 `/opt/catalog/knowledge-sources.json` 与 `knowledge-packets.json`，只含白名单组件声明和源码证据。独立 `catalog_knowledge` 表由 writer 显式建表，reader 只读；生成资料不改变原 Catalog 源摘要。

组件示例另由 `build_examples.py` 在镜像构建时生成。先建立静态 `examples.json`，再由 `run_example_receipts.py` 运行固定白名单 Project（临时目录、合成数据、CPU、正式 L0），最后合并 `example-receipts.json`。成功收据必须匹配当前发布摘要与命令，缺失或失配不能标记“已运行”。源码清单不包含这些派生文件，避免摘要循环；它包含构建器、执行器、示例清单与工程源文件。

网页只读 `NSGABLACK_CATALOG_EXAMPLES_INDEX=/opt/catalog/examples.json`，不能从查询参数指定文件，也不提供运行代码按钮。`verify_examples.py` 用真实 reader 核对源摘要、示例身份和双 profile 的搜索／详情展示，并禁止浏览过程调用模型或构造 Unit。未运行组件保留待验证或装配片段状态，不用四个代表性示例代替全部组件验收。

模型配置使用服务器 `/opt/framework-catalog/secrets/deepseek.json` 私密 JSON，字段仅为 api_key、model、max_output_tokens、timeout_seconds。文件权限0600、root所有，不进入构建目录。官方HTTPS端点固定，拒绝跳转；异常只记录类别。网页容器不挂载此文件。任务通过标准库HTTP调用，无需额外模型服务或GPU。

生成任务使用核对后的固定镜像，挂载 writer JSON 和 deepseek JSON，并设置 `NSGABLACK_CATALOG_WRITER_CONFIG=/run/secrets/catalog-writer.json`；挂载均只读。以独立root短任务读取私密配置，保留只读根文件系统、临时目录、原数据库网络和资源限制。包含新执行保护的镜像发布后，先明确组件范围与可接受开销，再使用显式命令，例如：

```bash
python /opt/catalog/runtime.py curate --execute --keys adapter.vns --limit 1 --workers 1
```

`--execute` 和非空 `--keys` 均为必需。精确组件/证据摘要/模型/提示版本命中时不请求模型；单项仍可能包含生成、独立复审、纠正和有限网络重试，不能把 `--limit 1` 理解为一次 HTTP 或金额上限。失败逐项报告，token用量不声称涵盖服务端全部计费。

`runtime.py sync` 只发布并核对事实。旧 `NSGABLACK_CATALOG_CURATE_ON_SYNC=1` 不再触发付费，报告会提示显式执行入口；部署、索引过期或网页浏览都不能代替本次执行授权。

网页通过 `NSGABLACK_CATALOG_KNOWLEDGE_ENABLED=1` 与镜像固定索引展示说明，默认缓存30秒。没有模型key和writer授权。页面对过期资料只提示，不展示旧正文；模型文字不执行、不获得HTML权限，相关链接只指向本profile实际存在的组件。

上线验收分别执行 `verify_ui.py` 和 `verify_knowledge.py`：后者检查首批20项、证据摘要、只读写入拒绝、网页无key，以及8次真实Dashboard搜索/说明展示；拦截任何模型调用或Unit构造。

模型输出未通过字段或边界校验时，依据同一冻结证据进行有限纠正；独立复审的格式修正不能清除实质问题。不放宽接纳规则。已收到的成功响应用量会合并，但失败 HTTP 的完整用量记账仍有缺口，不能据此推断全部服务端账单。

### 后台自动整理

旧部署曾通过独立的 `framework-catalog-curation.timer` 周期触发整理，约每15分钟检查一次，每批最多20项。2026-10-27 已停止并取消开机启用，不能因更新网页或还有待办而恢复。历史每日名额账本继续保留，它不代表本轮授权、token 数或金额预算。当前源码的宿主入口和容器入口均在未获显式执行参数时拒绝付费；服务器实际镜像与宿主脚本的验收以 [部署记录](DEPLOYED_CN.md) 为准。

本地 `auto_curate.py --drain --max-items N` 还要求 `--execute`；普通 `--once` 同样需要明确执行，旧timer不会自动获得授权。全量工具 `complete_catalog.py` 不带 `--execute` 时只输出本地计划；执行时默认一批，不能把 `--wait-seconds 0` 当作批数限制。原来源冻结、退避和尝试账本保留；完成须重新读取实际缓存，不能把已安排数量当作成功数量。范围许可不等于金额上限。

后台另发布经过白名单投影的 `/opt/framework-catalog/automation/progress/progress.json`，仅含数量、状态、时间和来源身份；网页只读挂载整个 progress 目录至 `/run/catalog-progress`，通过 `NSGABLACK_CATALOG_PROGRESS_PATH` 指定该固定文件。必须挂目录以接收原子替换，不能挂单文件留住旧inode；不得挂载私密state、writer、模型配置或宿主完整automation目录。systemd只增加progress目录写权限。网页核对当前源码索引身份，旧发布状态不冒充当前进度。

自动任务读取 `current/service.json`，核对当前网页实际运行的镜像身份，使用该固定镜像中的源码证据与生成规则。它只处理当前已发布版本：本机工作区的改动必须先发布，才会进入服务器整理范围。它不自动部署代码，也不改写组件源码或接口契约。

任务先查询现有知识的精确缓存身份。无待整理内容时不请求模型；新增或源码／模型／规则变化的条目进入待办。失败项独立退避，队列轮转，避免少数反复失败的组件挡住其余内容。鉴权或余额错误触发暂停，保留可追查的类别，不记录原始响应或凭据。

每天的限制按UTC日期计算，在调用模型前预留本批名额；失败与中断也计入，避免异常重启绕过限制。名额计算的是组件尝试，不是API调用次数或金额：单项仍可能发生已有的有限网络重试和一次格式纠正。不能把它当作账单金额硬上限。

主机文件锁和固定任务容器防止并发运行。短任务仅挂载现有 writer 与 DeepSeek 配置，不暴露服务端口，网页授权保持不变。状态和最后结果在主机私密目录持久化；停止定时器不会删除已整理资料，后续恢复会复用缓存。

运维查看与停用方式：

```bash
systemctl status framework-catalog-curation.timer
systemctl status framework-catalog-curation.service
systemctl list-timers framework-catalog-curation.timer
python3 /opt/framework-catalog/automation/auto_curate.py --status

# 仅停用自动整理，Catalog 网页继续提供已有资料
systemctl disable --now framework-catalog-curation.timer
systemctl stop framework-catalog-curation.service
```
