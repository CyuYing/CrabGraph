"""Reuse only the migrated private gateway credential after checking its model list."""
import json
from pathlib import Path

import httpx
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def main():
    private = ROOT / "runtime" / "lightrag" / ".env"
    values = dotenv_values(private)
    host = values.get("LLM_BINDING_HOST", "").rstrip("/")
    key = values.get("LLM_BINDING_API_KEY") or values.get("OPENAI_API_KEY")
    if not host or not key:
        raise SystemExit("No reusable credential; configure a DeepSeek key in the UI.")
    response = httpx.get(host + "/models", headers={"Authorization": "Bearer " + key}, timeout=20)
    response.raise_for_status()
    models = {m["id"] for m in response.json().get("data", [])}
    selected = next((m for m in ("deepseek-flash", "deepseek-v4-flash", "deepseek-v3.2") if m in models), None)
    if not selected:
        raise SystemExit("Gateway does not advertise a supported DeepSeek model.")
    app_env = ROOT / ".env"
    if not app_env.exists():
        app_env.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    overrides = {"DEEPSEEK_API_KEY": key, "DEEPSEEK_BASE_URL": host, "DEEPSEEK_MODEL": selected,
                 "VISION_MODEL": selected, "LIGHTRAG_URL": "http://127.0.0.1:9622"}
    for name, value in overrides.items():
        set_key(app_env, name, value)
    # Keep embedding provider/model intact: existing vectors cannot use a different embedding space.
    for prefix in ("", "QUERY_", "KEYWORD_"):
        for name, value in {"LLM_BINDING": "openai", "LLM_BINDING_HOST": host,
                            "LLM_BINDING_API_KEY": key, "LLM_MODEL": selected}.items():
            set_key(private, prefix + name, value)
    print(json.dumps({"model": selected, "base_url": host, "credential_reused_locally": True,
                      "source_modified": False}))


if __name__ == "__main__":
    main()
