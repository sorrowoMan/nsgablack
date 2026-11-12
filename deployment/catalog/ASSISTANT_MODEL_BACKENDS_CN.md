# 实验台 AI 的模型后端配置

实验台通过 `AssistantManager` 调用一个模型生成 JSON 草案，再进入同一份 `validate_draft` 校验。
现在可在 DeepSeek 与单独配置的聊天补全服务之间切换。后者可用于托管或自部署的微调模型，
但这个接口本身不负责训练、加载 LoRA 或启动推理服务；模型必须已经由推理后端提供服务。

## 1. 现有 DeepSeek 配置保持有效

现有文件不需要新增字段，继续使用官方固定 HTTPS 地址：

```json
{
  "api_key": "替换为该服务的密钥",
  "model": "deepseek-flash",
  "max_output_tokens": 4096,
  "timeout_seconds": 60
}
```

也可显式加 `"provider": "deepseek"`。旧的 `DeepSeekConfig` 和组件资料整理任务不变。

## 2. 自部署模型

私有服务配置文件写成：

```json
{
  "provider": "compatible",
  "base_url": "http://127.0.0.1:9000/v1",
  "model": "framework-assistant-lora",
  "max_output_tokens": 4096,
  "timeout_seconds": 60,
  "json_mode": true
}
```

`model` 必须是推理服务实际暴露的模型名称。LoRA 加载与基座选择由推理服务配置负责，
不能只把任意增量权重目录填到这里就认为已完成加载。HTTP 只允许 `localhost` 或字面量回环 IP。
省略 `api_key` 只允许这种本机回环服务，不会读取环境变量，也不会借用 DeepSeek 的 key。
容器里的 `127.0.0.1` 是该容器本身；跨容器服务须使用已配置证书的 HTTPS 地址与独立密钥，
或者通过受控回环转发接入。这里不会替部署者建立网络通道。

## 3. 托管或跨主机微调模型

```json
{
  "provider": "compatible",
  "base_url": "https://models.example.com/v1",
  "model": "team/framework-assistant",
  "api_key": "替换为此模型服务专用密钥",
  "max_output_tokens": 4096,
  "timeout_seconds": 60,
  "json_mode": true
}
```

HTTPS 地址由写入私有文件的部署者明确选择和信任。此字段不会由浏览器、自然语言、模型回复、
Catalog 数据或环境变量指定。只接受 origin 或 `/v1` 基路径，自动追加 `/chat/completions`；
不接受已含 `/chat/completions` 的完整地址、任意自定义路径、URL 用户信息、查询或片段。
连接禁用继承代理及 HTTP 跳转，不会自动重试。失败只返回固定错误类别，不返回上游响应正文。
输出预算为 256 至 4096 tokens，超时为 5 至 60 秒，响应上限为 256 KiB。

`compatible` 不发送 DeepSeek 专用的 `thinking` 字段。默认发送 `response_format=json_object`；
若服务不支持这一参数，可设 `json_mode=false`。关闭请求提示后，回复仍须是严格 JSON，
不会因此放宽字段、版本、组件和装配参数校验。模型必须支持 system/user 消息与非流式聊天补全。

## 4. 服务接线与交付边界

仍使用已有服务入口的 `--ai-config` 指向私有配置文件。只有 assistant 进程读取模型配置；
reader 和执行试跑的 runner 不接触模型密钥。更新文件后需受控重启 assistant 服务。
本次新增接口不自动部署模型，也不修改现有线上配置。

两类后端共用当前 `assistant_messages(packet)`、框架引导 Skill 和草案校验。
`AssistantManager` 保留请求去重和显式应用边界；模型输出仍显示 `verification_status=not_run`，
必须独立试跑才有运行证据。AI 编辑没有每日次数上限，`requests_per_utc_day/remaining/resets_at`
仍为 `null`。新增后端不影响用户已明确要求的无每日限额策略。

验证覆盖旧配置、独立密钥、路径与 HTTP 约束、代理与跳转拒绝、超时/坏回复、真实本机 HTTP，
以及端到端去重和草案拒绝。对应测试是 `tests/test_catalog_lab_model_provider.py`；
这些测试使用本机模拟服务，不代表任意厂商或微调权重已通过真实效果验收。
