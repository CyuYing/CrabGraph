"""Curated, open-source adapters; preferences apply to this local workspace."""
from crabgraph.settings import ROOT

CATALOG = [
    dict(id="knowledge", name="知识库检索", agent="search_knowledge", mcp="search_crab_knowledge", category="知识", description="从迁移副本联合检索原文与知识图谱。", permission="读取项目知识库", default=True, locked=True),
    dict(id="literature", name="联网文献检索", agent="search_public_literature", mcp="search_public_literature", category="联网", description="联网检索 Crossref 书目、DOI 与论文链接，无需额外 API Key。", permission="访问 Crossref 公共 API", default=True),
    dict(id="webpage", name="公开网页阅读", agent="fetch_research_page", mcp="fetch_research_page", category="联网", description="读取 FAO、NCBI、PLOS、Wikipedia、Wikimedia 的公开网页正文。", permission="联网读取指定研究网站", default=True),
    dict(id="mcp_images", name="MCP 图片检索", agent="search_images_via_mcp", mcp="search_reference_images", category="图像", description="检索 Wikimedia 参考图片，返回来源与许可信息。", permission="访问 Wikimedia 公共 API", default=True),
    dict(id="terminal", name="养殖记录分析", agent="analyze_pond_records", mcp="analyze_pond_csv", category="分析", description="执行固定 Python 统计程序分析 CSV，返回描述统计。", permission="读取用户 CSV · 固定统计程序", default=True),
    dict(id="download", name="研究 PDF 下载", agent="download_research_pdf", mcp="download_research_pdf", category="文件", description="从指定研究网站下载 PDF，保存到项目资源目录。", permission="联网 · 写入项目资源目录", default=False),
    dict(id="note", name="研究笔记", agent="save_note", mcp="save_note", category="文件", description="把研究记录保存为 Markdown，可在工具结果中下载。", permission="写入项目资源目录", default=False),
]


def catalog(store):
    overrides = store.tool_preferences()
    return [dict(t, enabled=overrides.get(t["id"], t["default"]), license="MIT（本项目适配器）", protocol="MCP / Agent Tool", source="src/crabgraph/mcp_server.py") for t in CATALOG]


def enabled_ids(store):
    return [t["id"] for t in catalog(store) if t["enabled"]]


def enabled_agents(ids):
    return {t["agent"] for t in CATALOG if t["id"] in ids}


def require_enabled(tool_id):
    from crabgraph.store import Store
    if tool_id not in enabled_ids(Store(ROOT / "runtime" / "workbench.sqlite")):
        raise ValueError("工具已停用，请在工具商店启用后重试")
