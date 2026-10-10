"""OpenAI-compatible generation settings; embedding/index settings are separate."""
import os
from urllib.parse import urlsplit

from dotenv import set_key

from crabgraph.settings import ROOT, Settings

PRESETS = [
    dict(id="deepseek", name="DeepSeek", base_url="https://api.deepseek.com/v1", model="deepseek-flash", vision_model="deepseek-flash", docs="https://api-docs.deepseek.com/"),
    dict(id="qwen", name="通义千问 / 百炼", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", model="qwen-plus", vision_model="qwen-vl-plus", docs="https://help.aliyun.com/zh/model-studio/use-bailian-in-langchain"),
    dict(id="glm", name="智谱 GLM", base_url="https://open.bigmodel.cn/api/paas/v4", model="glm-4.7", vision_model="glm-4.5v", docs="https://docs.bigmodel.cn/cn/guide/models/text/glm-4.7"),
    dict(id="custom", name="自定义兼容接口", base_url="", model="", vision_model="", docs=""),
]


def save_generation_config(base_url, model, vision_model, api_key=None):
    parsed = urlsplit(base_url)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("请输入有效的接口地址，不要在地址中包含凭据")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}):
        raise ValueError("远程接口使用 HTTPS；本地接口可使用 HTTP")
    if any(c in v for v in (base_url, model, vision_model, api_key or "") for c in "\r\n\0"):
        raise ValueError("配置不能包含换行符")
    values = {"DEEPSEEK_BASE_URL": base_url.rstrip("/"), "DEEPSEEK_MODEL": model.strip(), "VISION_MODEL": vision_model.strip() or model.strip()}
    if api_key:
        values["DEEPSEEK_API_KEY"] = api_key
    target = ROOT / ".env"
    temporary = ROOT / ".env.model-config.tmp"
    try:
        temporary.write_bytes(target.read_bytes() if target.exists() else b"")
        for key, value in values.items():
            set_key(str(temporary), key, value)
        os.replace(temporary, target)
        os.environ.update(values)
    finally:
        temporary.unlink(missing_ok=True)
    return Settings.from_env()
