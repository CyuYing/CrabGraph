import pytest

from crabgraph.business_tools import public_url, terminal_pond_statistics
from crabgraph.reports import pdf_report
from crabgraph.settings import ROOT


def test_public_fetch_cannot_reach_private_or_redirect_hosts():
    for url in ["http://www.fao.org/test", "https://127.0.0.1/", "https://www.fao.org.evil.example/",
                "https://user:password@www.fao.org/", "https://www.fao.org:9621/"]:
        with pytest.raises(ValueError):
            public_url(url)
    assert public_url("https://www.fao.org/test")


def test_fixed_terminal_statistics():
    stats = terminal_pond_statistics((ROOT / "examples" / "pond_records.csv").read_text(encoding="utf-8"))
    assert stats["rows"] > 0


def test_pdf_escapes_user_markup_and_preserves_chinese():
    data = pdf_report("# 青蟹研究\n输入 <script> / A & B\n结论 [S1]")
    assert data.startswith(b"%PDF") and len(data) > 3000
