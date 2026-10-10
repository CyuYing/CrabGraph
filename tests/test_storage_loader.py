import json

import numpy as np
from nano_vectordb import dbs

from crabgraph.storage_loader import load_storage


def test_reader_preserves_unicode_vectors_and_metadata(tmp_path):
    original = np.array([[0.6, 0.8], [1.0, 0.0]], dtype=np.float32)
    payload = {"embedding_dim": 2, "matrix": dbs.array_to_buffer_string(original),
               "data": [{"__id__": "青蟹", "content": "测试文档"}, {"__id__": "水质"}],
               "additional_data": {"revision": 2}}
    path = tmp_path / "vdb.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    old = dbs.load_storage(path)
    new = load_storage(path)
    assert old["data"] == new["data"]
    assert old["additional_data"] == new["additional_data"]
    np.testing.assert_array_equal(old["matrix"], new["matrix"])
