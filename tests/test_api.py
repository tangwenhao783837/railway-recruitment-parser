"""Tests for the FastAPI backend (app/main.py) — the three endpoints the
integration plan describes, checked against the parsed samples on disk.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

client = TestClient(app)


class TestApi(unittest.TestCase):
    def test_health(self):
        self.assertEqual(client.get("/health").json(), {"status": "ok"})

    def test_bureaus_lists_three(self):
        bureaus = client.get("/bureaus").json()
        self.assertEqual({b["bureau"] for b in bureaus}, {"南昌局", "太原局", "武汉局"})
        totals = {b["bureau"]: b["total_headcount"] for b in bureaus}
        self.assertEqual(totals, {"南昌局": 1352, "太原局": 877, "武汉局": 1055})

    def test_announcement_wuhan(self):
        d = client.get("/announcements/武汉局").json()
        self.assertEqual(d["total_headcount"], 1055)
        self.assertTrue(d["totals_match"])
        self.assertEqual(d["power_supply"]["headcount"], 150)

    def test_announcement_unknown_is_404(self):
        self.assertEqual(client.get("/announcements/不存在局").status_code, 404)

    def test_parse_endpoint(self):
        text = (SAMPLES / "wuhan_2027_dazhuan.txt").read_text(encoding="utf-8")
        d = client.post("/parse", json={"text": text}).json()
        self.assertEqual(d["bureau"], "武汉局")
        self.assertTrue(d["totals_match"])
        self.assertEqual(d["eligible_for_major"]["total_headcount"], 150)

    def test_index_page_lists_bureaus(self):
        html = client.get("/").text
        self.assertIn("铁路局招聘公告解析", html)
        self.assertIn("/bureaus", html)


if __name__ == "__main__":
    unittest.main()
