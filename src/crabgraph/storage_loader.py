"""Read NanoVectorDB snapshots without a full Unicode document allocation."""
from pathlib import Path

import ijson
from nano_vectordb import dbs


def load_storage(file_name):
    path = Path(file_name)
    if not path.exists():
        return None
    data = {}
    # Parse top-level fields independently; never retain a full JSON document buffer.
    with path.open("rb") as stream:
        # Large base64 matrix strings otherwise trigger excessive lexer-buffer copying.
        for name, value in ijson.kvitems(stream, "", use_float=True, buf_size=4 * 1024 * 1024):
            data[name] = dbs.buffer_string_to_array(value) if name == "matrix" else value
    data["matrix"] = data["matrix"].reshape(-1, data["embedding_dim"])
    return data


def install_snapshot_reader():
    # Process-local dependency hook; persistence format and write path remain upstream-owned.
    dbs.load_storage = load_storage
