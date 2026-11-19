"""Tests for bot/workflow.py — candidate matching and the dry-run path."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.workflow import (  # noqa: E402
    CANDIDATE_PROFILE,
    match_candidate,
    process_text,
    slack_message,
)
from parser import parse_announcement  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class TestWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (SAMPLES / "wuhan_2027_dazhuan.txt").read_text(encoding="utf-8")
        cls.parsed = parse_announcement(cls.text)

    def test_match_candidate(self):
        m = match_candidate(self.parsed, CANDIDATE_PROFILE)
        self.assertEqual(m["eligible_headcount"], 150)
        self.assertEqual(m["power_supply_headcount"], 150)
        self.assertTrue(m["birthplace_priority_applies"])

    def test_slack_message(self):
        msg = slack_message(
            self.parsed,
            match_candidate(self.parsed, CANDIDATE_PROFILE),
            "https://example.com",
        )
        self.assertIn("1055", msg["text"])
        self.assertIn("150", msg["text"])
        self.assertIn("2026-11-18", msg["text"])

    def test_process_text_dry_run(self):
        result = process_text(self.text, "https://example.com", {}, dry_run=True)
        self.assertTrue(result.startswith("new (dry-run)"))

    def test_process_text_unchanged(self):
        state = {self.parsed["title"]: "1055/10"}
        result = process_text(self.text, "", state, dry_run=True)
        self.assertTrue(result.startswith("unchanged"))


if __name__ == "__main__":
    unittest.main()
