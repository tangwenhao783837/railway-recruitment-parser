#!/usr/bin/env python3
"""Parse Chinese railway bureau campus-recruitment announcements into JSON.

Usage:
    python3 parser.py samples/nanchang_2027_dazhuan.txt
    python3 parser.py samples/*.txt [--major 铁道供电技术] [--out output]

Input: plain-text files holding one announcement each (title, body and the
post table, as copied from the official announcement page).
Output: one JSON file per input, written to the output directory.
Standard library only.

The parser handles the row layouts seen across bureaus:
- comma-separated rows with '专业要求：…' / '工作单位：…' markers
  (Nanchang, Taiyuan), including '专业要求与第N行相同' cross-references;
- labelled rows with '岗位编码/岗位名称/人数/学历/专业要求/单位/备注'
  fields separated by '；' (Wuhan, and other bureaus whose post table is
  an embedded HTML table).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Longest first: '网上资格审查与筛选' must win over '资格审查'.
STEP_PATTERNS = (
    "网上资格审查与筛选",
    "网上报名",
    "网上测评",
    "资格复审",
    "资格审查",
    "面试考核",
    "考试考核",
    "公示录用",
)
ROW_START = re.compile(r"(?m)^(\d+)[．.]\s*")
CODE_RE = re.compile(r"^\s*([A-Z]{2,}\d+|\d{8})")
ROW_LABELS = ("岗位编码", "岗位名称", "人数", "学历", "专业要求", "单位", "备注")


def _parse_majors(text: str) -> list[str]:
    """Split a '、'-separated major list, dropping the '及相近专业' tail."""
    text = text.strip().rstrip("。")
    text = re.sub(r"(及|等)相近专业$", "", text)
    text = text.rstrip("，、")
    return [p.strip() for p in re.split(r"[、，]", text) if p.strip()]


def _parse_units(text: str) -> list[dict]:
    """Parse '南昌供电段22人、鹰潭供电段2人' into unit/headcount pairs."""
    units: list[dict] = []
    for item in re.split(r"[、，]", text.strip()):
        item = item.strip().rstrip("。")
        if not item:
            continue
        m = re.match(r"(.+?)(\d+)人$", item)
        if m:
            units.append({"unit": m.group(1), "headcount": int(m.group(2))})
        else:
            units.append({"unit": item, "headcount": None})
    return units


def _parse_labeled_row(chunk: str) -> dict:
    """Parse a row whose fields are labelled, e.g. '岗位编码WHJ…；岗位名称：…；
    人数170人；学历：大专(高职)；专业要求：…；单位：…；备注：无。'"""
    fields: dict[str, str] = {}
    for part in chunk.split("；"):
        part = part.strip()
        for label in ROW_LABELS:
            if part.startswith(label):
                fields[label] = part[len(label):].strip("：: ").strip().rstrip("。")
                break
    headcount = None
    hm = re.search(r"(\d+)", fields.get("人数", ""))
    if hm:
        headcount = int(hm.group(1))
    remarks = fields.get("备注")
    if remarks in (None, "", "无", "（空）"):
        remarks = None
    return {
        "code": fields.get("岗位编码"),
        "title": fields.get("岗位名称"),
        "headcount": headcount,
        "majors": _parse_majors(fields.get("专业要求", "")),
        "units": _parse_units(fields.get("单位", "")),
        "remarks": remarks,
        "_majors_ref": None,
    }


def _parse_row(chunk: str) -> dict:
    """Parse one post-table row (either layout)."""
    chunk = chunk.strip()
    if "岗位编码" in chunk or "岗位名称" in chunk:
        return _parse_labeled_row(chunk)

    m = CODE_RE.match(chunk)
    code = m.group(1) if m else None
    rest = chunk[m.end():] if m else chunk

    hm = re.search(r"(\d+)人", rest)
    headcount = int(hm.group(1)) if hm else None
    title_raw = rest[: hm.start()] if hm else rest
    title = title_raw.strip("，、 ").replace("大专", "").strip("，、 ")

    majors: list[str] = []
    majors_ref: int | None = None
    mm = re.search(r"专业要求[:：]?\s*(.+?)(?:。|$)", rest, re.S)
    if mm:
        raw = mm.group(1).strip()
        paren = re.search(r"[（(](.+)[）)]", raw)
        ref_m = re.match(r"与第(\d+)行相同", raw)
        if paren:
            majors = _parse_majors(paren.group(1))
        elif ref_m:
            majors_ref = int(ref_m.group(1))
        else:
            majors = _parse_majors(raw)

    units: list[dict] = []
    um = re.search(r"(?:工作单位|工作地点|单位)[:：]\s*(.+?)(?:。|；|$)", rest, re.S)
    if um:
        units = _parse_units(um.group(1))

    remarks: str | None = None
    rm = re.search(r"备注[:：]\s*([^。]+)", rest)
    if rm:
        val = rm.group(1).strip()
        if val and val != "（空）":
            remarks = val

    return {
        "code": code,
        "title": title,
        "headcount": headcount,
        "majors": majors,
        "units": units,
        "remarks": remarks,
        "_majors_ref": majors_ref,
    }


def _parse_table(table_text: str) -> list[dict]:
    table_text = re.sub(r"\n合计\d+人。?\s*$", "", table_text.strip())
    parts = ROW_START.split(table_text)
    rows: list[dict] = []
    for i in range(1, len(parts), 2):
        rows.append(_parse_row(parts[i + 1]))
    # Resolve '与第N行相同' major cross-references.
    for row in rows:
        ref = row.pop("_majors_ref", None)
        if ref is not None and 1 <= ref <= len(rows):
            row["majors"] = rows[ref - 1]["majors"]
    return rows


def _parse_window(text: str) -> dict | None:
    m = re.search(
        r"报名时间[：为]?\s*(\d{4})年(\d{1,2})月(\d{1,2})日(?:至|-)(\d{1,2})月(\d{1,2})日",
        text,
    )
    if not m:
        return None
    year, sm, sd, em, ed = (int(g) for g in m.groups())
    return {
        "start": f"{year:04d}-{sm:02d}-{sd:02d}",
        "end": f"{year:04d}-{em:02d}-{ed:02d}",
    }


def _parse_process(text: str) -> list[str]:
    section = re.search(r"招聘流程[:：]?(.*?)(?:四、|$)", text, re.S)
    haystack = section.group(1) if section else text
    # Prefer the summary sentence ('按网上报名、…、公示录用等环节进行').
    intro = re.search(r"按(.+?)等环节进行", haystack)
    if intro:
        steps: list[str] = []
        for name in re.split(r"[、，]", intro.group(1)):
            name = name.strip()
            if name in STEP_PATTERNS and name not in steps:
                steps.append(name)
        if steps:
            return steps
    # Fallback: step names heading numbered items (avoids matching the same
    # words when they appear inside a step's description).
    pattern = r"(?:\d+[．.]|（[一二三四五]）)\s*(" + "|".join(STEP_PATTERNS) + ")"
    steps = []
    for m in re.finditer(pattern, haystack):
        if m.group(1) not in steps:
            steps.append(m.group(1))
    return steps


def _parse_education(text: str) -> str | None:
    if re.search(r"大专（高职）|大专\(高职\)|高职（大专）", text):
        return "大专（高职）"
    if re.search(r"本科及以上", text):
        return "本科及以上"
    if "本科" in text:
        return "本科"
    return None


def parse_announcement(text: str, major: str = "铁道供电技术") -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0] if lines else ""

    bureau_m = re.search(r"中国铁路(.+?局)集团有限公司", title)
    bureau = bureau_m.group(1) if bureau_m else None
    bureau_full = re.search(r"(中国铁路.+?集团有限公司)", title)
    no_m = re.search(r"(公告（[一二三]）)", title)
    src_m = re.search(r"来源[:：]\s*(https?://\S+)", text)

    total_m = re.search(r"本次计划招聘(\d+)人", text)
    total_headcount = int(total_m.group(1)) if total_m else None
    window = _parse_window(text)
    steps = _parse_process(text)
    phone_m = re.search(r"咨询电话[:：]?\s*(\d{3,4}-\d{7,8})", text)
    education = _parse_education(text)

    table_text = text.split("岗位信息表：", 1)[1] if "岗位信息表：" in text else ""
    rows = _parse_table(table_text) if table_text else []
    rows = [
        {
            "code": r["code"],
            "title": r["title"],
            "headcount": r["headcount"],
            "education": education,
            "majors": r["majors"],
            "units": r["units"],
            "remarks": r["remarks"],
        }
        for r in rows
    ]

    row_total = sum(r["headcount"] or 0 for r in rows)

    power_rows = [r for r in rows if "供电" in (r["title"] or "")]
    power_units: dict[str, int] = {}
    for r in power_rows:
        for u in r["units"]:
            if u["headcount"] is not None:
                power_units[u["unit"]] = power_units.get(u["unit"], 0) + u["headcount"]
    power_supply = {
        "post_count": len(power_rows),
        "headcount": sum(r["headcount"] or 0 for r in power_rows),
        "posts": [
            {"code": r["code"], "title": r["title"], "headcount": r["headcount"]}
            for r in power_rows
        ],
        "units": power_units,
    }

    eligible = [r for r in rows if major in r["majors"]]
    eligible_for_major = {
        "major": major,
        "post_count": len(eligible),
        "total_headcount": sum(r["headcount"] or 0 for r in eligible),
        "posts": [
            {"code": r["code"], "title": r["title"], "headcount": r["headcount"]}
            for r in eligible
        ],
    }

    return {
        "bureau": bureau,
        "bureau_full_name": bureau_full.group(1) if bureau_full else None,
        "title": title,
        "announcement_no": no_m.group(1) if no_m else None,
        "education_level": education,
        "total_posts": len(rows),
        "total_headcount": total_headcount,
        "row_headcount_sum": row_total,
        "totals_match": total_headcount is not None and row_total == total_headcount,
        "application_window": window,
        "process": steps,
        "has_written_exam": "考试考核" in steps or "笔试" in text,
        "one_post_limit": bool(re.search(r"每人限报[1一]个岗位", text)),
        "birthplace_priority": bool(
            re.search(r"工作(?:单位)?所在地生源优先", text)
        ),
        "contact_phone": phone_m.group(1) if phone_m else None,
        "source_url": src_m.group(1) if src_m else None,
        "posts": rows,
        "power_supply": power_supply,
        "eligible_for_major": eligible_for_major,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", help="announcement text file(s) to parse")
    ap.add_argument("--major", default="铁道供电技术",
                    help="major to report eligible posts for")
    ap.add_argument("--out", default="output", help="output directory")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    for path in args.files:
        src = Path(path)
        data = parse_announcement(src.read_text(encoding="utf-8"), major=args.major)
        dest = out_dir / (src.stem + ".json")
        dest.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        status = "OK " if data["totals_match"] else "WARN"
        print(
            f"[{status}] {src.name} -> {dest.name}: "
            f"{data['total_headcount']}人 / {data['total_posts']}岗 / "
            f"供电{data['power_supply']['headcount']}人 / "
            f"{args.major}可报{data['eligible_for_major']['total_headcount']}人"
        )
        ok = ok and data["totals_match"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
