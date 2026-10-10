"""Record retrieval diagnostics; these are not answer-accuracy measurements."""
import argparse
import json
import statistics
import time
from pathlib import Path

from crabgraph.retrieval import LightRAGClient
from crabgraph.settings import ROOT, Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=ROOT / "examples" / "eval_questions.json")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    if args.limit:
        questions = questions[:args.limit]
    settings = Settings.from_env()
    client = LightRAGClient(settings.lightrag_url, settings.lightrag_api_key)
    rows = []
    for question in questions:
        for mode in ("naive", "mix"):
            started = time.perf_counter()
            try:
                result = client.search(question["question"], mode)
                data = result["data"]
                rows.append({"id": question["id"], "mode": mode, "success": True,
                             "seconds": round(time.perf_counter() - started, 3),
                             "chunks": len(data.get("chunks", [])), "references": len(data.get("references", [])),
                             "entities": len(data.get("entities", [])), "relationships": len(data.get("relationships", []))})
            except Exception as exc:
                rows.append({"id": question["id"], "mode": mode, "success": False, "error": type(exc).__name__})
    summary = {}
    for mode in ("naive", "mix"):
        subset = [r for r in rows if r["mode"] == mode]
        good = [r for r in subset if r["success"]]
        summary[mode] = {"queries": len(subset), "successful": len(good),
                         "with_chunks": sum(r["chunks"] > 0 for r in good),
                         "median_seconds": statistics.median(r["seconds"] for r in good) if good else None}
    payload = {"note": "检索诊断；无人工标注 gold answer，不能推导准确率、召回率或幻觉降低幅度。小样本不代表稳定性能。",
               "summary": summary, "results": rows}
    output = ROOT / "research" / "retrieval_evaluation.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
