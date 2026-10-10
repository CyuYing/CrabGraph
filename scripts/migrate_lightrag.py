"""Copy an idle local LightRAG without writes to the source tree."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache",
           "lightrag_hku.egg-info", "runtime", "rag_storage", "inputs", "logs", "service_logs"}


def health(url: str) -> dict:
    with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=10) as r:
        return json.load(r)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inventory(root: Path) -> dict:
    return {str(p.relative_to(root)): {"bytes": p.stat().st_size, "sha256": digest(p)}
            for p in root.rglob("*") if p.is_file()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:9621")
    args = parser.parse_args()
    src = args.source.resolve()
    dst = ROOT / "vendor" / "LightRAG"
    storage_dst = ROOT / "runtime" / "lightrag" / "rag_storage"
    input_dst = ROOT / "runtime" / "lightrag" / "inputs"
    if dst.exists() or storage_dst.exists():
        raise SystemExit("Migration destination exists. Use a new project directory to avoid overwriting data.")
    info = health(args.url)
    if info.get("pipeline_busy") or info.get("pipeline_active") or info.get("pipeline_destructive_busy"):
        raise SystemExit("Source pipeline is busy. Wait for it to finish before copying; source will not be stopped.")
    source_storage = Path(info["working_directory"])
    source_inputs = Path(info["input_directory"])
    before = inventory(source_storage)
    size = sum(x["bytes"] for x in before.values()) + sum(p.stat().st_size for p in source_inputs.rglob("*") if p.is_file())
    free = shutil.disk_usage(ROOT).free
    if free < size * 2 + 3 * 1024**3:
        raise SystemExit(f"Insufficient free space: {free / 1024**3:.1f} GiB. Copy needs {size / 1024**3:.1f} GiB plus headroom.")
    def ignore(folder, names):
        return [n for n in names if n in IGNORED or n.endswith(".log") or n.startswith(".env.backup") or n == ".env"]
    shutil.copytree(src, dst, ignore=ignore)
    shutil.copytree(source_storage, storage_dst)
    shutil.copytree(source_inputs, input_dst)
    after = inventory(source_storage)
    copied = inventory(storage_dst)
    final_health = health(args.url)
    consistent = before == after == copied and not final_health.get("pipeline_busy") and not final_health.get("pipeline_destructive_busy")
    report = {"source": str(src), "destination": str(dst), "source_storage": str(source_storage),
              "destination_storage": str(storage_dst), "storage_files": before,
              "consistent": consistent, "copied_runtime_bytes": size, "original_modified": False,
              "source_version": info.get("core_version"), "copied_at_unix": time.time()}
    (ROOT / "research").mkdir(exist_ok=True)
    (ROOT / "research" / "migration_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not consistent:
        raise SystemExit("Source changed during copy. Snapshot is not verified; do not start it. Create a new snapshot when idle.")
    private = ROOT / "runtime" / "lightrag" / ".env"
    text = (src / ".env").read_text(encoding="utf-8-sig") if (src / ".env").exists() else ""
    # Rebase only the private config copy. Indexed source strings remain provenance.
    text = text.replace(str(src), str(dst)).replace(str(src).replace("\\", "/"), str(dst).replace("\\", "/"))
    overrides = {"HOST": "127.0.0.1", "PORT": "9622", "WORKING_DIR": str(storage_dst).replace("\\", "/"),
                 "INPUT_DIR": str(input_dst).replace("\\", "/"), "LOG_DIR": str(ROOT / "runtime" / "logs").replace("\\", "/"),
                 "AUTO_SCAN_AT_STARTUP": "false"}
    lines = [line for line in text.splitlines() if line.split("=", 1)[0].strip() not in overrides]
    lines.extend(f"{k}={v}" for k, v in overrides.items())
    private.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"consistent": consistent, "copied_runtime_MiB": round(size/1024**2, 1),
                      "storage_files": len(before), "free_GiB": round(free/1024**3, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
