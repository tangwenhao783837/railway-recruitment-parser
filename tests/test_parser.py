"""Tests for parser.py — checked against the numbers published in the
announcements themselves (totals, post counts and power-supply headcounts).
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser import parse_announcement  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load(name: str) -> dict:
    text = (SAMPLES / name).read_text(encoding="utf-8")
    return parse_announcement(text)


class TestNanchang(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = load("nanchang_2027_dazhuan.txt")

    def test_totals(self):
        self.assertEqual(self.d["bureau"], "南昌局")
        self.assertEqual(self.d["total_headcount"], 1352)
        self.assertEqual(self.d["total_posts"], 11)
        self.assertTrue(self.d["totals_match"])

    def test_window_and_process(self):
        self.assertEqual(
            self.d["application_window"],
            {"start": "2026-11-16", "end": "2026-12-20"},
        )
        self.assertEqual(
            self.d["process"], ["网上报名", "资格审查", "面试考核", "公示录用"]
        )
        self.assertFalse(self.d["has_written_exam"])  # 面试, no written test
        self.assertTrue(self.d["one_post_limit"])
        self.assertTrue(self.d["birthplace_priority"])
        self.assertEqual(self.d["contact_phone"], "0791-87021951")

    def test_power_supply(self):
        ps = self.d["power_supply"]
        self.assertEqual(ps["headcount"], 76)
        self.assertEqual(
            ps["units"],
            {"南昌供电段": 22, "鹰潭供电段": 2, "福州供电段": 40, "厦门供电段": 12},
        )

    def test_eligible_for_railway_power_major(self):
        # Rows 1, 4, 5, 9 list 铁道供电技术: 289 + 500 + 25 + 76.
        self.assertEqual(self.d["eligible_for_major"]["total_headcount"], 890)

    def test_cross_reference_row(self):
        # Row 5 says '专业要求与第4行相同' — majors must resolve to row 4's.
        rows = {r["code"]: r for r in self.d["posts"]}
        self.assertEqual(
            rows["NCJ20270205"]["majors"], rows["NCJ20270204"]["majors"]
        )
        self.assertIn("铁道供电技术", rows["NCJ20270205"]["majors"])

    def test_row_unit_sums(self):
        for row in self.d["posts"]:
            known = [u["headcount"] for u in row["units"] if u["headcount"] is not None]
            if known:
                self.assertEqual(sum(known), row["headcount"], row["code"])


class TestTaiyuan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = load("taiyuan_2027_dazhuan.txt")

    def test_totals(self):
        self.assertEqual(self.d["bureau"], "太原局")
        self.assertEqual(self.d["total_headcount"], 877)
        self.assertEqual(self.d["total_posts"], 10)
        self.assertTrue(self.d["totals_match"])

    def test_window_and_process(self):
        self.assertEqual(
            self.d["application_window"],
            {"start": "2026-11-19", "end": "2026-11-30"},
        )
        self.assertEqual(
            self.d["process"], ["网上报名", "资格审查", "考试考核", "公示录用"]
        )
        self.assertTrue(self.d["has_written_exam"])  # 考试考核
        self.assertTrue(self.d["one_post_limit"])
        self.assertTrue(self.d["birthplace_priority"])
        self.assertEqual(self.d["contact_phone"], "0351-2622289")

    def test_power_supply(self):
        ps = self.d["power_supply"]
        self.assertEqual(ps["headcount"], 65)
        self.assertEqual(
            ps["units"],
            {"太原供电段": 20, "侯马北供电段": 10, "大同西供电段": 30, "临汾综合段": 5},
        )

    def test_eligible_for_railway_power_major(self):
        # Rows 4, 5, 9 list 铁道供电技术: 283 + 132 + 65.
        self.assertEqual(self.d["eligible_for_major"]["total_headcount"], 480)

    def test_remarks_and_single_unit_row(self):
        rows = {r["code"]: r for r in self.d["posts"]}
        self.assertEqual(rows["27230201"]["remarks"], "适宜男生")
        # Row 27230601 lists one unit with no per-unit headcount.
        self.assertEqual(
            rows["27230601"]["units"], [{"unit": "太原通信段", "headcount": None}]
        )

    def test_row_unit_sums(self):
        for row in self.d["posts"]:
            known = [u["headcount"] for u in row["units"] if u["headcount"] is not None]
            if known:
                self.assertEqual(sum(known), row["headcount"], row["code"])


if __name__ == "__main__":
    unittest.main()
