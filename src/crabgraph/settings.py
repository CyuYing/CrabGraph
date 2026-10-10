import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    vision_model: str = "deepseek-flash"
    lightrag_url: str = "http://127.0.0.1:9622"
    lightrag_api_key: str = ""
    enable_rerank: bool = False
    knowledge_graph_enabled: bool = True

    @classmethod
    def from_env(cls):
        return cls(api_key=os.getenv("DEEPSEEK_API_KEY", ""),
                   base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                   model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
                   vision_model=os.getenv("VISION_MODEL", "deepseek-flash"),
                   lightrag_url=os.getenv("LIGHTRAG_URL", "http://127.0.0.1:9622"),
                   lightrag_api_key=os.getenv("LIGHTRAG_API_KEY", ""),
                   enable_rerank=os.getenv("ENABLE_RERANK", "false").lower() == "true")
