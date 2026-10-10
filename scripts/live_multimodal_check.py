import json
import time

import httpx

from crabgraph.settings import ROOT

if __name__ == "__main__":
    client = httpx.Client(base_url="http://127.0.0.1:8503/api", timeout=40, trust_env=False)
    image = client.post("/attachments", files={"file": ("crab-illustration.png", (ROOT / "examples" / "crab-illustration.png").read_bytes(), "image/png")})
    image.raise_for_status()
    csv = client.post("/attachments", files={"file": ("pond_records.csv", (ROOT / "examples" / "pond_records.csv").read_bytes(), "text/csv")})
    csv.raise_for_status()
    sid = client.post("/sessions").json()["id"]
    job = client.post("/chat", json={"session_id": sid,
                     "question": "这是青蟹示意插画，并非现场照片。请描述可见图形，并调用工具统计上传的 CSV。区分插画观察、记录统计与文献结论，不将示例数据作为实时水质。",
                     "mode": "pgvector", "image_id": image.json()["id"], "csv_id": csv.json()["id"]})
    job.raise_for_status()
    jid = job.json()["id"]
    for _ in range(180):
        value = client.get(f"/jobs/{jid}").json()
        if value["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(1)
    result = value.get("result") or {}
    evidence = {"job": jid, "session": sid, "status": value["status"], "sources": len(result.get("sources", [])),
                "metrics": result.get("metrics"), "fixture": "Project SVG illustration and synthetic pond CSV; protocol/tool test, not visual accuracy evaluation"}
    (ROOT / "docs" / "multimodal-validation.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    if value["status"] != "completed" or "analyze_pond_records" not in result.get("metrics", {}).get("tool_calls", []):
        raise RuntimeError("Multimodal/tool integration did not complete")
