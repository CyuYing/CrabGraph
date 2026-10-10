# 运行与维护

项目目录为 `E:\Projects\deepseek-lightrag-agent`。默认入口是 Vue 工作台 `http://127.0.0.1:8503`；FastAPI 同时提供 `/docs` 接口文档。

```powershell
cd E:\Projects\deepseek-lightrag-agent
.\setup.ps1
.\start.ps1
```

已配置的机器直接运行 `start.ps1` 即可。脚本验证端口归属，启动迁移的 LightRAG、独立 PGvector 与 FastAPI，窗口隐藏，日志写入 `runtime/logs`。运行 `stop.ps1` 只停止本项目拥有的 9622、8502、8503、8510 服务，不操作原始 9621。

## 服务与数据

| 服务 | 端口 | 数据位置 |
|---|---:|---|
| FastAPI 和 Vue | 8503 | runtime/workbench.sqlite、conversations.sqlite |
| LightRAG 副本 | 9622 | runtime/lightrag/rag_storage 与 inputs |
| PostgreSQL pgvector | 8510 | runtime/pgvector |
| 原始 LightRAG | 9621 | 原有目录，由用户独立管理 |

LightRAG 大型向量文件使用本项目进程内的流式加载器，4 MiB 读取缓冲避免大 base64 字符串的频繁复制。它不修改原始源代码，也不改变 NanoVectorDB 的存储格式。运行时仍会占用较多内存，启动需等待知识库载入。

PGvector 来自已有 LightRAG **副本的原文向量快照**，保留 Jina 模型和 1024 维配置。应用中的 `PGvector 原文快照` 模式使用真实查询嵌入与 PostgreSQL cosine 距离；它不是图片索引，也不自动同步后续新上传的资料。新上传资料请使用 LightRAG 混合检索。更新 PGvector 时先停止 8510，备份 `runtime/pgvector`，重新运行 `scripts/seed_pgvector.py`，使用空的新数据库目录启动后导入。不要覆盖唯一备份。

## 模型与凭据

点击头像打开设置弹窗，选择模型与连接，可选择 DeepSeek、通义千问、智谱 GLM 模板或自定义 OpenAI 兼容接口；保存后立即用于后续应用生成任务，并原子写入根目录 `.env`。接口地址变化时要求新凭据；GET配置仅返回已配置状态。执行中任务结束前不能修改模型。本机继续使用原有兼容接口的 `deepseek-v4-flash`，此次模板预览没有替换实际接口。LightRAG内部抽取及嵌入沿用副本配置。直接手动改 `.env` 则需要重启工作台。

会话与项目置顶、对话归属、工具启停保存在 `runtime/workbench.sqlite`，与聊天记录一起备份。工具商店有7项适配器，默认启用5项；新增问答保存工具选择快照，工具实验室在提交时检查启停状态，MCP每次调用检查最新状态。研究工作流始终可检索知识库；附加CSV需要启用分析工具。第三方MCP示例链接仅供查看源码，尚无任意外部服务器一键安装功能。

设置弹窗的 LightRAG 卡片提供“启用知识图谱”开关。开启使用图谱与原文混合检索，关闭仅使用原文；偏好保存在工作台 SQLite。问答与研究任务保存提交时的开关状态，后续修改不改变已有任务；MCP 知识检索每次读取当前偏好。对话区不再显示检索模式或项目归属下拉框。

迁移知识库的嵌入凭据单独保存在 `runtime/lightrag/.env`，不要更换嵌入模型后直接复用旧索引。`.env`、runtime、vendor、node_modules 与私有迁移清单均不提交 Git。前端配置接口只暴露凭据是否配置，不返回密钥。

## 持久化与任务恢复

问答按 session_id 保存 LangGraph 会话状态；界面消息另外保存于工作台 SQLite。后台任务与事件流可重放，断开浏览器不取消任务。每会话只允许一个进行中的问答；全局最多2个执行线程，队列限制4个任务。

服务重启后，正在执行或排队的任务标为失败，已进入 `awaiting_approval` 的研究计划保留，可继续审批恢复。取消是协作式操作：当前网络请求返回后停止，不会立即中断模型供应商已经接收的请求。

## MCP

```json
{"mcpServers":{"crabgraph":{"command":"E:\\Projects\\deepseek-lightrag-agent\\.venv\\Scripts\\python.exe","args":["-m","crabgraph.mcp_server"]}}}
```

MCP 提供知识、文献、网页、图片、CSV分析、PDF下载与笔记共7个工具及 `crabgraph://capabilities`；可选工具调用会检查商店启用状态。应用的图片搜索工具通过 SDK 启动本项目 stdio 服务，执行实际 MCP 客户端调用。

## 验证

```powershell
.\.venv\Scripts\pytest.exe -q
.\.venv\Scripts\ruff.exe check src scripts tests --config pyproject.toml
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts\live_workbench_check.py
.\.venv\Scripts\python.exe scripts\live_multimodal_check.py
```

后两项会真实调用已配置模型与嵌入接口并产生费用；只在需要重新验收时运行。图文验证使用自绘青蟹插画与合成 CSV，只验证输入协议、调用链和统计功能，不作为识别准确率测试。

## Serverless 边界

`crabgraph.serverless:handler` 是 Mangum 入口适配，已有 Lambda HTTP 事件单测。它尚未云端部署，不计入技术覆盖。当前后台线程、SQLite、固定 loopback 知识库地址适合本机工作台；完整云部署需要持久化数据库、任务队列、独立知识库服务与认证配置，不能直接把本机后台线程当成云端持久任务。
