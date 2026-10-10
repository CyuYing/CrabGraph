import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from crabgraph import api, workflow
from crabgraph.settings import Settings
from crabgraph.store import Store


def test_session_exclusion_and_event_replay(tmp_path):
    store = Store(tmp_path / "test.sqlite")
    sid = store.session()
    first = store.job("chat", {"question": "test"}, sid)
    import pytest
    with pytest.raises(ValueError):
        store.job("chat", {}, sid)
    a = store.emit(first, {"type": "stage", "text": "retrieval"})
    b = store.emit(first, {"type": "token", "text": "evidence"})
    assert store.events(first, a) == [{"id": b, "type": "token", "text": "evidence"}]
    store.recover()
    assert store.get_job(first)["status"] == "failed"


@pytest.mark.parametrize("graph_enabled", [True, False])
def test_approval_resumes_checkpoint_without_replanning(tmp_path, monkeypatch, graph_enabled):
    calls = []

    class Model:
        def with_structured_output(self, *args, **kwargs):
            return self

        def invoke(self, messages):
            calls.append("plan")
            return workflow.Plan(title="水质研究", queries=["青蟹水质管理"], approach="先检索再整理")

        def stream(self, messages):
            yield AIMessageChunk(content="结论有据 [S1]，无效引用 [S99]。")

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, query, mode):
            assert mode == ("mix" if graph_enabled else "naive")
            calls.append("search")
            return {"data": {"chunks": [{"content": "青蟹资料", "chunk_id": "c1", "file_path": "paper.pdf"}]}}

    monkeypatch.setattr(workflow, "create_model", lambda _, **kwargs: Model())
    monkeypatch.setattr(workflow, "LightRAGClient", Client)
    monkeypatch.setattr(workflow, "ROOT", tmp_path)
    store = Store(tmp_path / "runtime" / "test.sqlite")
    jid = store.job("research", {"goal": "青蟹水质研究", "review_plan": True})
    settings = Settings(knowledge_graph_enabled=graph_enabled)
    workflow.run_research(settings, store, jid)
    assert store.get_job(jid)["status"] == "awaiting_approval"
    assert calls == ["plan"]
    workflow.run_research(settings, store, jid, resume=True)
    result = store.get_job(jid)
    assert calls == ["plan", "search"]
    assert result["status"] == "completed"
    assert result["result"]["metrics"]["invalid_citations"] == ["S99"]
    assert "[S99]" not in result["result"]["answer"]


def test_api_rejects_original_service_private_origins_and_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "store", Store(tmp_path / "api.sqlite"))
    with TestClient(api.app) as client:
        assert client.post("/api/sessions", headers={"Origin": "https://untrusted.example"}).status_code == 403
        assert client.get("/api/attachments/not-a-uuid").status_code == 404
        assert client.post("/api/chat", json={"session_id": "unknown", "question": "青蟹"}).status_code == 404
        config = client.get("/api/config").json()
        assert "api_key" not in config
        monkeypatch.setattr(api, "settings", Settings(lightrag_url="http://127.0.0.1:9621"))
        assert client.get("/api/documents").status_code == 503


def test_serverless_adapter_health_event(monkeypatch):
    from crabgraph.serverless import handler
    event = {"version": "2.0", "routeKey": "GET /api/health", "rawPath": "/api/health", "rawQueryString": "",
             "headers": {"host": "127.0.0.1"}, "requestContext": {"http": {
                 "method": "GET", "path": "/api/health", "protocol": "HTTP/1.1", "sourceIp": "127.0.0.1"}},
             "isBase64Encoded": False}
    response = handler(event, SimpleNamespace())
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["service"] == "crabgraph-workbench"
