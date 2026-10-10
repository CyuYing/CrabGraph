# 当前技术选型

当前版本使用 FastAPI + LangChain / LangGraph + Vue 3 + DeepSeek + LightRAG + PostgreSQL pgvector。按此前选择的 Python 方向，将飞书公开的 16 个技术条目逐项对应，13/16 = 81.25% 是技术能力的等价覆盖比例，并非使用相同 Java 库。

具体实现与验证证据见 [逐项清单](technology-coverage.json) 和 [带图项目说明](project-guide.html#coverage)。Serverless 云部署、Cursor 开发环境、Ollama 本地模型运行不计入。PGlite 是单进程 PostgreSQL 内核演示，不是生产数据库集群；PGvector 为迁移时的原文快照，不自动同步新上传资料。
