"""Run bounded real-provider checks and persist evidence without any credentials."""
import asyncio
import hashlib
import json
import time

import httpx

from crabgraph.business_tools import read_public_page, search_literature
from crabgraph.mcp_client import inspect_mcp
from crabgraph.settings import ROOT


def wait_job(client, jid, expected, seconds=180):
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        job = client.get(f"/jobs/{jid}").json()
        if job["status"] in expected:
            return job
        if job["status"] in {"failed", "cancelled"}:
            raise RuntimeError(f"Job {jid} failed")
        time.sleep(1)
    raise TimeoutError("Job timed out")


if __name__ == "__main__":
    client = httpx.Client(base_url="http://127.0.0.1:8503/api", timeout=50, trust_env=False)
    overview = client.get("/overview")
    overview.raise_for_status()
    sid = client.post("/sessions").json()["id"]
    chat = client.post("/chat", json={"session_id": sid, "question": "青蟹水质管理需要关注哪些信息？请依据资料回答，并明确需要现场核实的内容。", "mode": "mix"})
    chat.raise_for_status()
    chat_job = wait_job(client, chat.json()["id"], {"completed"})
    print(json.dumps({"chat": "completed", "source_count": len(chat_job["result"]["sources"]), "metrics": chat_job["result"]["metrics"]}, ensure_ascii=False), flush=True)
    research = client.post("/research", json={"goal": "根据现有青蟹文献，整理水质管理的关键关注点与需要现场核实的信息。请区分文献结论和建议。", "review_plan": True})
    research.raise_for_status()
    jid = research.json()["id"]
    planned = wait_job(client, jid, {"awaiting_approval"})
    print(json.dumps({"research_plan": planned["result"]["plan"]}, ensure_ascii=False), flush=True)
    client.post(f"/jobs/{jid}/approve").raise_for_status()
    final = wait_job(client, jid, {"completed"}, 240)
    pdf = client.get(f"/jobs/{jid}/report", params={"format": "pdf"})
    pdf.raise_for_status()
    (ROOT / "docs" / "research-demo.pdf").write_bytes(pdf.content)
    mcp = asyncio.run(inspect_mcp())
    manifest = json.loads((ROOT / "research" / "migration_manifest.json").read_text(encoding="utf-8"))
    unchanged = []
    for filename, meta in manifest["storage_files"].items():
        path = __import__("pathlib").Path(manifest["source_storage"]) / filename
        with path.open("rb") as file:
            unchanged.append(hashlib.file_digest(file, "sha256").hexdigest() == meta["sha256"])
    evidence = {"date": "2026-10-10", "chat_job": chat_job["id"], "chat_session": sid,
                "chat_sources": len(chat_job["result"]["sources"]), "chat_metrics": chat_job["result"]["metrics"],
                "research_job": jid, "research_sources": len(final["result"]["sources"]), "research_plan": final["result"]["plan"],
                "research_metrics": final["result"]["metrics"], "pdf_bytes": len(pdf.content),
                "mcp_tools": mcp["tools"], "mcp_csv_rows": mcp["statistics"]["rows"],
                "public_literature_results": len(search_literature("Scylla paramamosain aquaculture")),
                "public_page_chars": len(read_public_page("https://en.wikipedia.org/wiki/Scylla_paramamosain")["content"]),
                "pgvector": httpx.get("http://127.0.0.1:8510/health", trust_env=False).json(),
                "original_storage_matches_snapshot": all(unchanged), "original_storage_files_checked": len(unchanged)}
    (ROOT / "docs" / "live-validation.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False), flush=True)
