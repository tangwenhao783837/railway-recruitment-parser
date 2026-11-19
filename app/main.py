"""FastAPI backend for the railway recruitment parser.

Wraps parser.py (standard library only) in a small web service:

- GET  /health                     health check
- GET  /bureaus                    parsed bureaus and their totals
- GET  /announcements/{bureau}     full parsed JSON for one bureau
- POST /parse                      parse raw announcement text -> JSON
- GET  /                           simple frontend (pick a bureau, see the
                                   parsed posts, deadlines and the
                                   power-supply breakdown)

Run it:

    pip install -r requirements.txt
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Then open http://localhost:8000/ in a browser.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser import parse_announcement  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE / "output"

app = FastAPI(
    title="railway-recruitment-parser",
    description="Parse Chinese railway bureau campus-recruitment "
    "announcements into structured JSON.",
    version="0.2.0",
)


class ParseRequest(BaseModel):
    text: str
    major: str = "铁道供电技术"


def _load_outputs() -> dict[str, dict]:
    results: dict[str, dict] = {}
    for path in sorted(OUTPUT_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        results[data["bureau"]] = data
    return results


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/bureaus")
def list_bureaus() -> list[dict]:
    data = _load_outputs()
    return [
        {
            "bureau": d["bureau"],
            "title": d["title"],
            "total_posts": d["total_posts"],
            "total_headcount": d["total_headcount"],
            "application_window": d["application_window"],
        }
        for d in data.values()
    ]


@app.get("/announcements/{bureau}")
def get_announcement(bureau: str) -> dict:
    data = _load_outputs()
    if bureau not in data:
        raise HTTPException(
            status_code=404, detail=f"no parsed announcement for bureau {bureau!r}"
        )
    return data[bureau]


@app.post("/parse")
def parse_text(req: ParseRequest) -> dict:
    return parse_announcement(req.text, major=req.major)


INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>铁路局招聘公告解析</title>
<style>body{font-family:sans-serif;max-width:720px;margin:2em auto;padding:0 1em}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:4px 8px;text-align:left}</style>
</head>
<body>
<h1>铁路局招聘公告解析</h1>
<select id="bureau"></select>
<div id="out">加载中…</div>
<script>
async function load() {
  const bureaus = await (await fetch('/bureaus')).json();
  const sel = document.getElementById('bureau');
  bureaus.forEach(b => {
    const o = document.createElement('option');
    o.value = b.bureau; o.textContent = b.bureau + ' ' + b.total_headcount + '人';
    sel.appendChild(o);
  });
  sel.onchange = show;
  show();
}
async function show() {
  const b = document.getElementById('bureau').value;
  const d = await (await fetch('/announcements/' + encodeURIComponent(b))).json();
  const rows = d.posts.map(p =>
    '<tr><td>' + p.title + '</td><td>' + p.headcount + '</td><td>' +
    p.majors.join('、') + '</td></tr>').join('');
  document.getElementById('out').innerHTML =
    '<h2>' + d.title + '</h2>' +
    '<p>报名：' + d.application_window.start + ' 至 ' + d.application_window.end +
    ' ｜ 流程：' + d.process.join(' → ') + '</p>' +
    '<p>供电岗 ' + d.power_supply.headcount + ' 人，铁道供电技术可报 ' +
    d.eligible_for_major.total_headcount + ' 人</p>' +
    '<table><tr><th>岗位</th><th>人数</th><th>专业要求</th></tr>' + rows + '</table>';
}
load();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML
