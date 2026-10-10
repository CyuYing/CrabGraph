import sqlite3

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.sqlite import SqliteSaver

from crabgraph.agent import build_agent
from crabgraph.retrieval import Evidence


class ScriptedModel(BaseChatModel):
    calls: int = 0

    @property
    def _llm_type(self):
        return "offline-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        if messages[-1].type == "human":
            msg = AIMessage(content="", tool_calls=[{"name": "search_knowledge", "args": {"query": "青蟹水质"},
                                                     "id": "search-" + str(self.calls), "type": "tool_call"}])
        else:
            msg = AIMessage(content="依据本轮原文回答 [S1]。")
        return ChatResult(generations=[ChatGeneration(message=msg)])


class FakeRetrieval:
    def search(self, query, mode):
        return {"data": {"chunks": [{"content": "测试青蟹文档", "file_path": "crab.pdf", "chunk_id": "c1"}]}}


def test_tools_execute_and_sessions_persist_without_cross_talk(tmp_path):
    db = tmp_path / "history.sqlite"
    config = {"configurable": {"thread_id": "session-a"}}
    evidence = Evidence()
    with sqlite3.connect(db, check_same_thread=False) as conn:
        agent = build_agent(ScriptedModel(), FakeRetrieval(), evidence, SqliteSaver(conn))
        result = agent.invoke({"messages": [HumanMessage(content="青蟹水质")]}, config)
        assert result["messages"][-1].content.endswith("[S1]。")
        assert len(evidence.sources) == 1
    with sqlite3.connect(db, check_same_thread=False) as conn:
        rebuilt = build_agent(ScriptedModel(), FakeRetrieval(), Evidence(), SqliteSaver(conn))
        assert len(rebuilt.get_state(config).values["messages"]) >= 4
        other = {"configurable": {"thread_id": "session-b"}}
        assert not rebuilt.get_state(other).values.get("messages")
