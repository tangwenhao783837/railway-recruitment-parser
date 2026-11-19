"""Devin-bot workflow for the railway recruitment parser.

Runs on a schedule (every 30 minutes during recruitment season). The
announcement pages on the official site are JavaScript-rendered, so the
bot fetches each page with its own browser and saves the raw announcement
text; this script then takes that text and:

1. parses it with parser.py,
2. if the announcement is new or changed, saves the sample + output JSON,
   opens an automated pull request to the repo, and
3. posts a Slack alert with the summary (total headcount, power-supply
   posts, application deadline) and the auto-generated candidate matches
   for the configured candidate profile.

Credentials come from the environment, never from the code:

    GITHUB_TOKEN      personal access token with repo scope (for the PR)
    GITHUB_REPO       e.g. tangwenhao783837/railway-recruitment-parser
    SLACK_WEBHOOK_URL incoming webhook URL for the alerts channel

Usage:

    # preview what would happen for one announcement (no PR, no Slack):
    python3 bot/workflow.py --dry-run \
        --text-file samples/wuhan_2027_dazhuan.txt \
        --source-url https://rczp.china-railway.com.cn/page/platform/company_info_del.html?parentId=324&jmetazpxxid=11385

    # full run over every .txt file dropped in bot/inbox/:
    python3 bot/workflow.py --inbox bot/inbox

The state file bot/seen.json records which announcements have already
been processed, so a re-run only handles new or changed ones.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser import parse_announcement  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
STATE_FILE = BASE / "bot" / "seen.json"
INBOX_DIR = BASE / "bot" / "inbox"

# Candidate profile for the auto-generated matches: posts whose major list
# contains this major and whose education level matches are flagged.
CANDIDATE_PROFILE = {
    "major": "铁道供电技术",
    "education": "大专（高职）",
    "home_region": "南昌",
}


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def match_candidate(parsed: dict, profile: dict) -> dict:
    """Flag the posts a candidate with this profile can actually apply for."""
    eligible = [
        p
        for p in parsed["eligible_for_major"]["posts"]
        if parsed["education_level"] == profile["education"]
    ]
    power = parsed["power_supply"]
    return {
        "candidate_major": profile["major"],
        "education": profile["education"],
        "home_region": profile["home_region"],
        "eligible_posts": eligible,
        "eligible_headcount": sum(p["headcount"] or 0 for p in eligible),
        "power_supply_headcount": power["headcount"],
        "birthplace_priority_applies": parsed["birthplace_priority"],
    }


def slack_message(parsed: dict, match: dict, source_url: str) -> dict:
    return {
        "text": (
            f"【新公告】{parsed['title']}\n"
            f"总人数 {parsed['total_headcount']} 人 / {parsed['total_posts']} 岗，"
            f"报名 {parsed['application_window']['start']} 至 "
            f"{parsed['application_window']['end']}\n"
            f"供电岗 {parsed['power_supply']['headcount']} 人，"
            f"{match['candidate_major']}可报 {match['eligible_headcount']} 人\n"
            f"来源：{source_url}"
        )
    }


def send_slack(webhook_url: str, payload: dict) -> int:
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status


def github_api(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    url = f"https://api.github.com{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def open_pr(repo: str, token: str, branch: str, files: dict[str, str], title: str) -> dict:
    """Create a branch, commit files to it, and open a pull request."""
    main_ref = github_api("GET", f"/repos/{repo}/git/ref/heads/main", token)
    main_sha = main_ref["object"]["sha"]
    github_api(
        "POST",
        f"/repos/{repo}/git/refs",
        token,
        {"ref": f"refs/heads/{branch}", "sha": main_sha},
    )
    for path, content in files.items():
        github_api(
            "PUT",
            f"/repos/{repo}/contents/{path}",
            token,
            {
                "message": title,
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": branch,
            },
        )
    return github_api(
        "POST",
        f"/repos/{repo}/pulls",
        token,
        {"title": title, "head": branch, "base": "main", "body": title},
    )


def process_text(text: str, source_url: str, state: dict, dry_run: bool) -> str:
    """Parse announcement text and (unless dry-run) PR + alert it."""
    parsed = parse_announcement(text)
    key = parsed["title"]
    fingerprint = f"{parsed['total_headcount']}/{parsed['total_posts']}"
    if state.get(key) == fingerprint:
        return f"unchanged: {key}"
    match = match_candidate(parsed, CANDIDATE_PROFILE)
    sample_name = f"{parsed['bureau']}_2027_dazhuan"
    files = {
        f"samples/{sample_name}.txt": text,
        f"output/{sample_name}.json": json.dumps(
            parsed, ensure_ascii=False, indent=2
        ),
    }
    if dry_run:
        print(json.dumps(slack_message(parsed, match, source_url), ensure_ascii=False))
        print(f"[dry-run] would open PR with {len(files)} files")
        return f"new (dry-run): {key}"
    repo = os.environ["GITHUB_REPO"]
    token = os.environ["GITHUB_TOKEN"]
    branch = f"announcement/{sample_name}"
    pr = open_pr(repo, token, branch, files, f"Add {parsed['bureau']} 2027 announcement")
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook:
        send_slack(webhook, slack_message(parsed, match, source_url))
    state[key] = fingerprint
    return f"new: {key} -> PR #{pr.get('number')}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="parse and print only")
    ap.add_argument("--text-file", help="announcement text file to process")
    ap.add_argument("--source-url", default="", help="official page the text came from")
    ap.add_argument("--inbox", help="directory of .txt files to process")
    args = ap.parse_args(argv)

    jobs: list[tuple[str, str]] = []
    if args.text_file:
        jobs.append((Path(args.text_file).read_text(encoding="utf-8"), args.source_url))
    if args.inbox:
        for path in sorted(Path(args.inbox).glob("*.txt")):
            jobs.append((path.read_text(encoding="utf-8"), ""))
    if not jobs:
        ap.error("give --text-file or --inbox")

    state = load_state()
    for text, source_url in jobs:
        try:
            print(process_text(text, source_url, state, args.dry_run))
        except Exception as exc:  # keep processing the other files
            print(f"failed: {exc}", file=sys.stderr)
    if not args.dry_run:
        save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
