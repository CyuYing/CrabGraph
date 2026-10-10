import json
import sqlite3
from dataclasses import replace
from uuid import uuid4

import streamlit as st

from crabgraph.agent import answer_events
from crabgraph.pond import analyze_csv
from crabgraph.retrieval import MODES, Evidence, LightRAGClient
from crabgraph.settings import ROOT, Settings

st.set_page_config(page_title="CrabGraph · 青蟹知识助手", page_icon="🦀", layout="wide")
st.title("🦀 CrabGraph · 青蟹多模态知识助手")
st.caption("图像观察 · 图谱与原文检索 · 证据回答 · 养殖记录分析")


def show_result(result):
    if result.get("observation"):
        with st.expander("图片观察结果"):
            st.write(result["observation"])
    with st.expander("检索原文与引用依据", expanded=False):
        sources = {s["id"]: s for s in result.get("sources", [])}
        for chunk in result.get("evidence", []):
            source = sources.get(chunk["source_id"], {})
            st.markdown(f"**[{chunk['source_id']}]**")
            st.caption(source.get("file_path", "来源未标注"))
            st.text(chunk["content"])
        if not result.get("evidence"):
            st.info("本次检索没有获得原文片段。")
    with st.expander("知识图谱证据与运行指标"):
        if result.get("entities"):
            st.dataframe(result["entities"], use_container_width=True)
        if result.get("relationships"):
            st.dataframe(result["relationships"], use_container_width=True)
        st.json(result.get("metrics", {}))


settings = Settings.from_env()
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())
    st.session_state.messages = []

with st.sidebar:
    st.header("连接配置")
    key = st.text_input("DeepSeek API Key", value=settings.api_key, type="password",
                        help="仅在本地进程会话中使用；不写入运行日志。可在 .env 配置以持久保存。")
    base_url = st.text_input("模型接口地址", value=settings.base_url)
    model_name = st.text_input("回答模型", value=settings.model)
    vision_model = st.text_input("图片观察模型", value=settings.vision_model)
    rag_url = st.text_input("迁移副本接口", value=settings.lightrag_url)
    rag_key = st.text_input("LightRAG API Key（可选）", value=settings.lightrag_api_key, type="password")
    mode = st.selectbox("检索策略", MODES, help="mix 为图谱+向量；naive 为纯向量，可用来做对照。")
    settings = replace(settings, api_key=key, base_url=base_url, model=model_name,
                       vision_model=vision_model, lightrag_url=rag_url, lightrag_api_key=rag_key)
    if st.button("检查副本服务"):
        try:
            info = LightRAGClient(rag_url, rag_key).health()
            st.success("LightRAG " + str(info.get("core_version", "")) + " 已连接")
            st.caption("独立副本：" + str(info.get("working_directory", "")))
        except Exception:
            st.error("无法访问副本。请先运行 start.ps1，再检查鉴权。")
    st.divider()
    image = st.file_uploader("上传青蟹或养殖现场图片", type=["png", "jpg", "jpeg", "webp"])
    if image:
        st.image(image, caption="本轮图片")
    csv_file = st.file_uploader("上传养殖记录 CSV", type=["csv"])
    pond_csv = None
    if csv_file:
        try:
            if csv_file.size > 1024**2:
                raise ValueError("CSV 最大 1 MB")
            pond_csv = csv_file.getvalue().decode("utf-8-sig")
            st.json(analyze_csv(pond_csv))
        except (ValueError, UnicodeDecodeError) as exc:
            st.error(str(exc))
            pond_csv = None
    if st.button("新建会话"):
        st.session_state.session_id = str(uuid4())
        st.session_state.messages = []
        st.rerun()
    st.caption("会话 ID：" + st.session_state.session_id)

chat_tab, retrieval_tab, history_tab, metrics_tab = st.tabs(["知识问答", "检索对照", "历史会话", "运行数据"])
with chat_tab:
    if not key:
        st.info("填写 DeepSeek Key 即可开始图文问答。也可先在「检索对照」验证现有青蟹知识库。")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("result"):
                show_result(message["result"])
    question = st.chat_input("描述你的青蟹问题，例如：摄食减少，需要检查哪些水质和行为信息？", disabled=not bool(key))
    if question:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            status = st.empty()
            response_box = st.empty()
            streamed = ""
            result = None
            try:
                for event in answer_events(settings, st.session_state.session_id, question, mode,
                                           image.getvalue() if image else None, pond_csv):
                    if event["type"] == "stage":
                        status.caption(event["text"])
                    elif event["type"] == "token":
                        streamed += event["text"]
                        response_box.markdown(streamed + " ▌")
                    elif event["type"] == "result":
                        result = event
                if result:
                    response_box.markdown(result["answer"])
                    status.empty()
                    show_result(result)
                    st.session_state.messages.extend([{"role": "user", "content": question},
                                                       {"role": "assistant", "content": result["answer"], "result": result}])
                    export = result["answer"] + "\n\n" + "\n".join(
                        f"[{s['id']}] {s['file_path']}" for s in result["sources"])
                    st.download_button("导出本轮答案", export, "crabgraph-answer.md")
            except Exception as exc:
                status.empty()
                response_box.empty()
                # Do not expose request headers, credentials, or provider response bodies.
                if isinstance(exc, ValueError):
                    st.error(str(exc))
                else:
                    st.error("本轮未完成（" + type(exc).__name__ + "）。请检查 Key、模型权限、副本服务和网络后重试。")

with retrieval_tab:
    st.write("使用相同问题比较纯向量检索与图谱检索。这里展示原文，不调用回答模型。")
    query = st.text_input("检索问题", "青蟹养殖水质管理需要关注哪些指标？")
    if st.button("检索原文"):
        try:
            with st.spinner("检索中"):
                payload = LightRAGClient(rag_url, rag_key).search(query, mode)
            evidence = Evidence()
            evidence.merge(payload["data"])
            show_result({"sources": evidence.sources, "evidence": evidence.chunks,
                         "entities": evidence.entities, "relationships": evidence.relationships,
                         "metrics": payload.get("metadata", {})})
        except Exception as exc:
            st.error("检索失败：" + type(exc).__name__)
    st.download_button("下载养殖记录示例（虚构演示数据）", (ROOT / "examples" / "pond_records.csv").read_bytes(), "pond_records.csv")

with history_tab:
    st.caption("会话存储在本地 SQLite，刷新页面后可输入原会话 ID 继续。")
    resume_id = st.text_input("恢复会话 ID")
    if st.button("恢复会话") and resume_id:
        import sqlite3 as sqlite_module

        from langgraph.checkpoint.sqlite import SqliteSaver
        db = ROOT / "runtime" / "conversations.sqlite"
        if not db.exists():
            st.info("还没有已保存的会话。")
        else:
            try:
                with sqlite_module.connect(db, check_same_thread=False) as conn:
                    checkpoint = SqliteSaver(conn).get({"configurable": {"thread_id": resume_id}})
                if not checkpoint:
                    st.warning("没有找到该会话。")
                else:
                    restored = []
                    for msg in checkpoint["channel_values"].get("messages", []):
                        if msg.type == "human":
                            restored.append({"role": "user", "content": str(msg.content).split("\n\n<retrieval_data>")[0]})
                        elif msg.type == "ai" and not msg.tool_calls and msg.content:
                            restored.append({"role": "assistant", "content": msg.content})
                    st.session_state.session_id = resume_id
                    st.session_state.messages = restored
                    st.rerun()
            except Exception:
                st.error("无法读取会话。")

with metrics_tab:
    path = ROOT / "runtime" / "metrics.sqlite"
    if path.exists():
        with sqlite3.connect(path) as conn:
            rows = conn.execute("SELECT payload FROM runs ORDER BY created DESC LIMIT 100").fetchall()
        data = [json.loads(row[0]) for row in rows]
        st.dataframe(data, use_container_width=True)
        st.download_button("导出真实运行指标", json.dumps(data, ensure_ascii=False, indent=2), "run-metrics.json")
    else:
        st.info("完成问答后记录耗时、token 数、检索片段数和工具调用。未测得的数据不展示为项目成绩。")
