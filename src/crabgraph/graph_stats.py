"""Count the project copy on disk without loading the full graph into memory."""
from functools import lru_cache
from xml.etree import ElementTree as ET

from crabgraph.settings import ROOT


@lru_cache(maxsize=2)
def _count(path, modified, size):
    nodes = edges = 0
    for _, element in ET.iterparse(path, events=("end",)):
        tag = element.tag.rsplit("}", 1)[-1]
        nodes += tag == "node"
        edges += tag == "edge"
        element.clear()
    return dict(nodes=nodes, edges=edges, source="项目迁移副本", display_cap=1000)


def graph_stats():
    path = ROOT / "runtime/lightrag/rag_storage/graph_chunk_entity_relation.graphml"
    if not path.exists():
        return dict(nodes=None, edges=None, source="项目迁移副本", display_cap=1000)
    info = path.stat()
    return _count(str(path), info.st_mtime_ns, info.st_size)
