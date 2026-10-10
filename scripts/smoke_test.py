"""Exercise the migrated service and the configured DeepSeek gateway."""
import argparse
import io
import json
import time
from pathlib import Path
from uuid import uuid4

from PIL import Image

from crabgraph.agent import answer_events, create_model
from crabgraph.multimodal import observe_image
from crabgraph.retrieval import LightRAGClient
from crabgraph.settings import ROOT, Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-model", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    client = LightRAGClient(settings.lightrag_url, settings.lightrag_api_key)
    health = client.health()
    expected = (ROOT / "runtime" / "lightrag" / "rag_storage").resolve()
    assert Path(health["working_directory"]).resolve() == expected, "Service is not the migrated copy"
    started = time.perf_counter()
    retrieved = client.search("青蟹养殖水质管理需要关注哪些指标？", keyword_bypass=True)
    data = retrieved["data"]
    report = {"lightrag_version": health.get("core_version"), "isolated_copy": True,
              "retrieval_seconds": round(time.perf_counter() - started, 2),
              "counts": {k: len(data.get(k, [])) for k in ("chunks", "entities", "relationships", "references")},
              "model": settings.model, "live_deepseek": False}
    if args.live_model:
        result = None
        csv_text = (ROOT / "examples" / "pond_records.csv").read_text(encoding="utf-8")
        for event in answer_events(settings, "smoke-" + str(uuid4()),
                                   "青蟹养殖水质管理需要关注哪些指标？请调用 analyze_pond_records 分析本轮上传的记录，区分统计结果与文献建议。",
                                   pond_csv=csv_text):
            if event["type"] == "result":
                result = event
        assert result and result["answer"], "No grounded answer"
        assert result["sources"], "No citable source retrieved"
        assert not result["metrics"]["invalid_citations"], "Model fabricated a citation"
        assert "analyze_pond_records" in result["metrics"]["tool_calls"], "Business tool was not invoked"
        report.update(live_deepseek=True, answer_chars=len(result["answer"]), sources=len(result["sources"]),
                      metrics=result["metrics"])
        # Synthetic fixture tests transport/vision capability, not biological image recognition accuracy.
        image = io.BytesIO()
        Image.new("RGB", (64, 64), color="gray").save(image, format="PNG")
        try:
            observation = observe_image(create_model(settings, vision=True), image.getvalue(), "描述可见内容")
            report["vision_transport"] = bool(observation)
        except Exception as exc:
            report["vision_transport"] = False
            report["vision_error_type"] = type(exc).__name__
    (ROOT / "research" / "smoke_test.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
