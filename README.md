# railway-recruitment-parser

[![Tests](https://github.com/tangwenhao783837/railway-recruitment-parser/actions/workflows/test.yml/badge.svg)](https://github.com/tangwenhao783837/railway-recruitment-parser/actions/workflows/test.yml)

Parse real Chinese railway bureau campus-recruitment announcements
(HTML pages as saved from the official sites) into structured JSON.

## What it does

- Reads raw announcement text for a bureau's 2027 graduate recruitment batch
- Extracts: bureau, batch title, education level, number of posts,
  total headcount, application window, selection process, written-test /
  interview info, one-post limit, birthplace-priority clause, and the
  power-supply post breakdown (headcount by unit) when the post table
  is present in the text
- Writes one JSON file per announcement into `output/`

## Usage

```bash
python3 parser.py samples/nanchang_2027_dazhuan.txt
python3 parser.py samples/taiyuan_2027_dazhuan.txt
# or parse every sample at once:
python3 parser.py samples/*.txt
```

No third-party dependencies — Python 3 standard library only.

## Product layer

- `app/main.py` — FastAPI backend wrapping the parser:
  `GET /health`, `GET /bureaus`, `GET /announcements/{bureau}`,
  `POST /parse`, and a frontend at `GET /` (pick a bureau, see the
  parsed posts, deadlines and power-supply breakdown). Run it with
  `pip install -r requirements.txt && uvicorn app.main:app`.
- `bot/workflow.py` — the scheduled Devin-bot workflow. The official
  announcement pages are JavaScript-rendered, so the bot fetches each
  page with its own browser and saves the raw text; this script then
  parses new announcements, opens an automated PR with the new sample +
  output JSON, posts a Slack alert with the summary, and auto-generates
  candidate matches for the configured profile
  (`bot/workflow.py --dry-run --text-file samples/wuhan_2027_dazhuan.txt`).
  Credentials (`GITHUB_TOKEN`, `GITHUB_REPO`, `SLACK_WEBHOOK_URL`)
  come from the environment.

## Samples

- `samples/nanchang_2027_dazhuan.txt` — 中国铁路南昌局集团有限公司
  2027年招聘高校毕业生公告（二）,大专批 (source:
  https://rczp.china-railway.com.cn — 中国铁路人才招聘网)
- `samples/taiyuan_2027_dazhuan.txt` — 中国铁路太原局集团有限公司
  2027年招聘高校毕业生公告（二）,大专批 (source:
  https://www.crtyhr.com — 太铁招聘)
- `samples/wuhan_2027_dazhuan.txt` — 中国铁路武汉局集团有限公司
  2027年招聘高校毕业生公告（二）,大专批 (source:
  https://rczp.china-railway.com.cn — 中国铁路人才招聘网)

## Sample output

`output/nanchang_2027_dazhuan.json` (excerpt — full file in `output/`):

```json
{
  "bureau": "南昌局",
  "title": "中国铁路南昌局集团有限公司2027年度招聘大专（高职）毕业生公告（二）",
  "education_level": "大专（高职）",
  "total_posts": 11,
  "total_headcount": 1352,
  "application_window": {"start": "2026-11-16", "end": "2026-12-20"},
  "process": ["网上报名", "资格审查", "面试考核", "公示录用"],
  "has_written_exam": false,
  "one_post_limit": true,
  "birthplace_priority": true,
  "power_supply": {"headcount": 76,
    "units": {"南昌供电段": 22, "鹰潭供电段": 2, "福州供电段": 40, "厦门供电段": 12}},
  "eligible_for_major": {"major": "铁道供电技术",
    "post_count": 4, "total_headcount": 890}
}
```

Taiyuan parses the same way: 877人 / 10岗 / 报名 2026-11-19 至 11-30 /
流程含考试考核 / 供电 65人 / 铁道供电技术可报 480人.
Wuhan parses the same way: 1055人 / 10岗 / 报名 2026-11-18 至 11-30 /
流程 网上报名→网上资格审查与筛选→网上测评→资格复审→考试考核→公示录用 /
供电 150人 / 铁道供电技术可报 150人. Its post table uses a different
layout (labelled `岗位编码/岗位名称/人数/学历/专业要求/单位/备注`
fields separated by `；`), which the parser also handles.
`totals_match` is true for all three samples (row headcounts sum to the
announced totals).

## Tests

```bash
python -m unittest discover -s tests
```

Checks the parsed output against the headcounts published in the
announcements (Nanchang 1352 / Taiyuan 877 / Wuhan 1055) and the
power-supply post totals (Nanchang 76 / Taiyuan 65 / Wuhan 150).
28 tests, all passing (parser + API + workflow).
