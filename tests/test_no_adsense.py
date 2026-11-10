"""Regression tests: ai-daily-news must not ship AdSense code or ads.txt.

Run: python3 -m pytest tests/test_no_adsense.py -q
     (or: python3 -m unittest discover -s tests -v)
No network, no real tokens: the build runs locally on committed content.
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("adsbygoogle", "googlesyndication", "1672880630267493", "ca-pub-")


def _read(path):
    return path.read_text(encoding="utf-8", errors="ignore")


class TestNoAdSense(unittest.TestCase):
    def test_sources_have_no_adsense(self):
        sources = [ROOT / "build.py", ROOT / "site" / "base.html", ROOT / "site" / "style.css"]
        for src in sources:
            text = _read(src)
            for token in FORBIDDEN:
                self.assertNotIn(token, text, f"{token} found in {src.relative_to(ROOT)}")
            self.assertNotIn("ADSENSE", text, f"ADSENSE marker in {src.relative_to(ROOT)}")
            self.assertNotIn("ad-slot", text, f"ad-slot in {src.relative_to(ROOT)}")

    def test_build_output_has_no_adsense_and_no_ads_txt(self):
        result = subprocess.run(
            [sys.executable, "build.py"], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((ROOT / "dist" / "ads.txt").exists(), "dist/ads.txt must not exist")
        html_files = sorted((ROOT / "dist").glob("*.html"))
        self.assertGreater(len(html_files), 0)
        for page in html_files:
            text = _read(page)
            for token in FORBIDDEN:
                self.assertNotIn(token, text, f"{token} found in dist/{page.name}")
            self.assertNotIn("ADSENSE", text, f"ADSENSE marker in dist/{page.name}")

    def test_404_page_ships(self):
        # So the host returns a real 404 (not the SPA index fallback)
        # for removed paths such as /ads.txt.
        self.assertTrue((ROOT / "site" / "404.html").exists())
        subprocess.run([sys.executable, "build.py"], cwd=ROOT, capture_output=True, text=True)
        self.assertTrue((ROOT / "dist" / "404.html").exists())

    def test_key_pages_still_render(self):
        subprocess.run([sys.executable, "build.py"], cwd=ROOT, capture_output=True, text=True)
        for name in ("index.html", "archive.html", "sponsor.html", "tutorials.html"):
            page = ROOT / "dist" / name
            self.assertTrue(page.exists(), f"dist/{name} missing")
            self.assertIn("AI Daily Digest", _read(page))


if __name__ == "__main__":
    unittest.main()
