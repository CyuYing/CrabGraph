"""Collect public GitHub evidence with timestamps and bounded concurrency."""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research"
SEEDS = [
    "HKUDS/LightRAG", "HKUDS/RAG-Anything", "langchain-ai/langchain",
    "langchain-ai/langgraph", "langchain-ai/retrieval-agent-template",
    "infiniflow/ragflow", "langgenius/dify", "open-webui/open-webui",
    "explodinggradients/ragas", "streamlit/streamlit", "fastapi/fastapi",
    "shangxiang0907/HeiMa-AI-LLM-RAG-Agent-Dev",
]
QUERIES = ["lightrag stars:>100", "langgraph rag agent stars:>500", "multimodal rag stars:>500"]


def fetch(url: str) -> bytes:
    headers = {"User-Agent": "CrabGraph-research/1.0", "Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN") and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as r:
        return r.read()


def collect(name: str) -> dict:
    folder = OUT / "snapshots" / name.replace("/", "__")
    folder.mkdir(parents=True, exist_ok=True)
    try:
        cache = OUT / "connector_metadata.json"
        cached = {x.get("full_name"): x for x in json.loads(cache.read_text(encoding="utf-8"))} if cache.exists() else {}
        meta = cached.get(name) or json.loads(fetch("https://api.github.com/repos/" + name))
        (folder / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        readme_error = None
        readme_url = f"https://raw.githubusercontent.com/{name}/{meta['default_branch']}/README.md"
        try:
            (folder / "README.md").write_bytes(fetch(readme_url))
        except Exception as exc:
            readme_error = str(exc)
        return {"repository": name, "stars": meta["stargazers_count"], "forks": meta["forks_count"],
                "pushed_at": meta["pushed_at"], "archived": meta["archived"],
                "license": (meta.get("license") or {}).get("spdx_id", "unconfirmed"),
                "url": meta["html_url"], "default_branch": meta["default_branch"], "readme_error": readme_error}
    except Exception as e:
        return {"repository": name, "error": type(e).__name__ + ": " + str(e)}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    names = set(SEEDS)
    search_log = []
    for query in ([] if (OUT / "connector_metadata.json").exists() else QUERIES):
        try:
            url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
                {"q": query, "sort": "stars", "order": "desc", "per_page": 5})
            result = json.loads(fetch(url))
            (OUT / ("search_" + str(len(search_log)) + ".json")).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            names.update(x["full_name"] for x in result["items"][:3])
            search_log.append({"query": query, "total_count": result["total_count"], "url": url})
        except Exception as e:
            search_log.append({"query": query, "error": str(e)})
    if (OUT / "connector_metadata.json").exists():
        names.update(x["full_name"] for x in json.loads((OUT / "connector_metadata.json").read_text(encoding="utf-8")) if x.get("full_name"))
        search_log.append({"source": "GitHub connector + earlier public search", "queries": QUERIES,
                           "note": "Public REST rate limit hit; repository metadata collected through authenticated connector."})
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        items = list(pool.map(collect, sorted(names)))
    items.sort(key=lambda x: x.get("stars", -1), reverse=True)
    payload = {"collected_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
               "queries": search_log, "projects": items}
    (OUT / "github_projects.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# GitHub 项目采集结果", "", "采集时间：" + payload["collected_at"], "",
             "公开 GitHub API 按 stars 降序搜索；另加入课程对应仓库及相关官方框架。Stars 是采集时快照，不代表质量或全球排名。", "",
             "| 项目 | Stars | License | 最近推送 UTC |", "|---|---:|---|---|"]
    for x in items:
        lines.append(f"| [{x['repository']}]({x.get('url', 'https://github.com/' + x['repository'])}) | {x.get('stars', '失败')} | {x.get('license', '待核实')} | {x.get('pushed_at', x.get('error', ''))} |")
    lines.extend(["", "每个项目的原始元数据和 README 位于 `snapshots/`。未声明或无法确认许可证的仓库仅用于研究，不复制实现。",
                  "", "本项目采用 LangChain / LangGraph 工具编排、LightRAG 图谱与向量检索、Streamlit 演示界面；RAGFlow/Dify 作为产品参考，Ragas 作为后续评测参考。",
                  "RAG-Anything 仅作多模态历史架构参考；当前本地 LightRAG 已有原生多模态模块，应优先复用现有实现。"])
    (OUT / "github_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    course = json.loads(fetch("https://api.bilibili.com/x/web-interface/view?bvid=BV1yjz5BLEoY"))
    if course.get("code") == 0:
        data = course["data"]
        (OUT / "video_chapters.json").write_text(json.dumps({"bvid": data["bvid"], "title": data["title"],
            "source": "https://www.bilibili.com/video/BV1yjz5BLEoY/", "evidence": "公开简介和分集目录；未逐帧观看全部视频",
            "chapters": [{k: p[k] for k in ("page", "part", "duration")} for p in data["pages"]]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"projects": len(items), "successful": sum("stars" in x for x in items),
                      "top": [{"repository": x["repository"], "stars": x.get("stars")} for x in items[:8]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
