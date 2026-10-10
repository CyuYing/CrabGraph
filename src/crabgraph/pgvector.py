"""Jina query embedding plus real PostgreSQL cosine distance on a copied index."""
import httpx
from dotenv import dotenv_values

from crabgraph.settings import ROOT


def search_pgvector(query: str) -> dict:
    config = dotenv_values(ROOT / "runtime" / "lightrag" / ".env")
    with httpx.Client(timeout=40) as client:
        response = client.post(config["EMBEDDING_BINDING_HOST"],
                               headers={"Authorization": "Bearer " + config["EMBEDDING_BINDING_API_KEY"]},
                               json={"model": config["EMBEDDING_MODEL"], "input": [query],
                                     "task": "retrieval.query", "embedding_type": "float"})
        response.raise_for_status()
        embedding = response.json()["data"][0]["embedding"]
        result = client.post("http://127.0.0.1:8510/search", json={"embedding": embedding, "limit": 6})
        result.raise_for_status()
    return {"data": {"chunks": result.json()["chunks"], "references": [], "entities": [], "relationships": []},
            "metadata": {"engine": "PostgreSQL pgvector", "snapshot": True}}
