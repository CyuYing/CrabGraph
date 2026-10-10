"""Local-only FastAPI workbench. All LightRAG mutations target the migrated service."""
import asyncio
import json
import mimetypes
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr
from starlette.middleware.trustedhost import TrustedHostMiddleware

from crabgraph.agent import answer_events
from crabgraph.graph_stats import graph_stats
from crabgraph.multimodal import image_content
from crabgraph.settings import ROOT, Settings
from crabgraph.store import Store
from crabgraph.tool_registry import CATALOG, catalog, enabled_ids
from crabgraph.workflow import Cancelled, run_research

store = Store()
pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="crabgraph")
settings = Settings.from_env()
UPLOADS = ROOT / "runtime" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app):
    store.recover()
    yield


app = FastAPI(title="CrabGraph 青蟹智研", version="0.2.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


@app.middleware("http")
async def local_origin(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin not in {"http://127.0.0.1:8503", "http://localhost:8503"}:
            return Response("Local origin required", status_code=403)
    return await call_next(request)


def rag(method, path, **kwargs):
    # Refuse the original service even if someone changes the application environment.
    if settings.lightrag_url.rstrip("/") != "http://127.0.0.1:9622":
        raise HTTPException(503, "工作台仅连接项目副本 9622，请检查 LIGHTRAG_URL")
    try:
        with httpx.Client(timeout=35, headers={"X-API-Key": settings.lightrag_api_key} if settings.lightrag_api_key else {}) as client:
            r = client.request(method, settings.lightrag_url + path, **kwargs)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError:
        raise HTTPException(502, "知识库服务暂时不可用，请检查项目副本 9622") from None


def attachment(aid, kind=None):
    try:
        UUID(aid)
        metadata = json.loads((UPLOADS / f"{aid}.json").read_text(encoding="utf-8"))
    except (ValueError, OSError):
        raise HTTPException(404, "附件不存在") from None
    if kind and metadata["kind"] != kind:
        raise HTTPException(422, "附件类型不匹配")
    return metadata, (UPLOADS / f"{aid}.bin").read_bytes()


def job_required(jid):
    job = store.get_job(jid)
    if not job:
        raise HTTPException(404, "任务不存在")
    return job


def execute(jid, resume=False):
    job = store.get_job(jid)
    if job["status"] == "cancelled":
        return
    store.update(jid, "running")
    try:
        payload = job["payload"]
        task_settings = replace(settings, knowledge_graph_enabled=payload.get("knowledge_graph_enabled", payload.get("mode", "mix") != "naive"))
        if job["kind"] == "tool":
            from crabgraph import business_tools
            from crabgraph.mcp_client import call_mcp
            functions = {"literature": business_tools.search_literature, "webpage": business_tools.read_public_page,
                         "download": business_tools.download_public_pdf, "note": business_tools.save_research_note,
                         "terminal": business_tools.terminal_pond_statistics,
                         "mcp_images": lambda value: json.loads(call_mcp("search_reference_images", {"query": value}))}
            started = time.perf_counter()
            store.emit(jid, {"type": "stage", "text": "执行研究工具：" + payload["tool"]})
            value = functions[payload["tool"]](payload["input"])
            store.finish(jid, {"answer": "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```",
                               "data": value, "sources": [], "metrics": {"elapsed_ms": round((time.perf_counter() - started) * 1000)}})
            return
        csv = attachment(payload["csv_id"], "csv")[1].decode("utf-8-sig") if payload.get("csv_id") else None
        if job["kind"] == "research":
            run_research(task_settings, store, jid, resume, csv)
            return
        image = attachment(payload["image_id"], "image")[1] if payload.get("image_id") else None
        for event in answer_events(task_settings, job["session_id"], payload["question"], payload["mode"], image, csv, enabled_tools=payload.get("enabled_tools", enabled_ids(store))):
            if store.get_job(jid)["status"] == "cancelled":
                raise Cancelled()
            if event["type"] == "result":
                if store.finish(jid, event):
                    store.message(job["session_id"], "assistant", event)
            else:
                store.emit(jid, event)
    except Cancelled:
        store.update(jid, "cancelled")
    except Exception as exc:
        # Do not forward provider response bodies or credentials to the browser.
        store.update(jid, "failed")
        store.emit(jid, {"type": "error", "text": f"执行失败（{type(exc).__name__}）。请检查模型连接与知识库状态后重试。"})


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "crabgraph-workbench", "version": "0.2.0"}


@app.get("/api/overview")
def overview():
    counts = rag("GET", "/documents/status_counts")
    jobs = store.jobs()
    return {"documents": counts, "sessions": len(store.sessions()), "jobs": len(jobs),
            "completed": sum(j["status"] == "completed" for j in jobs),
            "recent": [{k: j[k] for k in ("id", "kind", "status", "created", "payload")} for j in jobs[:5]],
            "model": settings.model, "storage": "项目副本", "lightrag_url": settings.lightrag_url}


@app.get("/api/config")
def config():
    return {"model": settings.model, "vision_model": settings.vision_model,
            "base_url": settings.base_url, "key_configured": bool(settings.api_key),
            "knowledge_graph_enabled": store.graph_enabled(),
            "lightrag_url": settings.lightrag_url, "memory": "SQLite 持久化", "task_engine": "LangGraph",
            "mcp_command": str(ROOT / ".venv" / "Scripts" / "python.exe"),
            "mcp_args": ["-m", "crabgraph.mcp_server"]}


class RetrievalConfigRequest(BaseModel):
    knowledge_graph_enabled: bool


@app.put("/api/config/retrieval")
def configure_retrieval(body: RetrievalConfigRequest):
    store.set_graph_enabled(body.knowledge_graph_enabled)
    return config()


@app.get("/api/config/presets")
def model_presets():
    from crabgraph.model_config import PRESETS
    return PRESETS


class ModelConfigRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=150)
    vision_model: str = Field(default="", max_length=150)
    api_key: SecretStr | None = None


@app.put("/api/config/model")
def configure_model(body: ModelConfigRequest):
    global settings
    if any(j["status"] in {"queued", "running"} for j in store.jobs()):
        raise HTTPException(409, "请等待当前任务完成后保存模型配置")
    if not body.model.strip():
        raise HTTPException(422, "请输入回答模型名称")
    # A blank key can only be reused with the same endpoint, preventing accidental credential forwarding.
    key = body.api_key.get_secret_value() if body.api_key else ""
    if body.base_url.rstrip("/") != settings.base_url.rstrip("/") and not key:
        raise HTTPException(422, "切换接口地址时，请填写该服务的 API Key")
    from crabgraph.model_config import save_generation_config
    try:
        settings = save_generation_config(body.base_url, body.model, body.vision_model, key or None)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return config()


@app.get("/api/sessions")
def sessions():
    return store.sessions()


@app.post("/api/sessions")
def new_session():
    return {"id": store.session()}


@app.get("/api/sessions/{sid}/messages")
def messages(sid: str):
    if sid not in {s["id"] for s in store.sessions()}:
        raise HTTPException(404, "会话不存在")
    return store.messages(sid)


class ChatRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1, max_length=4000)
    mode: str = "mix"
    image_id: str | None = None
    csv_id: str | None = None


class ResearchRequest(BaseModel):
    goal: str = Field(min_length=2, max_length=4000)
    review_plan: bool = True
    csv_id: str | None = None


class ToolRequest(BaseModel):
    tool: str
    input: str = Field(min_length=1, max_length=20000)


@app.post("/api/tools")
def run_tool(body: ToolRequest):
    if body.tool not in {"literature", "webpage", "download", "note", "terminal", "mcp_images"}:
        raise HTTPException(422, "未知工具")
    if body.tool not in enabled_ids(store):
        raise HTTPException(403, "该工具已停用，请在工具商店启用")
    validate_attachments({})
    jid = store.job("tool", body.model_dump())
    pool.submit(execute, jid)
    return {"id": jid}


@app.get("/api/resources/{aid}")
def resource_file(aid: str, format: str = "pdf"):
    try:
        UUID(aid)
    except ValueError:
        raise HTTPException(404, "资源不存在") from None
    if format not in {"pdf", "md"}:
        raise HTTPException(422, "格式无效")
    path = ROOT / "runtime" / "resources" / f"{aid}.{format}"
    if not path.exists():
        raise HTTPException(404, "资源不存在")
    from fastapi.responses import FileResponse
    return FileResponse(path, filename=f"crabgraph-resource.{format}")


def validate_attachments(payload):
    for key, kind in [("image_id", "image"), ("csv_id", "csv")]:
        if payload.get(key):
            attachment(payload[key], kind)
    if sum(j["status"] in {"queued", "running"} for j in store.jobs()) >= 4:
        raise HTTPException(429, "任务队列已满，请稍后再试")


@app.post("/api/chat")
def chat(body: ChatRequest):
    if not body.question.strip() or body.mode not in {"mix", "hybrid", "local", "global", "naive", "pgvector"}:
        raise HTTPException(422, "请检查问题和检索模式")
    if body.session_id not in {s["id"] for s in store.sessions()}:
        raise HTTPException(404, "会话不存在")
    payload = body.model_dump()
    payload["knowledge_graph_enabled"] = store.graph_enabled()
    if not payload["knowledge_graph_enabled"]:
        payload["mode"] = "naive"
    payload["enabled_tools"] = enabled_ids(store)
    if body.csv_id and "terminal" not in payload["enabled_tools"]:
        raise HTTPException(422, "请先启用养殖记录分析工具，再附加 CSV")
    validate_attachments(payload)
    try:
        jid = store.job("chat", payload, body.session_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    store.message(body.session_id, "user", {"text": body.question, "image_id": body.image_id, "csv_id": body.csv_id})
    pool.submit(execute, jid)
    return {"id": jid}


@app.post("/api/research")
def research(body: ResearchRequest):
    payload = body.model_dump()
    payload["knowledge_graph_enabled"] = store.graph_enabled()
    validate_attachments(payload)
    if body.csv_id and "terminal" not in enabled_ids(store):
        raise HTTPException(422, "请先启用养殖记录分析工具，再附加 CSV")
    jid = store.job("research", payload)
    pool.submit(execute, jid)
    return {"id": jid}


@app.get("/api/jobs")
def jobs():
    return store.jobs()


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    return job_required(jid) | {"events": store.events(jid)}


@app.post("/api/jobs/{jid}/approve")
def approve(jid: str):
    if job_required(jid)["status"] != "awaiting_approval":
        raise HTTPException(409, "任务当前不需要审批")
    store.update(jid, "queued")
    pool.submit(execute, jid, True)
    return {"status": "queued"}


@app.post("/api/jobs/{jid}/cancel")
def cancel(jid: str):
    if job_required(jid)["status"] in {"completed", "failed", "cancelled"}:
        raise HTTPException(409, "任务已结束")
    store.update(jid, "cancelled")
    store.emit(jid, {"type": "cancelled", "text": "任务已取消，正在执行的网络调用将在返回后停止。"})
    return {"status": "cancelled"}


@app.get("/api/jobs/{jid}/events")
async def stream(jid: str, request: Request, after: int = 0):
    job_required(jid)
    try:
        cursor = max(after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        raise HTTPException(422, "无效事件编号") from None

    async def generate():
        nonlocal cursor
        while not await request.is_disconnected():
            events = store.events(jid, cursor)
            for event in events:
                cursor = event["id"]
                yield f"id: {cursor}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            status = store.get_job(jid)["status"]
            if status in {"completed", "failed", "cancelled", "awaiting_approval"} and not store.events(jid, cursor):
                yield f"event: done\ndata: {json.dumps({'status': status})}\n\n"
                break
            if not events:
                yield ": heartbeat\n\n"
            await asyncio.sleep(.3)
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/attachments")
async def upload_attachment(file: UploadFile = File(...)):
    data = await file.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024 or not data:
        raise HTTPException(422, "附件应为 1 字节至 8 MB")
    name = Path(file.filename or "attachment").name
    if name.lower().endswith(".csv"):
        try:
            from crabgraph.pond import analyze_csv
            analyze_csv(data.decode("utf-8-sig"))
        except (ValueError, UnicodeError):
            raise HTTPException(422, "CSV 必须为 UTF-8，包含有效养殖记录") from None
        kind, mime = "csv", "text/csv"
    else:
        try:
            image_content(data)
        except (ValueError, OSError) as exc:
            raise HTTPException(422, str(exc)) from None
        kind = "image"
        import io

        from PIL import Image
        mime = Image.MIME[Image.open(io.BytesIO(data)).format]
    aid = str(uuid4())
    meta = {"id": aid, "name": name, "kind": kind, "mime": mime, "size": len(data)}
    (UPLOADS / f"{aid}.bin").write_bytes(data)
    (UPLOADS / f"{aid}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


@app.get("/api/attachments/{aid}")
def uploaded(aid: str):
    meta, data = attachment(aid)
    return Response(data, media_type=meta["mime"], headers={"X-Content-Type-Options": "nosniff"})


@app.get("/api/documents")
def documents(page: int = 1, status: str | None = None):
    if page < 1 or status not in {None, "processed", "pending", "failed", "processing", "preprocessed", "parsing", "analyzing"}:
        raise HTTPException(422, "无效筛选参数")
    return rag("POST", "/documents/paginated", json={"page": page, "page_size": 20, "status_filter": status})


@app.post("/api/documents/upload")
async def document_upload(file: UploadFile = File(...)):
    name = Path(file.filename or "file").name
    if Path(name).suffix.lower() not in {".pdf", ".txt", ".md", ".docx"}:
        raise HTTPException(422, "支持 PDF、TXT、Markdown、DOCX")
    data = await file.read(20 * 1024 * 1024 + 1)
    if not data or len(data) > 20 * 1024 * 1024:
        raise HTTPException(422, "单文件应小于 20 MB")
    return await asyncio.to_thread(rag, "POST", "/documents/upload", files={"file": (name, data, file.content_type or mimetypes.guess_type(name)[0])})


@app.get("/api/graph/labels")
def labels():
    return rag("GET", "/graph/label/popular", params={"limit": 40})


@app.get("/api/graph")
def graph(label: str = "青蟹", depth: int = 2, max_nodes: int = 300):
    if not label.strip() or len(label) > 200 or depth not in {1, 2, 3} or not 50 <= max_nodes <= 1000:
        raise HTTPException(422, "图谱查询参数无效")
    return rag("GET", "/graphs", params={"label": label, "max_depth": depth, "max_nodes": max_nodes})


@app.get("/api/graph/stats")
def graph_totals():
    return graph_stats()


class ToolPreference(BaseModel):
    enabled: bool


@app.get("/api/tool-store")
def tool_store():
    return {"tools": catalog(store), "scope": "本地工作空间", "sdk_source": "https://github.com/modelcontextprotocol/python-sdk", "ecosystem_source": "https://github.com/modelcontextprotocol/servers"}


@app.put("/api/tool-store/{tool_id}")
def set_tool(tool_id: str, body: ToolPreference):
    definition = next((t for t in CATALOG if t["id"] == tool_id), None)
    if not definition:
        raise HTTPException(404, "工具不存在")
    if definition.get("locked") and not body.enabled:
        raise HTTPException(409, "知识检索是核心能力，需要保持启用")
    store.set_tool(tool_id, body.enabled)
    return {"tools": catalog(store)}


class ProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=60)


class ItemPreference(BaseModel):
    pinned: bool = False
    project_id: str | None = None


@app.get("/api/projects")
def projects():
    return store.projects()


@app.post("/api/projects")
def create_project(body: ProjectRequest):
    if not body.title.strip():
        raise HTTPException(422, "请输入项目名称")
    return {"id": store.project(body.title.strip())}


@app.put("/api/sidebar/{kind}/{item_id}")
def sidebar_preference(kind: str, item_id: str, body: ItemPreference):
    if kind == "project" and item_id in {p["id"] for p in store.projects()}:
        store.pin_project(item_id, body.pinned)
    elif kind == "session" and item_id in {s["id"] for s in store.sessions()}:
        if body.project_id and body.project_id not in {p["id"] for p in store.projects()}:
            raise HTTPException(404, "项目不存在")
        store.session_preference(item_id, body.project_id, body.pinned)
    else:
        raise HTTPException(404, "项目或对话不存在")
    return {"ok": True}


@app.get("/api/metrics")
def metrics():
    path = ROOT / "runtime" / "metrics.sqlite"
    if not path.exists():
        return []
    with sqlite3.connect(path) as db:
        return [json.loads(r[0]) for r in db.execute("SELECT payload FROM runs ORDER BY created DESC LIMIT 100")]


@app.get("/api/jobs/{jid}/report")
def report(jid: str, format: str = "md"):
    job = job_required(jid)
    if job["status"] != "completed":
        raise HTTPException(409, "请等待任务完成")
    if format not in {"md", "pdf"}:
        raise HTTPException(422, "支持 md 或 pdf")
    result = job["result"]
    text = result["answer"] + "\n\n## 来源\n" + "\n".join(
        f"- [{s['id']}] {Path(s.get('file_path', '')).name}" for s in result.get("sources", []))
    if format == "md":
        return Response(text.encode("utf-8"), media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="crabgraph-report.md"'})
    from crabgraph.reports import pdf_report
    data = pdf_report(text)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="crabgraph-report.pdf"'})


dist = ROOT / "frontend" / "dist"
app.mount("/guide", StaticFiles(directory=ROOT / "docs", html=True), name="project-guide")
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
