from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

MODES = ("mix", "hybrid", "local", "global", "naive", "pgvector")


class RetrievalError(RuntimeError):
    pass


@dataclass
class Evidence:
    sources: list[dict] = field(default_factory=list)
    chunks: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)

    def merge(self, data: dict) -> None:
        refs = {str(r.get("reference_id", "")): r for r in data.get("references", [])}
        known = {(s["file_path"], s.get("chunk_id", "")): s["id"] for s in self.sources}
        for chunk in data.get("chunks", []):
            reference = refs.get(str(chunk.get("reference_id", "")), {})
            path = chunk.get("file_path") or reference.get("file_path") or "未标注来源"
            chunk_id = chunk.get("chunk_id", "")
            key = (path, chunk_id or chunk.get("content", ""))
            # Deduplicate by actual content when a server omits chunk_id.
            duplicate = next((c for c in self.chunks if c.get("key") == key), None)
            if duplicate:
                continue
            source_id = known.get((path, chunk_id)) or f"S{len(self.sources) + 1}"
            if source_id not in {s["id"] for s in self.sources}:
                self.sources.append({"id": source_id, "file_path": path, "chunk_id": chunk_id})
                known[(path, chunk_id)] = source_id
            self.chunks.append({"source_id": source_id, "content": chunk.get("content", ""), "key": key})
        for category in ("entities", "relationships"):
            target = getattr(self, category)
            for item in data.get(category, [])[:20]:
                if item not in target:
                    target.append(item)

    def context(self, max_chars: int = 20000) -> str:
        parts = [f"[{c['source_id']}] {c['content'][:3500]}" for c in self.chunks[:10]]
        # Graph structure is evidence context, not a similarity/confidence score.
        parts.append("图谱实体与关系（需结合原文核实）：" + json.dumps(
            {"entities": self.entities[:8], "relationships": self.relationships[:8]}, ensure_ascii=False))
        return "\n\n".join(parts)[:max_chars]


class LightRAGClient:
    def __init__(self, base_url: str, api_key: str = "", transport=None, use_graph: bool = True):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key} if api_key else {}
        self.transport = transport
        self.use_graph = use_graph

    def _client(self):
        return httpx.Client(base_url=self.base_url, headers=self.headers,
                            timeout=httpx.Timeout(90, connect=5), transport=self.transport)

    def health(self) -> dict:
        with self._client() as client:
            response = client.get("/health")
            response.raise_for_status()
            return response.json()

    def search(self, question: str, mode: str = "mix", keyword_bypass: bool = False) -> dict:
        if mode not in MODES:
            raise ValueError("Unsupported retrieval mode")
        if not self.use_graph and mode != "pgvector":
            mode = "naive"
        if mode == "pgvector":
            from crabgraph.pgvector import search_pgvector
            try:
                return search_pgvector(question)
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                raise RetrievalError("PGvector 检索失败，请检查 8510 服务与嵌入接口") from exc
        payload: dict[str, Any] = {"query": question, "mode": mode, "top_k": 12, "chunk_top_k": 8,
                                  "max_total_tokens": 14000, "max_entity_tokens": 2000,
                                  "max_relation_tokens": 2000, "enable_rerank": False}
        if keyword_bypass:
            # Used for smoke tests: avoid generating keywords through the original configured LLM.
            payload.update(hl_keywords=["青蟹养殖"], ll_keywords=["青蟹", "养殖", "水质"])
        try:
            with self._client() as client:
                response = client.post("/query/data", json=payload)
                response.raise_for_status()
                result = response.json()
            if result.get("status") != "success":
                raise RetrievalError("LightRAG did not return a successful retrieval result")
            data = result.get("data", {})
            for field_name in ("chunks", "entities", "relationships", "references"):
                if not isinstance(data.get(field_name, []), list):
                    raise RetrievalError("Unexpected LightRAG response schema")
            if not self.use_graph:
                data["entities"], data["relationships"] = [], []
            if mode != "naive" and not data.get("chunks"):
                fallback = self.search(question, "naive", keyword_bypass)
                data["chunks"] = fallback["data"].get("chunks", [])
                data["references"] = fallback["data"].get("references", [])
                result.setdefault("metadata", {})["chunk_fallback"] = "naive"
            return result
        except httpx.HTTPError as exc:
            raise RetrievalError("LightRAG 检索失败，请检查副本服务、鉴权及嵌入接口配置。") from exc


def sanitize_citations(answer: str, sources: list[dict]) -> tuple[str, list[str]]:
    allowed = {s["id"] for s in sources}
    invalid = sorted(set(re.findall(r"\[(S\d+)\]", answer)) - allowed)
    for source in invalid:
        answer = answer.replace(f"[{source}]", "[来源待核实]")
    return answer, invalid
