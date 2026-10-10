"""Copy existing embeddings without re-embedding or touching the original instance."""
import json

from nano_vectordb.dbs import buffer_string_to_array

from crabgraph.settings import ROOT

if __name__ == "__main__":
    source = ROOT / "runtime" / "lightrag" / "rag_storage" / "vdb_chunks.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    matrix = buffer_string_to_array(data["matrix"]).reshape(-1, data["embedding_dim"])
    rows = [{"id": meta["__id__"], "file_path": meta.get("file_path", ""),
             "content": meta.get("content", ""), "vector": matrix[i].tolist()} for i, meta in enumerate(data["data"])]
    target = ROOT / "runtime" / "pgvector-seed.json"
    target.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Prepared {len(rows)} copied vectors of dimension {data['embedding_dim']}")
