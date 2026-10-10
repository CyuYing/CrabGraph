"""Build an illustrated project handbook using the bundled artifact Python runtime."""

import html
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as PDFImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
IMAGES = DOCS / "images"
IMAGES.mkdir(parents=True, exist_ok=True)
GREEN = "#17695b"
MUTED = "#607b71"
coverage = json.loads((DOCS / "technology-coverage.json").read_text(encoding="utf-8"))
live = json.loads((DOCS / "live-validation.json").read_text(encoding="utf-8"))
vision = json.loads((DOCS / "multimodal-validation.json").read_text(encoding="utf-8"))
projects = json.loads((ROOT / "research" / "github_projects.json").read_text(encoding="utf-8"))["projects"]
covered = sum(item["covered"] for item in coverage["items"])
assert covered == 13 and len(coverage["items"]) == 16


def font(size, bold=False):
    return ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc", size)


def diagram(name, width, height, title, subtitle):
    im = Image.new("RGB", (width, height), "#f7faf5")
    draw = ImageDraw.Draw(im)
    draw.text((45, 30), title, fill="#21483e", font=font(34, True))
    draw.text((45, 82), subtitle, fill=MUTED, font=font(21))
    return im, draw


def box(draw, rect, title, lines=(), fill="#e7f1e7", border="#c5d9c8", title_size=25):
    x, y, right, bottom = rect
    draw.rounded_rectangle(rect, radius=15, fill=fill, outline=border, width=2)
    draw.text((x + 22, y + 16), title, fill="#245748", font=font(title_size, True))
    for i, line in enumerate(lines):
        draw.text((x + 22, y + 56 + i * 29), line, fill="#647d6d", font=font(20))


def arrow(draw, start, end, color="#87ab93", width=4):
    draw.line([start, end], fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    tip = [
        (end[0] - 14 * math.cos(angle - 0.48), end[1] - 14 * math.sin(angle - 0.48)),
        end,
        (end[0] - 14 * math.cos(angle + 0.48), end[1] - 14 * math.sin(angle + 0.48)),
    ]
    draw.polygon(tip, fill=color)


im, draw = diagram(
    "architecture", 1250, 975, "CrabGraph 系统架构", "同源工作台  ·  持久化智能体  ·  独立知识副本"
)
box(draw, (340, 145, 900, 245), "Vue 3 交互工作台", ["问答 / 研究 / 图谱 / 资料 / 工具 / 运行观察"])
box(
    draw,
    (340, 290, 900, 405),
    "FastAPI 8503",
    ["输入校验 · SSE 事件重放 · 任务管理", "同源静态页面与接口文档"],
)
box(
    draw,
    (130, 460, 620, 590),
    "LangGraph / LangChain",
    ["问答 ReAct 模型与工具循环", "研究：规划 → 审批 → 检索 → 报告"],
)
box(
    draw,
    (690, 460, 1120, 590),
    "DeepSeek 兼容接口",
    ["业务回答 / 计划生成 / 图像观察"],
    fill="#f5ead7",
    border="#e1cfab",
)
box(draw, (45, 650, 400, 795), "LightRAG 副本 9622", ["原文 + 实体关系联合检索", "26191 实体 / 27790 关系"])
box(
    draw,
    (450, 650, 805, 795),
    "PostgreSQL pgvector",
    ["1300 条原文向量快照", "Jina 1024 维 / cosine 距离"],
    fill="#e7eef1",
    border="#c8d9df",
)
box(
    draw,
    (855, 650, 1205, 795),
    "MCP 与业务工具",
    ["文献 / 图片 / 网页 / 文件", "终端统计 / 下载 / PDF"],
    fill="#eeebf4",
    border="#d8cfe3",
)
box(
    draw,
    (130, 850, 1120, 945),
    "SQLite 持久化",
    ["会话 checkpoint · 研究 checkpoint · 任务与事件 · 运行指标"],
    title_size=23,
)
for start, end in [
    ((620, 245), (620, 290)),
    ((535, 405), (375, 460)),
    ((735, 405), (900, 460)),
    ((620, 525), (690, 525)),
    ((245, 590), (220, 650)),
    ((470, 590), (625, 650)),
    ((565, 590), (1020, 650)),
]:
    arrow(draw, start, end)
draw.line([(130, 525), (20, 525), (20, 830), (200, 830)], fill="#87ab93", width=4)
arrow(draw, (200, 830), (200, 850))
draw.line([(900, 350), (1230, 350), (1230, 830), (1100, 830)], fill="#87ab93", width=4)
arrow(draw, (1100, 830), (1100, 850))
im.save(IMAGES / "architecture.png")

im, draw = diagram(
    "workflow", 1250, 560, "从研究目标到报告", "有界自主规划，重要执行前可人工确认；全程保留事件与状态"
)
stages = [
    ("01 规划", ["模型拆解目标", "最多 3 个查询"]),
    ("02 审批", ["interrupt 暂停", "Command 恢复"]),
    ("03 检索", ["LightRAG 联合", "去重合并证据"]),
    ("04 撰写", ["DeepSeek 生成", "附本轮来源"]),
    ("05 检查", ["引用编号有效", "输出长度检查"]),
    ("06 导出", ["PDF / Markdown", "真实报告文件"]),
]
for i, (title, lines) in enumerate(stages):
    x = 40 + i * 201
    box(draw, (x, 175, x + 180, 320), title, lines, title_size=24)
    if i < 5:
        arrow(draw, (x + 180, 247), (x + 200, 247), width=3)
box(
    draw,
    (150, 405, 1100, 520),
    "状态与事件可追溯",
    [
        "SQLite 保存计划和任务事件；浏览器断开不取消后台任务",
        "重启后保留待审批计划，进行中的任务标记失败；取消在网络请求返回后生效",
    ],
)
for x in (330, 730, 1030):
    arrow(draw, (x, 320), (x, 405))
im.save(IMAGES / "workflow.png")

im, draw = diagram(
    "retrieval",
    1250,
    780,
    "多模态问答与证据链",
    "图像观察、记录统计与文献依据分开表达，来源编号只来自本轮检索",
)
box(draw, (45, 165, 390, 290), "用户输入", ["业务问题 / 可选图片", "可选养殖记录 CSV"])
box(
    draw,
    (450, 165, 795, 290),
    "图像观察",
    ["DeepSeek 视觉协议", "仅描述可见事实与局限"],
    fill="#f5ead7",
    border="#e0cfab",
)
box(draw, (855, 165, 1205, 290), "检索入口", ["LightRAG 混合 / 原文", "或独立 PGvector 快照"])
box(draw, (855, 370, 1205, 495), "证据组织", ["合并片段与关系，去重", "生成 S1 等本轮引用编号"])
box(draw, (450, 370, 795, 495), "ReAct 模型与工具循环", ["按需要追加检索与统计", "工具和模型调用次数有界"])
box(draw, (45, 370, 390, 495), "答案与证据面板", ["流式答案 / 引用 / 原文", "观察与统计不作为确诊"])
box(
    draw,
    (155, 580, 1095, 720),
    "保留本轮可验证信息",
    [
        "耗时、Token、工具调用与最终结果写入持久化记录",
        "自动检查引用编号存在；没有自动证明引用支持结论，也没有测量诊断准确率",
    ],
)
for start, end in [
    ((390, 227), (450, 227)),
    ((795, 227), (855, 227)),
    ((1030, 290), (1030, 370)),
    ((855, 430), (795, 430)),
    ((450, 430), (390, 430)),
    ((220, 495), (400, 580)),
]:
    arrow(draw, start, end)
im.save(IMAGES / "retrieval.png")

im, draw = diagram(
    "migration",
    1250,
    590,
    "保留原实例，使用项目副本",
    "迁移采用复制与 SHA256 核对；应用不接入原始服务执行写入",
)
box(
    draw,
    (45, 175, 460, 360),
    "原始 LightRAG",
    ["原端口 9621，用户独立管理", "原始源码 / .env / 知识资料", "12 个存储文件 hash 与快照一致"],
    fill="#eef0ea",
    border="#d9dfd0",
)
box(
    draw,
    (790, 175, 1205, 360),
    "项目内 LightRAG 副本",
    ["独立端口 9622", "runtime/lightrag / vendor/LightRAG", "上传资料与检索仅使用本副本"],
)
arrow(draw, (460, 250), (790, 250))
draw.text((500, 205), "复制并校验", fill=GREEN, font=font(23, True))
draw.text((484, 280), "不移动，不修改原目录", fill=MUTED, font=font(20))
box(
    draw,
    (790, 425, 1205, 545),
    "额外 PGvector 索引",
    ["从副本复制 1300 条原文向量", "独立目录，不重建原索引"],
    fill="#e7eef1",
    border="#c8d9df",
)
arrow(draw, (995, 360), (995, 425))
draw.text((60, 450), "项目停止脚本仅操作归属本项目的进程", fill=MUTED, font=font(23))
draw.text((60, 494), "私有知识资料与凭据均不提交 Git", fill=MUTED, font=font(23))
im.save(IMAGES / "migration.png")

im, draw = diagram(
    "mcp", 1250, 620, "真实 MCP 服务与客户端", "MCP 使用 stdio 传输，不以普通 Python 函数调用冒充协议调用"
)
box(draw, (45, 165, 385, 285), "智能体 / MCP 客户端", ["ClientSession initialize", "list_tools / call_tool"])
box(
    draw,
    (465, 165, 795, 285),
    "stdio 协议通道",
    ["本项目 Python 子进程", "标准输入输出消息传输"],
    fill="#e7eef1",
    border="#c8d9df",
)
box(draw, (875, 165, 1205, 285), "FastMCP 服务", ["7 个工具与能力资源", "工具商店持久化开关"])
for start, end in [((385, 225), (465, 225)), ((795, 225), (875, 225))]:
    arrow(draw, start, end)
for i, (title, lines) in enumerate(
    [
        ("知识检索", ["search_crab_knowledge", "LightRAG 9622"]),
        ("用户记录统计", ["analyze_pond_csv", "只分析调用者提供的数据"]),
        ("参考图片搜索", ["search_reference_images", "Wikimedia 来源与许可"]),
    ]
):
    x = 45 + i * 405
    box(draw, (x, 385, x + 355, 540), title, lines, title_size=25)
    arrow(draw, (1040, 285), (x + 177, 385))
draw.text(
    (45, 575),
    "能力资源：crabgraph://capabilities；外部参考图片不代表用户现场数据或诊断依据。",
    fill=MUTED,
    font=font(20),
)
im.save(IMAGES / "mcp.png")

im, draw = diagram("validation", 1250, 590, "本机运行快照", "三种任务的一次真实调用耗时，单位：秒")
values = [
    live["chat_metrics"]["elapsed_ms"] / 1000,
    vision["metrics"]["elapsed_ms"] / 1000,
    live["research_metrics"]["elapsed_ms"] / 1000,
]
for tick in range(0, 51, 10):
    x = 320 + tick * 15
    draw.line([(x, 150), (x, 425)], fill="#dfe7dc", width=2)
    draw.text((x - 10, 440), str(tick), fill=MUTED, font=font(20))
for i, (label, value, color) in enumerate(
    zip(["混合检索问答", "图文与 CSV 问答", "研究报告执行"], values, ["#458c74", "#88b2a1", "#dbb981"])
):
    y = 175 + i * 90
    draw.text((45, y + 10), label, fill=GREEN, font=font(24))
    right = 320 + value * 15
    draw.rounded_rectangle((320, y, right, y + 52), radius=6, fill=color)
    draw.text((right + 15, y + 10), f"{value:.2f} s", fill=MUTED, font=font(23))
draw.text((45, 510), "任务与输入不同，不能据此比较方案优劣。", fill=MUTED, font=font(21))
draw.text((45, 546), "研究执行耗时不含规划和人工审批等待。", fill=MUTED, font=font(21))
im.save(IMAGES / "validation.png")

pdfmetrics.registerFont(TTFont("GuideBody", "C:/Windows/Fonts/msyh.ttc"))
pdfmetrics.registerFont(TTFont("GuideBold", "C:/Windows/Fonts/msyhbd.ttc"))
styles = {
    "title": ParagraphStyle(
        "Title",
        fontName="GuideBold",
        fontSize=27,
        leading=38,
        textColor=colors.HexColor("#174c42"),
        spaceAfter=15,
        wordWrap="CJK",
    ),
    "h1": ParagraphStyle(
        "H1",
        fontName="GuideBold",
        fontSize=20,
        leading=30,
        textColor=colors.HexColor("#174c42"),
        spaceAfter=15,
        wordWrap="CJK",
    ),
    "h2": ParagraphStyle(
        "H2",
        fontName="GuideBold",
        fontSize=13,
        leading=21,
        textColor=colors.HexColor("#305d4c"),
        spaceBefore=13,
        spaceAfter=8,
        keepWithNext=True,
        wordWrap="CJK",
    ),
    "body": ParagraphStyle(
        "Body",
        fontName="GuideBody",
        fontSize=10.5,
        leading=18.5,
        textColor=colors.HexColor("#42574a"),
        spaceAfter=11,
        wordWrap="CJK",
    ),
    "small": ParagraphStyle(
        "Small",
        fontName="GuideBody",
        fontSize=8.5,
        leading=14,
        textColor=colors.HexColor("#748773"),
        spaceAfter=10,
        wordWrap="CJK",
    ),
    "cell": ParagraphStyle(
        "Cell",
        fontName="GuideBody",
        fontSize=9,
        leading=15,
        textColor=colors.HexColor("#42574a"),
        wordWrap="CJK",
    ),
    "label": ParagraphStyle(
        "Label",
        fontName="GuideBody",
        fontSize=9,
        leading=16,
        textColor=colors.HexColor("#779785"),
        spaceAfter=13,
    ),
}
doc = SimpleDocTemplate(
    str(DOCS / "CrabGraph项目说明.pdf"),
    pagesize=(210 * mm, 297 * mm),
    leftMargin=22 * mm,
    rightMargin=22 * mm,
    topMargin=22 * mm,
    bottomMargin=20 * mm,
    title="CrabGraph 青蟹多模态智能体项目说明",
    author="CrabGraph",
)
story, html_sections = [], []
figure_count = 0


def p(text, style="body"):
    story.append(Paragraph(escape(text), styles[style]))
    html_sections.append(f'<p class="{style}">{html.escape(text)}</p>')


def h2(text):
    p(text, "h2")


def page(title, anchor):
    if story:
        story.append(PageBreak())
    html_sections.append(f'<section id="{anchor}"><h2>{html.escape(title)}</h2>')
    story.append(Paragraph(escape(title), styles["h1"]))


def endpage():
    html_sections.append("</section>")


def image(filename, caption, max_height=390):
    global figure_count
    source = IMAGES / filename
    assert source.exists(), source
    with Image.open(source) as img:
        width, height = img.size
    scale = min(doc.width / width, max_height / height)
    story.append(PDFImage(str(source), width=width * scale, height=height * scale))
    story.append(Spacer(1, 9))
    figure_count += 1
    label = f"图 {figure_count}  {caption}"
    story.append(Paragraph(escape(label), styles["small"]))
    html_sections.append(
        f'<figure><img src="images/{html.escape(filename)}" alt="{html.escape(caption)}" loading="lazy"><figcaption>{html.escape(label)}</figcaption></figure>'
    )


def table(headers, rows, widths=None):
    widths = widths or [doc.width / len(headers)] * len(headers)
    cells = [[Paragraph(escape(str(v)), styles["cell"]) for v in row] for row in [headers] + rows]
    t = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4ece7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8f3")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9dfd6")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend([t, Spacer(1, 13)])
    head = "".join(f"<th>{html.escape(str(v))}</th>" for v in headers)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row) + "</tr>" for row in rows)
    html_sections.append(
        f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
    )


page("青蟹多模态智能体项目说明", "intro")
p("CRABGRAPH  /  PROJECT HANDBOOK  /  2026.10.10", "label")
p("面向 Python 与 AI 应用开发的完整业务工作台", "title")
p(
    "CrabGraph 将青蟹资料检索、图文观察、用户记录分析与自主研究任务放进同一个本地工作空间。项目以真实知识库和模型调用为基础，给出可追溯的答案与研究报告，支持持久化记忆、MCP、计划确认和运行观察。"
)
image("01-overview.jpg", "真实运行的青蟹智研总览", max_height=215)
table(
    ["交付范围", "当前实现"],
    [
        ["主要技术", "FastAPI / LangChain / LangGraph / Vue 3 / DeepSeek / LightRAG / PostgreSQL pgvector"],
        ["参考覆盖", "13 / 16 项等价技术能力，81.25%；按已选择的 Python 方向核算"],
        ["本机位置", "E:\\Projects\\deepseek-lightrag-agent"],
        ["使用入口", "http://127.0.0.1:8503"],
    ],
    widths=[90, doc.width - 90],
)
endpage()

page("项目定位与业务价值", "business")
p(
    "该项目服务于青蟹养殖资料查询和研究整理：把文献中的结论、现场图片的可见线索与用户提供的记录分开处理，再通过同一工作台提供检索依据。它适合展示 AI 应用开发中的业务建模、模型接入、RAG、智能体编排和产品交付能力。"
)
h2("两条完整业务链")
p(
    "知识问答链面向具体业务问题，可上传图片和养殖 CSV。图片先生成观察文字，问题与观察用于本轮知识检索；随后模型按需调用追加检索和统计工具，流式生成答案，并给出原文片段和来源。"
)
p(
    "研究任务链面向更长的目标。模型先规划最多3个检索问题，用户可以确认计划再执行。LangGraph 保存审批中断点，检索后合并证据、生成报告、检查引用编号，最后导出 PDF 或 Markdown。"
)
h2("可以讲清楚的技术亮点")
p(
    "一是原实例与副本隔离：复制现有知识库，保留嵌入配置，并通过哈希核对证明原始存储未改变。二是有状态执行：会话、研究计划、任务状态和事件分别持久化，浏览器断开后仍能读取结果。三是证据可见：来源与原文面板让用户核查模型结论，而不是仅看到一个答案。"
)
p(
    "四是完整工具链：不仅定义工具，还通过真实模型调用、MCP 协议调用、固定终端命令与资源文件验证业务流程。五是独立 PGvector 路径：在保留 LightRAG 的同时，通过已有向量快照验证 PostgreSQL 的相似检索能力。"
)
image("migration.png", "原始 LightRAG 与项目副本的隔离关系", max_height=245)
endpage()

page("功能一览与交互设计", "features")
p(
    "工作台使用海洋绿色与浅色背景，青蟹图形由知识节点组成。左侧仅保留新对话、置顶项目或对话、普通对话与项目；点击头像打开居中设置弹窗，左侧切换分类、右侧独立滚动，集中访问工具商店、模型配置、知识资料和其他能力。已去除装饰性英文标题、重复说明和小字。"
)
table(
    ["页面", "核心功能", "演示重点"],
    [
        ["智研总览", "资料状态、会话与任务足迹", "真实数量，不显示虚构准确率"],
        ["知识问答", "图片与 CSV、多轮记忆、SSE", "观察和文献证据分开"],
        ["研究任务", "计划确认、检索、报告", "展示 interrupt 与恢复"],
        ["知识资料", "分页、筛选、上传", "只向知识副本写入"],
        ["图谱探索", "缩放、拖拽、实体详情", "从关系继续发起问答"],
        ["工具实验室", "六类工具单独执行", "检查真实接口和产物"],
        ["运行观察", "耗时、Token、工具记录", "区分性能与准确性"],
        ["连接设置", "配置状态、MCP 接入", "密钥留在服务端"],
        ["工具商店", "7个工具、分类、搜索、启停", "默认启用联网等5项能力"],
    ],
    widths=[75, 190, doc.width - 265],
)
p(
    "前端采用 Vue 3 与 TypeScript，Markdown 输出经 DOMPurify 清理；图谱引擎按需加载。生产构建主脚本约220 kB，图谱模块约465 kB，均为压缩前构建产物大小。会话归属和置顶状态存入 SQLite，刷新后保留。"
)
endpage()

page("图文问答与证据核查", "chat")
image("02-chat.jpg", "图文输入与真实问答来源面板", max_height=215)
p(
    "开启一个会话后，输入业务问题并选择检索模式。附件支持 PNG、JPEG、WebP 与 UTF-8 CSV，单个附件上限8 MB。点击回答中的 S 编号或右侧来源卡片，可以选择本轮资料；展开原文片段进行核查。"
)
p(
    "图文验收使用本项目绘制的青蟹插画与合成养殖记录。这组样例验证图片输入、视觉协议、PGvector、工具调用与统计输出，不代表现场青蟹图像识别准确率。真实模型调用返回6个来源，并调用了 analyze_pond_records。"
)
image("retrieval.png", "从用户输入到有来源的答案", max_height=220)
endpage()

page("研究任务与计划审批", "research")
image("03a-approval.jpg", "历史验收截图：计划确认按钮（旧版页面布局）", max_height=225)
p(
    "输入研究目标，选择是否在执行前确认计划。开启确认时，模型先输出标题、研究方法与最多3个检索问题，任务进入待确认状态。点击确认后通过 Command 恢复同一 LangGraph 线程，后续研究不重新规划。"
)
p(
    "任务列表可打开已有任务。执行过程中记录检索阶段和命中片段，完整结果存入数据库；取消在当前网络调用结束后生效。模型或知识库调用失败时显示失败状态，已保存记录仍可查看。"
)
image("workflow.png", "规划到报告的有界工作流", max_height=210)
endpage()

page("报告产出与引用边界", "reports")
image("03b-report.jpg", "真实执行轨迹、研究报告与导出入口", max_height=335)
p(
    f"另一轮完整研究任务按3个问题检索，合并了{live['research_sources']}个可引用来源，生成了带摘要、发现、局限和核实建议的报告。研究执行阶段耗时{live['research_metrics']['elapsed_ms'] / 1000:.2f}秒，不包含规划和人工确认等待。"
)
p(
    "最终输出执行引用编号检查，只允许本轮来源编号；若模型触及输出长度限制，任务标记失败，不把截断内容认定为完成。PDF 导出使用中文字体，并将 Markdown 表格转换为可分页表格。"
)
p(
    "来源计数是可引用条目数，可能包含同一文件的不同片段。来源编号存在不等于引用一定支持结论。当前系统没有自动测量语义忠实性、现场诊断准确率或农业生产适用性；这些需要业务专家与真实标注案例进一步评审。"
)
endpage()

page("知识资料管理", "documents")
image("04-library.jpg", "迁移副本中的实际资料与处理状态", max_height=330)
p(
    "资料列表支持分页与状态筛选，可查看文件名称、更新时间、片段数与摘要。新上传支持 PDF、TXT、Markdown、DOCX，最大20 MB，并通过副本的上传接口提交处理。"
)
p(
    "当前副本保留70份资料及迁移时的历史状态：59份显示已处理、8份失败、3份处理或分析中。历史状态没有被伪造为全部成功，上传后的解析能力和耗时取决于副本的具体配置。"
)
h2("为什么保留原嵌入模型")
p(
    "现有向量使用 Jina jina-embeddings-v5-text-small，维度为1024。更换回答模型不要求重建这些向量，但更换嵌入模型后不能直接复用旧索引。项目默认保留原嵌入配置，仅使用独立副本运行。"
)
h2("PGvector 快照的使用")
p(
    "PGvector 复制的是副本已存在的1,300条原文向量。它保留真实文本和向量，查询时调用同一嵌入模型，再使用 PostgreSQL cosine 距离检索。该索引不自动同步新上传资料，新资料默认使用 LightRAG 混合检索。"
)
endpage()

page("知识图谱探索", "graph")
image("05-graph.jpg", "图谱弹窗：全库统计与174节点的实际实体子图", max_height=420)
p(
    "输入中心实体或选择热门名称，查询1到3层关系；展示上限可选65、150、300、500、1000，默认300。全库统计与当前子图统计分别展示，并保留 LightRAG 截断状态。实测 S. serrata 一层关系，在65上限时被截断；300上限时返回174节点、300关系。"
)
p(
    "原库与副本均有26,191节点和27,790关系，GraphML 的SHA256一致，数据没有减少。全库概览使用中心实体 *，按连接度选取有限节点，不代表加载完整图谱；颜色和布局距离不表示置信度。证据来自 LightRAG 的 /query/data 原文及图谱检索，应用新增来源编号与原文面板；知识资料模块负责同一副本的文件管理。"
)
endpage()

page("研究工具与外部资料", "tools")
image("06-tools.jpg", "工具实验室弹窗中的真实 Crossref 执行结果", max_height=355)
table(
    ["工具", "实际处理", "主要边界"],
    [
        ["文献检索", "Crossref 书目、DOI、链接", "元数据不是全文证据"],
        ["MCP 图片检索", "Wikimedia 来源与许可", "参考图不是用户现场数据"],
        ["网页抓取", "公共 HTML 正文提取", "HTTPS 白名单，不跟随重定向"],
        ["PDF 下载", "资源保存到项目目录", "验证 PDF，最大8 MB"],
        ["文件笔记", "生成唯一 Markdown 文件", "不接受任意写入路径"],
        ["终端统计", "固定 Python CSV 命令", "不运行模型生成的任意命令"],
    ],
    widths=[85, 170, doc.width - 255],
)
p(
    "已实测 Crossref 返回5条文献元数据，公共页面正文抓取6,636字符；FAO 青蟹实用手册 PDF 下载成功，大小1,673,574字节。外部资源仅用于发现资料，不自动进入知识库。",
    "small",
)
endpage()

page("MCP 接入与协议验证", "mcp")
image("mcp.png", "MCP 客户端、stdio 通道与服务端工具", max_height=280)
p(
    "MCP 服务提供知识检索、联网文献、网页正文、用户 CSV 统计、参考图片、PDF下载、笔记保存共7个工具，以及 crabgraph://capabilities 资源。模型调用图片工具时，通过客户端启动本项目 Python stdio 服务，执行真实协议初始化与工具调用。"
)
p(
    "验证程序调用 initialize、list_tools、list_resources 和 call_tool，列出7个工具；CSV统计成功，联网文献检索经MCP返回5条Crossref结果。图片工具已有实际协议调用记录。停用选项会阻止MCP调用，能力资源返回当前启用列表。"
)
table(
    ["配置项", "本机值"],
    [
        ["command", "E:\\Projects\\deepseek-lightrag-agent\\.venv\\Scripts\\python.exe"],
        ["args", "-m crabgraph.mcp_server"],
        ["传输", "stdio"],
        ["使用方式", "将连接设置页面提供的 JSON 加入支持 MCP 的客户端"],
    ],
    widths=[90, doc.width - 90],
)
p(
    "MCP 是协议与工具接口；它不能替代对工具参数、资源范围、输入可信度和业务结论的校验。项目把用户资料、网页与图片文字都视为不可信数据，而不是系统指令。"
)
endpage()

page("开源工具商店与会话项目", "market")
image("10-marketplace.jpg", "设置弹窗中的开源工具商店", max_height=365)
p("工具商店包含7个本项目MIT适配器，知识检索为始终启用的核心能力。联网文献、公开网页、图片检索、CSV分析默认启用，PDF下载和笔记保存可按需启用。支持分类、搜索和持久化开关；应用没有把尚未安装的第三方MCP服务器标成可用工具。API资料与第三方图片遵循各自许可。")
p("启停状态存入工作空间SQLite；提交问答时保存工具快照并筛选模型工具列表，工具实验室在提交时检查开关，MCP在调用时检查最新开关。停用联网文献后的工具请求返回403，刷新后状态保留。侧栏支持项目新建、项目内对话、已有对话移动到项目，以及项目与对话置顶。")
endpage()

page("模型模板与自定义配置", "models")
image("08-settings.jpg", "设置弹窗：模型配置与独立LightRAG副本连接", max_height=365)
p("点击头像打开设置弹窗，选择模型与连接。关闭按钮、Esc或遮罩均可关闭；弹窗关闭后保留对话、证据和未发送草稿。预选DeepSeek、通义千问/百炼、智谱GLM，或填写任意OpenAI兼容接口。回答模型需要支持工具调用，图像模型需要支持图片输入；模板只是可编辑起点，模型可用性依具体服务账号而定。此次没有使用其他供应商密钥发起付费模型验证。")
p("配置API不返回密钥。留空可保留当前接口凭据，切换地址必须输入新服务密钥，避免把已有密钥转发给其他接口。保存原子更新项目.env并立即应用于后续任务；已有执行任务时拒绝修改。配置用于应用回答、研究规划与图片观察，LightRAG内部抽取及Jina嵌入沿用副本配置；原始知识库不变。")
endpage()

page("技术选型与覆盖口径", "coverage")
p(
    "参考飞书项目公开介绍中的16项技术选型，以已选择的 Python / AI 应用开发方向按对应能力核算：覆盖13项，13÷16=81.25%。这里的覆盖是技术能力等价实现，不是相同 Java 依赖、相同商业平台或相同业务场景的使用比例。"
)
p(
    "每项只有在本机有实际实现与验证证据时才计入。Serverless 尚未云端部署、Cursor 开发环境和 Ollama 本地模型部署均不计入。已提供的 Serverless 入口适配单测单独列明。"
)
table(
    ["参考技术", "Python 对应实现", "计入"],
    [[x["reference"], x["implementation"], "是" if x["covered"] else "否"] for x in coverage["items"][:8]],
    widths=[140, doc.width - 185, 45],
)
p(
    "PGvector 使用 PGlite 内的实际 PostgreSQL 与 pgvector 0.8.1 扩展，适合本机单进程演示；它不是独立部署的生产 PostgreSQL 集群。Java 后端与框架能力分别由 FastAPI、LangChain 和 LangGraph 替代。",
    "small",
)
endpage()

page("技术覆盖与验证证据", "coverage-evidence")
table(
    ["参考技术", "Python 对应实现", "计入"],
    [[x["reference"], x["implementation"], "是" if x["covered"] else "否"] for x in coverage["items"][8:]],
    widths=[140, doc.width - 185, 45],
)
h2("四个可复查的证据")
p(
    "模型与 Tool Calling：真实 DeepSeek 图文问答调用 analyze_pond_records。MCP：标准 SDK 客户端列出7个工具，图片与新增联网文献均有 stdio 协议调用记录。PGvector：真实1024维查询嵌入与数据库 cosine 检索，返回6个来源。"
)
p(
    "序列化：实际 research-checkpoints.sqlite 中 checkpoint 的 type 为 msgpack，审批恢复测试证明状态可以继续使用。这里覆盖序列化能力，没有声称测量过 Kryo 与 ormsgpack 的性能优劣。"
)
p(
    "完整逐项证据保存于 docs/technology-coverage.json。飞书参考：\nhttps://yuyuanweb.feishu.cn/wiki/D4VSwmWJviWiCekA78ocIZM5nz6",
    "small",
)
endpage()

page("系统架构与关键设计", "architecture")
image("architecture.png", "前端、API、智能体、模型与存储的连接", max_height=425)
p(
    "Vue 与 FastAPI 同源部署，默认8503提供页面与接口。LightRAG 副本固定9622，PGvector 固定8510，模型配置留在服务端。迁移加载器只在副本进程中替换快照读取函数，不改变上游持久化格式。"
)
p(
    "界面消息与任务事件用于产品呈现，LangGraph checkpoint 用于模型和工作流状态，运行指标用于观察耗时与工具调用。分开持久化这些职责，便于查找失败原因与恢复待审批任务。"
)
endpage()

page("持久化与运行边界", "persistence")
h2("会话与任务")
p(
    "同一个会话只允许一个进行中的问答，以避免 checkpoint 竞争。任务状态与事件落入 SQLite，SSE 支持事件编号重放；浏览器断开不会撤销后台任务。工作台最多2个执行线程，队列限制4个活动任务。"
)
p(
    "研究计划在审批节点持久化。服务重启后，待审批计划可以继续确认；正在执行和排队的任务标记失败。取消任务是协作式停止，已经发给供应商的调用需等待返回，不代表撤回已产生的费用。"
)
h2("工具与凭据范围")
p(
    "知识库写入只连接项目副本。网页工具仅接受白名单 HTTPS 地址，拒绝私有地址、任意主机、非标准端口和重定向。文件工具只写入项目资源目录，终端工具只执行固定 CSV 统计程序，不接受任意命令。"
)
p(
    "前端 Markdown 经 DOMPurify 清理。配置接口不返回密钥，API 写入请求检查本地 Origin，服务只绑定 loopback。当前应用是本机工作台，尚未实现公网多用户认证或权限体系。"
)
h2("进一步发展方向")
p(
    "生产扩展可以加入共享 PostgreSQL、独立任务队列、对象存储、细粒度权限、PGvector 增量同步与业务标注评测。Serverless 入口已有 HTTP 事件适配单测；完整云部署仍需替换本地数据库和后台线程，当前不计入覆盖。"
)
endpage()

page("GitHub 调研与实现来源", "github")
p(
    "前期调研从 LightRAG、LangGraph、RAG、多模态与智能体相关项目中筛选热度和适用性；GitHub 元数据及许可证状态保存在 research/github_projects.json。星标快照记录时间为2026年10月10日，不是长期固定排名。"
)
selected_names = {
    "HKUDS/LightRAG",
    "langchain-ai/langgraph",
    "langchain-ai/langchain",
    "fastapi/fastapi",
    "HKUDS/RAG-Anything",
    "langchain-ai/retrieval-agent-template",
}
selected = [x for x in projects if x.get("repository") in selected_names]
table(
    ["项目", "星标快照", "许可证状态"],
    [[x["repository"], f"{x.get('stars', 0):,}", x.get("license", "待核实")] for x in selected],
    widths=[doc.width - 170, 80, 90],
)
p(
    "项目自行实现业务工作台与编排代码，并复制本机已有 LightRAG 上游源码到 vendor 运行。retrieval-agent-template 用于研究检索工作流组织方式；课程学习仓库用于了解视频模块，不宣称取得商业课程完整源码。"
)
p(
    "Dify、Open WebUI、RAGFlow 等调研项目用于比较产品与技术方向，不构成本项目所有代码的直接来源。许可证未知、NOASSERTION 或未取得代码许可的仓库，不按开源许可直接复用。"
)
h2("来源与可复查链接")
for x in selected:
    p(x["repository"] + "  " + x["url"], "small")
endpage()

page("安装启动与日常使用", "run")
p(
    "项目目录：E:\\Projects\\deepseek-lightrag-agent。已配置本机直接在 PowerShell 执行 .\\start.ps1；首次准备依赖执行 .\\setup.ps1，然后运行启动脚本。"
)
table(
    ["入口", "地址 / 作用"],
    [
        ["工作台", "http://127.0.0.1:8503"],
        ["带图说明文档", "http://127.0.0.1:8503/guide/project-guide.html"],
        ["API 文档", "http://127.0.0.1:8503/docs 与 /redoc"],
        ["知识副本管理", "http://127.0.0.1:9622/webui/"],
        ["PGvector 状态", "http://127.0.0.1:8510/health"],
        ["停止", ".\\stop.ps1，仅停止本项目归属进程"],
    ],
    widths=[115, doc.width - 115],
)
h2("五步体验")
p(
    "1. 从知识问答开始，输入一个青蟹业务问题，查看带来源的回答。\n2. 上传图片或 CSV，比较观察结果、统计结果和文献结论。\n3. 在研究任务里输入目标，确认计划后等待报告，下载 PDF。\n4. 在图谱中选择实体，查看关系与描述，再发起实体问答。\n5. 打开工具实验室和运行观察，检查实际结果、耗时和 Token。"
)
h2("配置与备份")
p(
    "头像设置可保存回答模型和视觉模型，无需重启工作台；根目录 .env 持久化配置，runtime/lightrag/.env 保留知识库副本配置。不把兼容网关模型名直接当成官方服务名称。服务停止后备份 runtime 与私有配置，保留原始知识库的独立备份。"
)
p(
    "更多维护说明见 docs/operations.md。源码、依赖与数据路径都使用项目相对结构；私有知识数据、凭据和依赖缓存不提交 Git。",
    "small",
)
endpage()

page("本机验收与真实运行记录", "validation")
image("validation.png", "不同任务的一次真实运行耗时快照", max_height=240)
table(
    ["验证项", "实际结果"],
    [
        ["自动化测试", "21项通过；新增工具启停、项目置顶、工具过滤、图谱上限与模型密钥检查"],
        [
            "混合问答",
            f"8个来源，总耗时{live['chat_metrics']['elapsed_ms'] / 1000:.2f}s；首字{live['chat_metrics']['first_token_ms'] / 1000:.2f}s",
        ],
        ["研究报告", f"15个来源；审批恢复成功；执行阶段{live['research_metrics']['elapsed_ms'] / 1000:.2f}s"],
        ["图文与 CSV", f"6个来源；{vision['metrics']['elapsed_ms'] / 1000:.2f}s；实际统计工具调用"],
        ["PGvector", "1300条 / 1024维 / 扩展0.8.1，真实检索已验证"],
        ["原始存储", "12个文件SHA256与迁移快照一致"],
    ],
    widths=[105, doc.width - 105],
)
p(
    "这些结果用于证明流程可运行，没有形成规模化准确率、并发压测、生产 SLA 或农业诊断指标。插画和合成 CSV 只用于协议与工具验证，历史失败资料仍保留真实状态。"
)
p(
    "复查文件：docs/live-validation.json、multimodal-validation.json、download-validation.json。运行实时验收脚本会调用模型与嵌入服务，产生供应商费用。",
    "small",
)
endpage()

page("界面观察与移动端", "ui")
image("07-observability.jpg", "问答运行观察中的真实性能与工具记录", max_height=310)
image("09-mobile.jpg", "390像素宽移动端的工作台布局", max_height=215)
p(
    "桌面仅有一个会话与项目侧栏；工具与配置移入头像设置弹窗。390像素窄屏弹窗没有横向溢出，分类自动折行，右侧内容独立滚动；键盘焦点限制在弹窗内，关闭后回到头像按钮。移动端折叠侧栏，问答证据面板按需展开。研究与对话各自保留执行轨迹，切换页面时恢复对应回答的证据，避免历史研究过程混入问答面板。",
    "small",
)
endpage()

page("简历写法与面试演示", "interview")
h2("可以使用的项目描述")
p(
    "构建青蟹多模态研究工作台，使用 FastAPI、LangGraph、Vue 3 与 DeepSeek 实现持久化问答、图文观察、用户记录分析、可审批的研究任务和报告导出；接入 LightRAG 的约2.6万实体与2.8万关系图谱，并复制1,300条原文向量到独立 PostgreSQL pgvector 索引，提供可追溯证据和实际 MCP 工具调用。"
)
h2("六分钟演示顺序")
table(
    ["时间", "演示动作", "解释重点"],
    [
        ["0—1 分钟", "总览与业务范围", "资料、图片、CSV不是同一种证据"],
        ["1—2 分钟", "问答与来源面板", "原文、引用、本轮检索与多轮记忆"],
        ["2—3 分钟", "图文和CSV示例", "真实模型工具调用，注明示例性质"],
        ["3—4 分钟", "研究计划确认", "interrupt、checkpoint、resume"],
        ["4—5 分钟", "图谱与MCP工具", "有限子图、协议与真实返回结果"],
        ["5—6 分钟", "报告与运行观察", "解释耗时、局限和未部署项"],
    ],
    widths=[70, 155, doc.width - 225],
)
h2("需要准备的追问")
p(
    "为什么 LightRAG 与 PGvector 同时存在？LightRAG 提供图谱和原文联合检索，PGvector 快照验证另一条关系型向量检索路径；当前不自动同步。为什么使用两个 SQLite 层？工作台数据和智能体状态职责不同。为什么来源编号检查不能代表准确性？编号只证明来源存在，没有判断语义支持关系。"
)
p(
    "如何处理长任务和失败？事件持久化、协作式取消、审批状态恢复和明确失败记录。如何保证原始知识库不被改变？固定副本地址、启动与停止归属检查、复制后哈希核验。下一步会做什么？补业务标注评测、增量同步和完整云端任务基础设施。"
)
endpage()

page("交付文件与资料归属", "deliverables")
table(
    ["文件 / 目录", "用途"],
    [
        ["README.md", "项目入口、功能与验收概览"],
        ["docs/CrabGraph项目说明.pdf", "可分享的带图项目说明书"],
        ["docs/project-guide.html", "本地可浏览的带图说明文档"],
        ["docs/images", "真实页面截图、架构、流程与验证图"],
        ["docs/technology-coverage.json", "16项参考技术逐项对照"],
        ["docs/operations.md", "启动、维护、备份与运行边界"],
        ["src/crabgraph / frontend", "工作台后端与Vue源码"],
        ["tests / scripts", "自动化验证、迁移与构建脚本"],
    ],
    widths=[205, doc.width - 205],
)
p(
    "所有截图来自本机实际运行页面，架构与流程图按当前代码自行绘制。青蟹示意插画由项目绘制，作为协议测试样例；合成养殖 CSV 已注明用途。外部图片搜索结果保留原网页与许可，不混作用户现场图片。"
)
p(
    "工作台原始代码采用 MIT 许可；LightRAG、依赖与参考项目保留各自许可证。私有知识资料、凭据和个人环境不在工作台代码许可证中授权。GitHub 调研文件保存原始许可证状态，不把未知许可证解释为可任意复用。"
)
p(
    "参考公开项目说明、GitHub 上游与官方技术文档用于方案对照，不声明取得参考课程的全部源码或云服务。Serverless 完整部署、Cursor 环境与 Ollama 本地模型运行不计入当前81.25%的等价技术能力覆盖。"
)
endpage()


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("GuideBody", 8)
    canvas.setFillColor(colors.HexColor("#92a08b"))
    canvas.drawString(22 * mm, 12 * mm, "CRABGRAPH   项目说明   2026.10.10")
    canvas.drawRightString(188 * mm, 12 * mm, str(doc.page))
    canvas.restoreState()


doc.build(story, onFirstPage=footer, onLaterPages=footer)
css = """
:root{font-family:'Segoe UI','Microsoft YaHei',sans-serif;color:#25483c;background:#f1f5ee;font-size:15px;line-height:1.9}*{box-sizing:border-box}body{margin:0}a{color:#1e7d61}header{background:#184e42;color:#e9f1dc;padding:46px 7vw}header small{letter-spacing:3px;color:#b4c8ac}header h1{font-size:34px;margin:12px 0}header p{max-width:830px;color:#bacab1;font-size:14px}header a{display:inline-block;color:#184e42;background:#e9d8b7;padding:8px 18px;border-radius:7px;margin-top:13px;text-decoration:none}.layout{display:grid;grid-template-columns:225px minmax(0,1030px);gap:32px;max-width:1350px;margin:35px auto;padding:0 24px}aside{position:sticky;top:20px;align-self:start;background:#fcfdf7;border:1px solid #dfe7d5;border-radius:10px;padding:20px}aside strong{font-size:13px}aside a{display:block;font-size:12px;color:#758e62;text-decoration:none;padding:5px 0}main{min-width:0}section{padding:34px 40px;background:#fffefa;border:1px solid #e0e8d7;border-radius:12px;margin-bottom:24px;scroll-margin-top:20px}h2{font-size:24px;line-height:1.5;margin:0 0 23px}p{margin:14px 0;color:#607c64}.h2{font-size:19px;font-weight:600;color:#356448;margin-top:28px}.title{font-size:26px;color:#285744;font-weight:600}.label{font-size:11px;letter-spacing:2px;color:#8aa074}.small{font-size:12px;color:#899f75;overflow-wrap:anywhere}figure{margin:24px 0}figure img{width:100%;height:auto;display:block;border-radius:8px;border:1px solid #e0e8d6}figcaption{font-size:12px;color:#91a77e;margin-top:10px}.table-wrap{overflow:auto;margin:22px 0}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border:1px solid #dce4d2;padding:12px 14px;vertical-align:middle;text-align:left}th{background:#e7efe0;color:#5f8250}tr:nth-child(even)td{background:#f6f9f0}footer{text-align:center;font-size:12px;color:#92a481;padding:15px 0 35px}@media(max-width:900px){.layout{grid-template-columns:1fr}aside{position:static;display:flex;flex-wrap:wrap;gap:4px 18px}aside strong{width:100%}section{padding:25px}h2{font-size:22px}}@media(max-width:500px){header{padding:30px 22px}header h1{font-size:27px}.layout{padding:0 12px;gap:18px;margin-top:20px}section{padding:21px 18px;font-size:13px}th,td{font-size:11px;padding:9px}h2{font-size:20px}figure{margin:20px 0}}
"""
toc = [
    ("intro", "项目介绍"),
    ("business", "业务价值与亮点"),
    ("features", "功能梳理"),
    ("chat", "图文问答"),
    ("research", "研究计划与审批"),
    ("reports", "报告与引用"),
    ("documents", "知识资料"),
    ("graph", "图谱探索"),
    ("tools", "工具实验室"),
    ("mcp", "MCP接入"),
    ("market", "开源工具商店"),
    ("models", "模型模板配置"),
    ("coverage", "技术覆盖口径"),
    ("coverage-evidence", "覆盖与证据"),
    ("architecture", "系统架构"),
    ("persistence", "持久化设计"),
    ("github", "GitHub调研"),
    ("run", "安装与使用"),
    ("validation", "实际验收"),
    ("ui", "界面与移动端"),
    ("interview", "简历与面试"),
    ("deliverables", "交付与归属"),
]
nav = "".join(f'<a href="#{anchor}">{title}</a>' for anchor, title in toc)
html_doc = f'<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CrabGraph 青蟹智能体项目说明</title><style>{css}</style></head><body><header><small>CRABGRAPH · PROJECT HANDBOOK</small><h1>青蟹多模态智能体项目说明</h1><p>业务功能、技术对照、系统架构、真实界面、运行与面试演示。Python等价技术能力覆盖13/16，81.25%。</p><a href="CrabGraph项目说明.pdf">下载PDF说明书</a></header><div class="layout"><aside><strong>文档目录</strong>{nav}</aside><main>{"".join(html_sections)}</main></div><footer>CrabGraph · 2026年10月10日 · 图片与验证记录来自本机真实实现</footer></body></html>'
(DOCS / "project-guide.html").write_text(html_doc, encoding="utf-8")
print(
    json.dumps(
        {
            "pdf": "docs/CrabGraph项目说明.pdf",
            "html": "docs/project-guide.html",
            "figures": figure_count,
            "covered": covered,
            "coverage_percent": covered / 16 * 100,
        },
        ensure_ascii=False,
    )
)
