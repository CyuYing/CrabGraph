"""Start the migrated copy with path guards and a private environment."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "LightRAG"
RUNTIME = ROOT / "runtime" / "lightrag"

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if not (VENDOR / "lightrag").is_dir() or not (RUNTIME / "rag_storage").is_dir():
        raise SystemExit("Verified migration copy is required before starting.")
    os.chdir(RUNTIME)
    load_dotenv(RUNTIME / ".env", override=True)
    # These overrides are authoritative; inherited variables cannot point back to the source.
    os.environ.update(HOST="127.0.0.1", PORT="9622", WORKING_DIR=str(RUNTIME / "rag_storage"),
                      INPUT_DIR=str(RUNTIME / "inputs"), LOG_DIR=str(ROOT / "runtime" / "logs"), WORKERS="1")
    sys.path.insert(0, str(VENDOR))
    from crabgraph.storage_loader import install_snapshot_reader
    install_snapshot_reader()
    from lightrag.api.lightrag_server import main
    main()
