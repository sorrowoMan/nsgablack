# Redis Context 后端：安全配置、运行与迁移

Redis 只改变 Context 的存储位置，不改变它的语义边界：Context 仍然只承载小型契约
字段、控制信号和正式引用；population、模型、完整历史等大对象必须进入 Snapshot 或
Artifact。

## 1. 本机开发的安全启动方式

推荐直接使用 BlackBase 提供的本机 Compose：

```powershell
Set-Location C:\Users\hp\Desktop\blackbase
docker compose -f compose.redis.local.yml up -d
```

等价的单容器命令是：

```powershell
docker run --name nsgablack-redis `
  -p 127.0.0.1:6379:6379 `
  -d --restart unless-stopped `
  redis:7.4-alpine redis-server --appendonly yes --protected-mode no
```

这里的 `127.0.0.1:` 不能省略。`-p 6379:6379` 会把无认证服务发布到所有主机网卡，
不属于安全的本机开发配置。

检查实际监听面与连通性：

```powershell
docker ps --format "table {{.Names}}\t{{.Ports}}"
python -c "import redis; print(redis.Redis(host='127.0.0.1', port=6379).ping())"
```

## 2. Solver 配置

```python
solver = EvolutionSolver(
    problem,
    context_store_backend="redis",
    context_store_redis_url="redis://127.0.0.1:6379/0",
    context_store_key_prefix="nsgablack:projA:context",
    context_store_ttl_seconds=3600,
    context_store_serializer="safe",
    context_store_max_payload_bytes=262_144,
)
```

`safe` 是默认且推荐的版本化信封。它精确保留基础标量、tuple/list/set、bytes、
非 object NumPy 数组、`DataRef` 和 `StateRef`，并拒绝任意 Python 对象，不会退化成
`repr` 字符串。

`pickle_signed` 只用于受控的旧数据互操作；它并不会放宽 Context 的正式类型边界。
它把 pickle 放在 JSON 外信封中，先校验 HMAC，再执行反序列化：

```powershell
$env:NSGABLACK_CONTEXT_HMAC_KEY = "<由密钥系统注入，不提交到仓库>"
```

```python
context_store_serializer="pickle_signed"
context_store_hmac_env_var="NSGABLACK_CONTEXT_HMAC_KEY"
```

签名只能保证完整性，不能把 pickle 变成跨信任边界的安全格式。普通运行应继续使用
`safe`。

## 3. 旧 pickle Context 的迁移

新版本不会在 `safe` 模式下自动读取旧裸 pickle。这是有意的 fail-closed 行为，避免
攻击者通过伪造 `blackbase:context:*` 键触发任意代码执行。

确需迁移时，应满足全部条件：

1. Redis 与不可信网络完全隔离；
2. 先备份并确认旧键来源可信；
3. 使用独立进程和独立前缀，以显式 `pickle_unsafe` 模式读取；
4. 立即用 `safe` Store 写入新前缀；
5. 删除迁移进程的 pickle 权限，不在正常 Case 中开启兼容开关。

`project doctor --strict` 会拒绝 `pickle_unsafe` 和
`context_store_unsafe_allow_legacy_pickle=True` 的正常工程配置。

## 4. 跨机器部署

跨主机时不能照搬本机 Compose。至少需要：

- Redis ACL 与独立运行账户；
- TLS 或受信任私网隧道；
- 防火墙来源限制；
- 凭据通过环境变量或密钥系统注入；
- 独立 DB/namespace 与 TTL；
- 监控认证失败、危险命令和异常连接。

Redis URL 可能包含凭据。运行报告只能显示脱敏后的 backend/namespace，不能回显完整
URL。

## 5. 多项目隔离

同一 Redis 可以服务多个 Project，但前缀必须包含稳定项目标识：

```text
nsgablack:projA:context
nsgablack:projB:context
```

Context TTL 用于控制面新鲜度；Snapshot TTL 用于恢复与审计窗口。二者不能共用一个
模糊的清理策略。

## 6. Doctor 与排障

```powershell
python -m nsgablack project doctor --path . --build --strict
```

严格检查覆盖：

- 前缀缺失、过短或未包含项目标识；
- TTL 非法或策略隐式；
- 未知 serializer；
- `pickle_unsafe`；
- legacy pickle 迁移开关；
- 非正数 payload 上限；
- signed pickle 缺少 HMAC 环境变量名。

常见故障：

- `Connection refused`：Redis 未启动或端口不同；
- HMAC 校验失败：密钥轮换或数据被修改；
- `RedisValueCodecError`：旧 pickle、损坏信封、类型不受支持或数据越界；
- Context 字段过大：把载荷迁到 Snapshot/Artifact，只保留引用；
- 键提前消失：检查 TTL 是否覆盖完整 Case 生命周期。

## 7. 最小验证

```powershell
python -c "from blackbase.context import create_context_store; s=create_context_store(backend='redis', redis_url='redis://127.0.0.1:6379/0', key_prefix='nsgablack:ctxdemo', ttl_seconds=30, serializer='safe'); s.set('k', {'v':(1,2)}); print(s.get('k')); print(s.snapshot())"
```

输出中的 tuple 仍应是 tuple；Redis 原始值应是 JSON 版本化信封，而不是以 pickle 协议
字节开头。
