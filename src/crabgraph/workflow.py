"""A checkpointed plan/approval/research/report LangGraph."""
import json
import sqlite3
import time
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from crabgraph.agent import SYSTEM_PROMPT, create_model
from crabgraph.pond import analyze_csv
from crabgraph.retrieval import Evidence, LightRAGClient, sanitize_citations
from crabgraph.settings import ROOT


class Plan(BaseModel):
    title: str = Field(max_length=100)
    queries: list[str] = Field(min_length=1, max_length=3)
    approach: str = Field(max_length=1200)


class ResearchState(TypedDict, total=False):
    goal: str
    review_plan: bool
    plan: dict
    sources: list
    chunks: list
    entities: list
    relationships: list
    statistics: dict
    report: str
    invalid_citations: list
    usage: dict


class Cancelled(Exception):
    pass


def run_research(settings, store, jid, resume=False, pond_csv=None):
    job = store.get_job(jid)
    model = create_model(settings, max_tokens=3500)

    def check():
        if store.get_job(jid)["status"] == "cancelled":
            raise Cancelled()

    def stage(text):
        check()
        store.emit(jid, {"type": "stage", "text": text})

    def planner(state):
        stage("规划研究问题与检索步骤")
        plan = model.with_structured_output(Plan, method="function_calling").invoke([
            SystemMessage(content="你是青蟹业务研究规划员。将用户目标拆成最多3个独立检索问题。只规划可从知识库查证的内容，资料不足须说明。"),
            HumanMessage(content=state["goal"])])
        store.emit(jid, {"type": "plan", "plan": plan.model_dump()})
        return {"plan": plan.model_dump()}

    def approval(state):
        if state.get("review_plan"):
            approved = interrupt({"plan": state["plan"], "message": "请确认研究计划"})
            if approved is not True:
                raise Cancelled()
        stage("研究计划已确认")
        return {}

    def research(state):
        evidence = Evidence()
        client = LightRAGClient(settings.lightrag_url, settings.lightrag_api_key, use_graph=settings.knowledge_graph_enabled)
        for i, query in enumerate(state["plan"]["queries"]):
            stage(f"检索 {i + 1}/{len(state['plan']['queries'])}：{query}")
            evidence.merge(client.search(query, "mix" if settings.knowledge_graph_enabled else "naive")["data"])
            store.emit(jid, {"type": "retrieval", "query": query, "chunks": len(evidence.chunks), "sources": len(evidence.sources)})
        stats = {}
        if pond_csv:
            stage("分析用户上传的养殖记录")
            stats = analyze_csv(pond_csv)
        return {"sources": evidence.sources, "chunks": evidence.chunks, "entities": evidence.entities,
                "relationships": evidence.relationships, "statistics": stats}

    def compose(state):
        stage("基于证据撰写研究报告")
        evidence = Evidence()
        evidence.sources, evidence.chunks = state["sources"], state["chunks"]
        evidence.entities, evidence.relationships = state["entities"], state["relationships"]
        if not evidence.sources:
            return {"report": "# 资料不足\n\n没有检索到可引用原文，无法完成研究结论。请补充业务资料。", "usage": {}}
        chunks, usage, finish_reason = [], {}, None
        prompt = ("研究目标：" + state["goal"] + "\n按研究报告格式回答，包含摘要、主要发现、证据与局限、可执行的核实建议。重要结论必须标注来源。"
                  + "\n<retrieval_data>" + evidence.context() + "</retrieval_data>\n<statistics>"
                  + json.dumps(state.get("statistics", {}), ensure_ascii=False) + "</statistics>")
        for chunk in model.stream([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]):
            check()
            if isinstance(chunk.content, str) and chunk.content:
                chunks.append(chunk.content)
                store.emit(jid, {"type": "token", "text": chunk.content})
            if chunk.usage_metadata:
                usage = chunk.usage_metadata
            finish_reason = chunk.response_metadata.get("finish_reason", finish_reason)
        if finish_reason == "length":
            raise RuntimeError("研究报告超过输出限制，请缩小研究目标后重试。")
        return {"report": "".join(chunks), "usage": usage}

    def verify(state):
        stage("检查引用编号并保存报告")
        report, invalid = sanitize_citations(state["report"], state["sources"])
        # This checks source existence, not semantic entailment or agronomic accuracy.
        return {"report": report, "invalid_citations": invalid}

    builder = StateGraph(ResearchState)
    for name, fn in [("plan", planner), ("approval", approval), ("research", research), ("compose", compose), ("verify", verify)]:
        builder.add_node(name, fn)
    for a, b in [(START, "plan"), ("plan", "approval"), ("approval", "research"), ("research", "compose"), ("compose", "verify"), ("verify", END)]:
        builder.add_edge(a, b)
    started = time.perf_counter()
    with sqlite3.connect(ROOT / "runtime" / "research-checkpoints.sqlite", check_same_thread=False) as conn:
        graph = builder.compile(checkpointer=SqliteSaver(conn))
        state = graph.invoke(Command(resume=True) if resume else {
            "goal": job["payload"]["goal"], "review_plan": job["payload"].get("review_plan", True)},
            {"configurable": {"thread_id": jid}, "recursion_limit": 12})
    check()
    if "__interrupt__" in state:
        result = {"plan": state["plan"]}
        store.update(jid, "awaiting_approval", result)
        store.emit(jid, {"type": "awaiting_approval", **result})
        return
    result = {"answer": state["report"], "sources": state.get("sources", []),
              "evidence": [{"source_id": c["source_id"], "content": c["content"]} for c in state.get("chunks", [])],
              "plan": state["plan"], "statistics": state.get("statistics", {}),
              "metrics": {"elapsed_ms": round((time.perf_counter() - started) * 1000),
                          "model": settings.model, "invalid_citations": state["invalid_citations"],
                          **state.get("usage", {})}}
    store.finish(jid, result)
