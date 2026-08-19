# 学习路线图

本路线图面向 nsgablack + mlblack 双框架的独立开发者。每条路线都和框架已有组件对接，学了能用。

---

## 1. SQL 与查询优化

**和框架的对应：** `catalog/store/postgres.py`（catalog 后端）、`core/resources/backends_postgres.py`（L0 task queue）。

**已懂：** `SELECT`、`INSERT`、`CREATE TABLE`、`FOR UPDATE SKIP LOCKED`。

**需要补：**

- 执行计划：`EXPLAIN ANALYZE`。你的 catalog 查询在 10 万条目时走全表扫描还是索引命中，看这个就知
- 索引策略：B-tree（等值/范围查询）、Hash（等值查询）、GIN（全文搜索/数组包含）。catalog 的 `search_entries` 如果用 GIN 索引 `tags` 数组，会比 `LIKE '%keyword%'` 快两个数量级
- 事务隔离级别：READ COMMITTED vs REPEATABLE READ vs SERIALIZABLE。L0 的 `PostgresTaskQueueBackend.claim()` 用了 `FOR UPDATE SKIP LOCKED`——它在 REPEATABLE READ 下的行为是什么？多个 worker 同时 claim 会不会丢任务？
- 连接池：你的 catalog 和 L0 backend 每个请求都 `connect()` → `close()`。在高并发下应该用 `psycopg_pool`。理解连接池的工作方式：多少个连接够用？什么时候该扩容？

**练习：** 给 `catalog_entry` 表加一个 GIN 索引，用 `EXPLAIN ANALYZE` 比较加索引前后的 `search_entries` 查询耗时。目标：让关键词搜索不走全表扫描。

---

## 2. 网络协议与序列化

**和框架的对应：** `core/resources/backends.py`（`DataTransportBackend`、`InlineDataTransportBackend`、`ArtifactDataTransportBackend`）。

**已懂：** JSON 序列化、bytes 传输、`DataRef` 为引用。

**需要补：**

- JSON 的代价：Python dict → JSON string → bytes，每步都 copy 一次。一个 10MB 的候选向量 JSON 序列化后可能变成 30MB（float 的文本表示）。这就是为什么你区分了 `InlineDataTransportBackend`（小 payload）和 `ArtifactDataTransportBackend`（大 payload 走引用）
- Protobuf / FlatBuffers / Cap'n Proto：二进制格式，不需要 parse。对 L0 的 task payload 来说，protobuf 序列化的 float 向量就是原始字节，零膨胀
- Apache Arrow：列式内存格式，可以零拷贝从 C++ 传给 Python、从磁盘传给内存。你的 `S3ParquetSource` 读取 Parquet 文件时，pyarrow 做的就是把 Parquet（列存）→ Arrow（列存内存）→ numpy（零拷贝视图）。整条链没有一次全量数据拷贝
- gRPC vs REST：gRPC 用 protobuf + HTTP/2 多路复用，你的 L0 在跨节点 worker 通信时用 gRPC 比 HTTP+JSON 快 5-10×。什么时候该用——worker 之间高频通信（心跳、task 分发、result 返回）

**练习：** 把 `task_to_json` / `result_to_json` 替换为一个 protobuf 实现，比较 1000 条 task 的序列化耗时和字节数。目标：理解为什么二进制格式比 JSON 小 3-5×。

---

## 3. 并发模型

**和框架的对应：** L0 的 `TaskQueueBackend`（线程安全）、Redis 的 BRPOP（阻塞出队）、PostgreSQL 的 SKIP LOCKED。

**已懂：** `threading.Condition`、`RLock`、多线程基础。

**需要补：**

- Python GIL：什么时候多线程有用（I/O 密集——等网络、等磁盘），什么时候没用（CPU 密集——numpy 矩阵运算）。你的 L0 worker 如果做 GPU 训练，多线程就够了；如果做纯 Python 的目标函数评估，要用多进程
- asyncio 事件循环：单线程协作式并发。适合"等很多事回复"的场景——比如一个 AsyncEventDrivenAdapter 同时等 100 个远程 evaluate 结果。比开 100 个线程省资源，但要求所有 I/O 操作都是非阻塞的
- 多进程 vs 多线程：`ProcessPoolBackend` vs `ThreadPoolBackend` 的选择不只是"并行用线程、CPU 用进程"。多进程的 IPC 开销（pickle 序列化）比多线程的共享内存大得多。小数据量用线程、大数据量且 CPU 密集用进程
- 锁的粒度：你的 `InMemoryLeaseStore` 用一个全局 RLock 保护所有 lease。如果 100 个 worker 同时申请 lease，它们会在这一把锁上排队。优化手段：分片锁（按 GPU 编号分）、读写锁（lease 查询多写少）、无锁数据结构（原子操作）

**练习：** 写一个 benchmark：100 个线程同时往 `InMemoryTaskQueueBackend` 提交和 claim task，测吞吐量。然后把锁改成读多写少的 `threading.RWLock`（自己实现或用第三方），再测。目标：理解锁竞争对吞吐的影响。

---

## 4. 测试策略

**和框架的对应：** `tests/` 目录已有 665 个测试，但覆盖不均匀。

**已懂：** 写 `def test_xxx(): assert ...`。

**需要补：**

- 单元测试 vs 集成测试：你当前没有区分。`test_pareto_archive_truncates_with_crowding` 是单元测试（只测一个 Plugin）。`test_authoritative_examples_smoke` 是集成测试（启动 Solver 跑完整流程）。应该分开放：单元测试 1 秒跑完做 CI 门禁，集成测试夜间跑
- Property-based test：不写"给定输入 X 期望输出 Y"，写"对于任意合法输入，某种恒等式总成立"。比如"Archive 的 `_nondominated_mask` 返回的集合里，不存在 A 支配 B"——这不是测试一个 case，是测试一个数学性质。用 `hypothesis` 库自动生成输入
- Fixture 管理：你的 `_ToyProblem` 在多个测试文件里重复定义。抽到 `conftest.py` 里作为 fixture。factory-boy 风格造数据
- Mock 的策略：什么时候 mock 数据库（不想起 PostgreSQL）、什么时候不 mock（要测真的 SQL 语法）。规则——外部依赖（网络、数据库、文件系统）在单元测试 mock，在集成测试不 mock
- 代码覆盖率：`coverage.py` 跑一遍 `pytest --cov=nsgablack`。不是追求 100%，是看哪些代码路径从来没被跑过——那些就是潜在的 bug 窝

**练习：** 给 `ParetoArchivePlugin._nondominated_mask` 写一个 property test：随机生成 N 个目标向量，验证返回的 mask 中不存在 A 支配 B。用 `hypothesis` 库。目标：理解"测试恒等式"和"测试具体值"的区别。

---

## 5. Build、部署、DevOps 入门

**和框架的对应：** 你的框架是一个 Python 包，目前全靠 `python -m nsgablack` 在本地跑。要让它能在"真实环境"运行。

**已懂：** `pip install -e .`、`python -m pytest`。

**需要补：**

- Docker：把你的 PostgreSQL + Redis + nsgablack 写成 `docker-compose.yml`。别人 clone 下来敲 `docker compose up` 就能得到一个运行中环境——PostgreSQL catalog、Redis L0 runtime、一个 worker。不需要手动装依赖
- CI pipeline：GitHub Actions 免费。最少的 CI：每次 push 自动 `pip install -e .` → `pytest tests/unit/` → `flake8` / `ruff`。保护你的 main 分支永远不会被坏的 commit 破坏
- 打包和版本：`pyproject.toml` 里配好 entry point。用户 `pip install nsgablack` 之后 `python -m nsgablack` 能用。加版本号 `__version__ = "0.1.0"`，用 `setuptools_scm` 从 git tag 自动读版本
- 日志 vs print：把框架里的 `print()` 换成 `logging.getLogger(__name__).info()`。加一个 `NSGABLACK_LOG_LEVEL` 环境变量控制日志粒度——本地调试时 TRACE，生产跑时 WARNING

**练习（推荐先做）：** 写一个 `docker-compose.yml`，编排 postgres:16 + redis:7 + 一个 nsgablack worker container。目标：从 `docker compose up` 到在容器里跑通一个完整的 propose → evaluate → update 循环。

---

## 学习顺序建议

如果每天拿出 1-2 小时，按这个顺序收益递减最慢：

1. **Docker + docker-compose**（1-2 天）——立即让你的框架"能给别人跑"
2. **SQL 索引 + EXPLAIN**（2-3 天）——直接加速你的 catalog 查询
3. **测试策略**（穿插进行）——每写一个新功能，先写 property test 再写实现
4. **序列化（Arrow / Protobuf）**（3-5 天）——对你的 DataTransport 层有直接性能收益
5. **并发模型**（5-7 天）——最费脑，但理解了 GIL/asyncio/锁粒度之后不会再写出死锁

---

## 6. ML 基础（为架构设计，不为炼丹）

你不需要成为调参专家，不需要知道 ResNet 有多少层。你需要的是理解 ML 的**结构模式**——因为 mlblack 的 Codec / Spec / Problem / Trainer 就是对这些模式做抽象。

### 6.1 什么是"模型"——从运筹视角看 ML

你的背景是运筹学（目标函数 + 约束 + 搜索）。在这个视角下，ML 的本质是：

- 运筹：给定已知的目标函数 f(x)，用搜索算法找最优 x
- ML：给定已知的 (X, y) 数据对，用一个参数化函数 g(x; θ) 去近似 f，搜索的是 θ

"训练"就是搜索 θ。梯度下降是一种搜索算法——它用导数的方向信息加速搜索。BP (反向传播) 是自动求导链式法则的实现。

**你框架里的对应：** nsgablack 的 `GradientOptimizerAdapter` 是搜索 θ 的策略；mlblack 的 `FunctionalGradientLearningProblem` 负责把 autograd 梯度放进正式 Feedback。`Problem.evaluate` 给的是 loss（相当于运筹里的目标函数值），`UnknownState` 就是 θ 的扁平化表示。你不需要理解"怎么推导 softmax 的导数"——autograd 替你做了。你需要理解的是：梯度下降在做什么、什么时候会卡在鞍点、为什么需要学习率衰减和学习率预热。

**推荐资料：** 李宏毅《机器学习》2021 课程前 5 讲（B 站有），不讲数学推导，只讲直觉。

### 6.2 损失函数 = 你定义"什么是好的"

MSE（均方误差）= 预测值和真实值越接近越好。Cross-Entropy = 预测的概率分布和真实标签越一致越好。Huber Loss = 对异常值不敏感（离得近和 MSE 一样惩罚、离得远改为线性惩罚）。

**你框架里的对应：** 这些是 `Problem` 层的职责。你的 `BlackBoxProblem.evaluate()` 就是计算 loss 的地方。理解每个 loss 的语义，你才能在 Problem 层选对它。

### 6.3 神经网络不是魔法——是复合函数

一个线性层 `y = Wx + b` 就是矩阵乘法加平移。激活函数（ReLU、GELU）就是 if x>0 then x else 0 的平滑版。堆叠多层 = 复合函数 `f₃(f₂(f₁(x)))`  = 非线性表达能力。

**你框架里的对应：** `NeuralGraphSpec` 里的 `NeuralBlockSpec`。你声明 "这一层是 Linear(64→32) + ReLU"，`NeuralGraphCodec` 算出参数量（64×32 + 32 = 2080 个 θ），从 `UnknownState` 里切出 2080 个值填进去。这就是解码——你不关心 W 矩阵里具体是什么数，只关心它占多少维。

**推荐资料：** 3Blue1Brown《Neural Networks》系列（YouTube，4 集，每集 15 分钟）。先看这个再看任何理论书。

### 6.4 过拟合 / 欠拟合 = 你的搜索在错误的空间

过拟合：你的模型 g(x; θ) 把噪音也学到了。在训练数据上表现极好，在新数据上表现差。等价于：你的搜索找到了一个对训练集最优的解，但这个解不在真实问题的 Pareto 前沿上。

欠拟合：你的模型太简单了，连训练数据上的规律都学不到。

**你框架里的对应：** `train_valid_split`（拆训练集/验证集）、`NumericDataView`（携带训练集和验证集）、`ModelConditionedTargetConfig`（防止数据泄漏的 stage-to-stage 数据隔离）。这些不是你随便加的——它们是防止过拟合的架构手段。

### 6.5 集成 = 你的"多专家投票"设计直觉是对的

为什么集成方法（Bagging、Boosting、Stacking）有效？因为单个模型的误差可以分解为 bias + variance + noise。集成降低的是 variance——多个模型各自犯错的地方不同，平均后互相抵消。

**你框架里的对应：** `PredictionIntegrationComponent` 就是集成。`.additive(weights=...)` 等于加权投票。`ModelConditionedTargetComponent` 等于 Boosting——用前一阶段的残差训练下一阶段。你已经实现了这些，理解它们为什么在数学上有效会让你知道什么时候该用 additive、什么时候该用 gated。

### 6.6 你应该跳过的东西

- 手动推导反向传播公式（autograd 做了）
- CNN/RNN/Transformer 的 paper 原文（除非你要实现新的架构 spec）
- 调参技巧大全（batch size、learning rate schedule、weight decay——这些是工程师的经验积累，不是架构知识）
- GAN / Diffusion / RL 的实现细节（等你真的在框架里做这些场景再学）

**当前最小必看：** 3Blue1Brown 的 4 集神经网络视频 + 李宏毅课程前 5 讲。总共约 6 小时。看完之后你对 mlblack 里每个组件的命名和设计会有完全不同的理解。

---

## 不需要现在学的

- Hadoop / Spark / Flink：数据工程，不是你的方向。你只需要接入它们产出的数据
- Kubernetes：等你需要管理 10+ 节点的集群再学，Docker compose 足够当前规模
- 深度学习框架源码（Torch JIT、JAX XLA）：你是 mlblack 的用户，不是 PyTorch 的开发者
- 分布式共识算法（Raft、Paxos）：PostgreSQL 和 Redis 已经替你实现了
- 手动推导反向传播：autograd 做了，你只需要知道梯度下降在搜索 θ 就够了
