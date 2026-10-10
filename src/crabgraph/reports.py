"""Unicode PDF report export with escaped user content."""
import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def escaped_pdf_text(text: str) -> str:
    """Preserve scientific subscripts even when the CJK font lacks those glyphs."""
    rendered = escape(text)
    for char, value in zip("₀₁₂₃₄₅₆₇₈₉₊₋", "0123456789+-", strict=True):
        rendered = rendered.replace(char, f"<sub>{value}</sub>")
    for char, value in zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-", strict=True):
        rendered = rendered.replace(char, f"<super>{value}</super>")
    return rendered.replace("−", "-")


def register_chinese():
    name = "CrabChinese"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    windows_font = Path("C:/Windows/Fonts/simsun.ttc")
    if windows_font.exists():
        pdfmetrics.registerFont(TTFont(name, str(windows_font)))
    else:
        name = "STSong-Light"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(name))
    return name


def pdf_report(text: str) -> bytes:
    font = register_chinese()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(210 * mm, 297 * mm),
                           rightMargin=22 * mm, leftMargin=22 * mm,
                           topMargin=22 * mm, bottomMargin=22 * mm,
                           title="CrabGraph 青蟹研究报告", author="CrabGraph")
    normal = ParagraphStyle("body", fontName=font, fontSize=10.5, leading=18,
                            textColor=colors.HexColor("#30463d"), spaceAfter=8, wordWrap="CJK")
    heading = ParagraphStyle("heading", parent=normal, fontSize=16, leading=23,
                             spaceBefore=14, spaceAfter=10, keepWithNext=True)
    story = [Paragraph("CrabGraph 青蟹研究报告", heading), Spacer(1, 8)]
    table_rows = []

    def flush_table():
        if not table_rows:
            return
        columns = max(len(row) for row in table_rows)
        cells = [[Paragraph(escaped_pdf_text(cell.replace("**", "")), normal) for cell in row + [""] * (columns - len(row))] for row in table_rows]
        table = Table(cells, colWidths=[doc.width / columns] * columns, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7efe9")),
                                   ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#d2dfd6")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                                   ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        story.extend([table, Spacer(1, 10)])
        table_rows.clear()

    for line in text.splitlines():
        if line.strip().startswith("|") and line.strip().endswith("|"):
            row = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r"[-: ]+", cell) for cell in row):
                table_rows.append(row)
            continue
        flush_table()
        if not line.strip():
            continue
        is_heading = line.startswith("#")
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        # Never interpret markdown/user text as ReportLab XML.
        story.append(Paragraph(escaped_pdf_text(line), heading if is_heading else normal))
    flush_table()
    doc.build(story)
    return buffer.getvalue()
