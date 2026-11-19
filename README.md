# railway-recruitment-parser

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

## Samples

- `samples/nanchang_2027_dazhuan.txt` — 中国铁路南昌局集团有限公司
  2027年招聘高校毕业生公告（二）,大专批 (source:
  https://rczp.china-railway.com.cn — 中国铁路人才招聘网)
- `samples/taiyuan_2027_dazhuan.txt` — 中国铁路太原局集团有限公司
  2027年招聘高校毕业生公告（二）,大专批 (source:
  https://www.crtyhr.com — 太铁招聘)

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
`totals_match` is true for both samples (row headcounts sum to the
announced totals).

## Tests

```bash
python3 tests/test_parser.py
```

Checks the parsed output against the headcounts published in the
announcements (Nanchang 1352 / Taiyuan 877) and the power-supply
post totals (Nanchang 76 / Taiyuan 65).
