# 工程代码编辑器（离线组件）

这是 Streamlit v1 自定义组件，仅维护当前文件的文本草稿。它不执行 Python、不调用模型、不加载 CDN、不读写工程文件；保存仍由调用方的正式版本检查完成。

## Python 接口

调用 `nsgablack.catalog.lab_workspace_editor.render_code_editor(st, *, value, identity, key, height=520, language="python", read_only=False, goto_line=None, diagnostics=None, theme="dark")`。

- `identity` 由调用者绑定工作副本、版本、编辑会话 epoch 和文件路径。放弃草稿、外部替换文本时必须换 epoch；相同身份的后台重绘不会覆盖输入框或重置光标。
- 返回 `None` 或 `{identity, text, sequence, command}`。`command` 只有 `None` 和 `"save"`；保存请求包含最新文本，调用者应先接收文本，再保存。重复/旧序列和旧身份的消息不会改变草稿。
- 后端记住各身份的序列，作为 `sequence_base` 传入 iframe。重新挂载或切文件后回来，从该序列继续递增。
- 普通编辑在 280 毫秒停顿后同步；失焦立即同步。Ctrl/Cmd+S 或工具条保存发送最新文本。同步草稿不等于写入工作副本。
- `goto_line` 从 1 起；传 `None` 会清除这次定位记录，下次可再次定位同一行。
- `diagnostics` 是至多 200 条 `{line, column?, severity: "error"|"warning", message}`。只显示与当前文本一致的诊断；不包含修复代码或执行动作。
- Python 和 JSON 提供高亮；Markdown/TOML/纯文本保留完整编辑能力。全文上限与工作副本一致：UTF-8 512 KiB。
- `theme` 只接受 `"dark"`、`"light"`、`"system"`，默认暗色。父界面显式传入同名主题；跟随系统使用 iframe 自身的 `prefers-color-scheme`。主题改变通过 CodeMirror Compartment 重新配置，文档、光标、选区、撤销历史与消息序列继续使用原实例，不更换 `identity`。
- 暗色和浅色均覆盖语法、行号、选区、查找替换、自动完成、诊断提示、工具条与状态条。所有颜色来自 iframe 内的本地资源，不加载主题 CDN。草稿状态明确写为“已同步到会话”，不代表刷新后仍能恢复。
- 明确传 `plaintext_fallback=True` 才使用测试用 `文件内容` 文本框。生产不自动降级。

行号、Python 自动缩进、Tab 缩进、撤销/重做、Ctrl/Cmd+F 搜索和诊断标记由 CodeMirror 6 提供。编辑器自适应 iframe 的实际高度；`height` 是父页面未覆盖布局时的默认高度。

## 协议与依赖

`index.html`、`editor.css`、`editor.bundle.js` 为全部运行资源。CSP 禁止网络连接和外部脚本；CodeMirror 样式需要自身 iframe 内的内联 style。消息使用 Streamlit 官方 v1 的 `componentReady(apiVersion=1)`、`render`、`setFrameHeight` 和 `setComponentValue(dataType="json")`；协议形状核对 `streamlit-component-lib@2.0.0` 的 `dist/streamlit.js`，没有捆绑该库及 React/Arrow。

组件只接收父窗口的 render 消息并锁定其 origin，用户文本仅发给该窗口。诊断和状态使用文本节点；不把用户内容当 HTML。所有依赖使用 MIT 许可证，具体版本和原许可证见 `build-manifest.json` 与 `THIRD_PARTY_LICENSES.txt`。

## 可复现构建

把此目录的 `package.json`、`package-lock.json`、`editor.js`、`editor.css`、`index.html`、`build.mjs` 复制到独立任务缓存目录，执行 `npm ci`、`npm run build`；已有同版固定依赖时可直接重建，无需再次联网安装。将生成的 bundle、manifest 和许可证复制回此目录。无需在应用服务器安装 Node/npm；构建与运行均不需要新增 Python 依赖。版本固定在 lockfile；manifest 保存输出 SHA-256、源码与样式摘要、主题列表和实际捆绑版本，不包含机器路径或构建时间。

官方资料：<https://docs.streamlit.io/develop/concepts/custom-components/components-v1/intro>、<https://codemirror.net/docs/>。
