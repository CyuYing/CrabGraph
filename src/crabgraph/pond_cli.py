import json
import sys
from pathlib import Path

from crabgraph.pond import analyze_csv
from crabgraph.settings import ROOT

if __name__ == "__main__":
    path = Path(sys.argv[1]).resolve()
    if not path.is_relative_to((ROOT / "runtime" / "resources").resolve()) or path.suffix != ".csv":
        raise ValueError("Only project research CSVs are accepted")
    print(json.dumps(analyze_csv(path.read_text(encoding="utf-8-sig")), ensure_ascii=False))
