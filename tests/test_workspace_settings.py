import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from crabgraph import agent, api, model_config
from crabgraph.store import Store
from crabgraph.tool_registry import enabled_ids


def test_workspace_preferences_persist_and_disabled_tools_are_rejected(tmp_path, monkeypatch):
    local = Store(tmp_path / "workspace.sqlite")
    monkeypatch.setattr(api, "store", local)
    with TestClient(api.app) as client:
        sid = client.post("/api/sessions").json()["id"]
        pid = client.post("/api/projects", json={"title": "水质研究"}).json()["id"]
        assert client.put(f"/api/sidebar/session/{sid}", json={"project_id": pid, "pinned": True}).status_code == 200
        assert client.put(f"/api/sidebar/project/{pid}", json={"pinned": True}).status_code == 200
        assert client.put("/api/tool-store/literature", json={"enabled": False}).status_code == 200
        assert client.post("/api/tools", json={"tool": "literature", "input": "Scylla"}).status_code == 403
        assert client.put("/api/tool-store/knowledge", json={"enabled": False}).status_code == 409
        assert client.put("/api/tool-store/unknown", json={"enabled": True}).status_code == 404
        assert client.put(f"/api/sidebar/session/{sid}", json={"project_id": "missing"}).status_code == 404
    reopened = Store(local.path)
    assert "literature" not in enabled_ids(reopened)
    assert reopened.sessions()[0]["project_id"] == pid
    assert reopened.sessions()[0]["pinned"] == 1
    assert reopened.projects()[0]["pinned"] == 1


def test_agent_only_receives_enabled_tools(monkeypatch):
    captured = {}
    monkeypatch.setattr(agent, "create_agent", lambda **kw: captured.update(kw))
    agent.build_agent(None, None, None, None, enabled_tools=["knowledge", "webpage"])
    assert {t.name for t in captured["tools"]} == {"search_knowledge", "fetch_research_page"}


def test_graph_limit_is_forwarded_and_bounds_are_enforced(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "store", Store(tmp_path / "workspace.sqlite"))
    monkeypatch.setattr(api, "rag", lambda *a, **kw: calls.append(kw["params"]) or {"nodes": [], "edges": [], "is_truncated": True})
    with TestClient(api.app) as client:
        response = client.get("/api/graph?label=S.%20serrata&depth=1&max_nodes=300")
        assert response.json()["is_truncated"] is True
        assert calls[-1] == {"label": "S. serrata", "max_depth": 1, "max_nodes": 300}
        assert client.get("/api/graph?max_nodes=1001").status_code == 422
        assert client.get("/api/graph?depth=9").status_code == 422


def test_model_settings_keep_keys_private_and_require_new_endpoint_key(tmp_path, monkeypatch):
    monkeypatch.setattr(model_config, "ROOT", tmp_path)
    monkeypatch.setattr(api, "store", Store(tmp_path / "workspace.sqlite"))
    monkeypatch.setattr(api, "settings", replace(api.settings, base_url="https://old.example/v1", api_key="old-secret"))
    for key in ["DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "VISION_MODEL"]:
        monkeypatch.setenv(key, "old-secret" if key == "DEEPSEEK_API_KEY" else "old-value")
    (tmp_path / ".env").write_text("EMBEDDING_MODEL=unchanged\n", encoding="utf-8")
    with TestClient(api.app) as client:
        body = {"base_url": "https://new.example/v1", "model": "custom-model", "vision_model": "custom-vision"}
        assert client.put("/api/config/model", json=body).status_code == 422
        body["api_key"] = "new-secret"
        response = client.put("/api/config/model", json=body)
        assert response.status_code == 200
        assert response.json()["model"] == "custom-model"
        assert response.json()["key_configured"] is True
        assert "secret" not in json.dumps(response.json())
        assert "secret" not in client.get("/api/config").text
        assert "EMBEDDING_MODEL=unchanged" in (tmp_path / ".env").read_text()
        assert not (tmp_path / ".env.model-config.tmp").exists()
        jid = api.store.job("chat", {})
        assert client.put("/api/config/model", json=body).status_code == 409
        api.store.update(jid, "completed")
        body["base_url"] = "http://remote.example/v1"
        assert client.put("/api/config/model", json=body).status_code == 422
    with pytest.raises(ValueError):
        model_config.save_generation_config("https://new.example/v1", "bad\nmodel", "", "key")


def test_graph_preference_persists_and_jobs_keep_submission_policy(tmp_path, monkeypatch):
    local = Store(tmp_path / "workspace.sqlite")
    monkeypatch.setattr(api, "store", local)
    monkeypatch.setattr(api, "pool", SimpleNamespace(submit=lambda *args: None))
    with TestClient(api.app) as client:
        assert client.get("/api/config").json()["knowledge_graph_enabled"] is True
        assert client.put("/api/config/retrieval", json={"knowledge_graph_enabled": False}).status_code == 200
        sid = client.post("/api/sessions").json()["id"]
        chat = client.post("/api/chat", json={"session_id": sid, "question": "水质管理", "mode": "global"}).json()["id"]
        research = client.post("/api/research", json={"goal": "比较青蟹水质文献"}).json()["id"]
        assert Store(local.path).graph_enabled() is False
        assert local.get_job(chat)["payload"]["mode"] == "naive"
        assert client.put("/api/config/retrieval", json={"knowledge_graph_enabled": True}).status_code == 200
        for jid in [chat, research]:
            assert local.get_job(jid)["payload"]["knowledge_graph_enabled"] is False


def test_execute_uses_saved_graph_policy_after_preference_changes(tmp_path, monkeypatch):
    local = Store(tmp_path / "workspace.sqlite")
    monkeypatch.setattr(api, "store", local)
    local.set_graph_enabled(True)
    seen = []

    def answer(settings, *args, **kwargs):
        seen.append(settings.knowledge_graph_enabled)
        yield {"type": "result", "answer": "原文回答", "sources": []}

    monkeypatch.setattr(api, "answer_events", answer)
    monkeypatch.setattr(api, "run_research", lambda settings, *args: seen.append(settings.knowledge_graph_enabled))
    chat = local.job("chat", {"question": "青蟹", "mode": "naive", "knowledge_graph_enabled": False}, local.session())
    research = local.job("research", {"goal": "青蟹比较", "knowledge_graph_enabled": False})
    api.execute(chat)
    api.execute(research)
    assert seen == [False, False]
