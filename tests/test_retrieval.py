import httpx
import pytest

from crabgraph.retrieval import Evidence, LightRAGClient, RetrievalError, sanitize_citations


def test_client_uses_data_endpoint_and_no_generation():
    def respond(request):
        import json
        assert request.url.path == "/query/data"
        body = json.loads(request.content)
        assert body["mode"] in {"mix", "naive"}
        assert body["ll_keywords"] == ["青蟹", "养殖", "水质"]
        assert body["max_entity_tokens"] + body["max_relation_tokens"] < body["max_total_tokens"]
        return httpx.Response(200, json={"status": "success", "data": {"chunks": []}})
    client = LightRAGClient("http://test", transport=httpx.MockTransport(respond))
    assert client.search("青蟹水质", keyword_bypass=True)["status"] == "success"


def test_errors_do_not_become_empty_success():
    client = LightRAGClient("http://test", transport=httpx.MockTransport(
        lambda request: httpx.Response(500, json={"detail": "private provider response"})))
    with pytest.raises(RetrievalError, match="检索失败"):
        client.search("青蟹水质")


def test_no_citation_can_be_fabricated():
    evidence = Evidence()
    evidence.merge({"chunks": [{"content": "青蟹资料", "chunk_id": "c1", "reference_id": "1"}],
                    "references": [{"reference_id": "1", "file_path": "crab.pdf"}]})
    answer, invalid = sanitize_citations("有依据 [S1]，假来源 [S9]。", evidence.sources)
    assert invalid == ["S9"]
    assert "[S1]" in answer and "[S9]" not in answer
    assert evidence.sources[0]["file_path"] == "crab.pdf"


def test_deduplicates_chunks_and_retains_sources_across_searches():
    evidence = Evidence()
    a = {"content": "first", "chunk_id": "a", "file_path": "a.pdf"}
    b = {"content": "second", "chunk_id": "b", "file_path": "b.pdf"}
    evidence.merge({"chunks": [a]})
    evidence.merge({"chunks": [a, b]})
    assert len(evidence.chunks) == 2
    assert [s["id"] for s in evidence.sources] == ["S1", "S2"]


def test_disabled_graph_forces_text_retrieval_even_for_tool_requested_modes():
    import json
    modes = []

    def respond(request):
        modes.append(json.loads(request.content)["mode"])
        return httpx.Response(200, json={"status": "success", "data": {
            "chunks": [{"content": "原文", "file_path": "crab.pdf"}],
            "entities": [{"name": "青蟹"}], "relationships": [{"source": "青蟹"}]}})

    transport = httpx.MockTransport(respond)
    client = LightRAGClient("http://test", transport=transport, use_graph=False)
    for mode in ["mix", "global", "local", "hybrid", "naive"]:
        data = client.search("青蟹水质", mode)["data"]
        assert data["chunks"][0]["content"] == "原文"
        assert data["entities"] == data["relationships"] == []
    assert modes == ["naive"] * 5
    enabled = LightRAGClient("http://test", transport=transport, use_graph=True)
    assert enabled.search("青蟹水质", "global")["data"]["entities"]
    assert modes[-1] == "global"
