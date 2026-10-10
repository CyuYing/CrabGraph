"""Summarize user-provided measurements without inventing husbandry thresholds."""
import csv
import io
import math
import statistics

FIELDS = ("temperature", "ph", "dissolved_oxygen", "salinity", "ammonia_nitrogen")


def analyze_csv(text: str) -> dict:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames or not set(FIELDS).intersection(reader.fieldnames):
        raise ValueError("CSV 至少包含一个字段：" + ", ".join(FIELDS))
    rows = list(reader)
    if not rows or len(rows) > 5000:
        raise ValueError("CSV 应包含 1～5000 行记录")
    summary = {}
    invalid = 0
    for name in FIELDS:
        values = []
        for row in rows:
            value = row.get(name, "").strip()
            if not value:
                continue
            try:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError
                values.append(number)
            except ValueError:
                invalid += 1
        if values:
            summary[name] = {"count": len(values), "min": min(values), "max": max(values),
                             "mean": round(statistics.mean(values), 3),
                             "first": values[0], "last": values[-1],
                             "change": round(values[-1] - values[0], 3)}
    return {"rows": len(rows), "metrics": summary, "invalid_values": invalid,
            "note": "首末与变化按 CSV 行顺序计算；趋势是否适宜需结合知识库证据、测量单位及养殖阶段，未内置诊断阈值。"}
