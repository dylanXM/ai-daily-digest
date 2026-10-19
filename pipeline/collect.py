#!/usr/bin/env python3
"""ai-daily daily content collection pipeline.

Usage:
    python3 collect.py [YYYY-MM-DD]

Without arguments, collects data for "yesterday". Collects three kinds of content:
  1. AI news       - Publisher RSS feeds (TechCrunch AI, The Decoder, MIT TR AI),
                     filtered by publish date, RSS description used as summary
  2. GitHub AI trends - GitHub API search, recent repos sorted by stars
  3. AI new products  - Publisher RSS launch items + Hacker News Show HN

Output: ~/workspace/ai-daily/content/YYYY-MM-DD.json (strictly follows the data contract)

If one category fails -> that category is an empty array, no fake data.
If all three are empty -> non-zero exit code.
"""

import sys
import os
import json
import re
import time
import html
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import date, timedelta, datetime, timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime

BASE = os.path.expanduser("~/workspace/ai-daily")
CONTENT = os.path.join(BASE, "content")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ai-daily-pipeline/1.0"}
FETCH_TIMEOUT = 18


# ---------------------------------------------------------------- utilities
def log(msg):
    print(msg, flush=True)


def http_get(url, timeout=FETCH_TIMEOUT, max_bytes=300000):
    """Returns (final_url, text); on failure returns (url, "")."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            final = r.geturl()
            raw = r.read(max_bytes)
        ctype = ""
        try:
            ctype = r.headers.get("Content-Type", "")
        except Exception:
            pass
        enc = "utf-8"
        m = re.search(r"charset=([\w-]+)", ctype or "")
        if m:
            enc = m.group(1)
        text = raw.decode(enc, errors="ignore")
        if not text.strip() and enc != "utf-8":
            text = raw.decode("utf-8", errors="ignore")
        return final, text
    except Exception as e:
        log(f"  [warn] fetch failed {url[:80]}: {e}")
        return url, ""


def format_stars(n):
    try:
        n = int(n)
    except Exception:
        return str(n)
    if n >= 1000:
        s = f"{n / 1000:.1f}k"
        return s.replace(".0k", "k")
    return str(n)


AI_WORD_RE = re.compile(
    r"(\bai\b|\bllm\b|\bgpt\b|\bmcp\b|\brag\b|\btts\b|\basr\b|"
    r"agent|agents|copilot|chatgpt|Muse|gemini|"
    r"deepseek|qwen|llama|mistral|sora|midjourney|diffusion|transformer|"
    r"machine learning|deep learning|neural|voice assistant|"
    r"text-to-speech|image generation|video generation)",
    re.I,
)


def looks_ai(text):
    return bool(text and AI_WORD_RE.search(text))


# ---------------------------------------------------------------- news
# Use publisher RSS feeds directly (real article links + built-in summaries)
NEWS_FEEDS = [
    # (rss url, source name)
    ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch"),
    ("https://the-decoder.com/feed/", "The Decoder"),
    ("https://www.technologyreview.com/topic/artificial-intelligence/feed/", "MIT Technology Review"),
]

BIG_KW = [
    "openai", "anthropic", "google", "deepmind", "deepseek", "meta", "nvidia",
    "microsoft", "apple", "release", "launches", "launched", "open source",
    "open-source", "model", "agent", "breakthrough",
]

FLUFF_RE = re.compile(r"(sponsored|advertorial|advertisement)", re.I)


def clean_html(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_rss_items(rss_text):
    items = []
    try:
        root = ET.fromstring(rss_text)
    except Exception:
        return items
    for it in root.iter("item"):
        title_el = it.find("title")
        link_el = it.find("link")
        pub_el = it.find("pubDate")
        src_el = it.find("source")
        desc_el = it.find("description")
        title = html.unescape((title_el.text or "").strip()) if title_el is not None and title_el.text else ""
        link = (link_el.text or "").strip() if link_el is not None and link_el.text else ""
        pub = (pub_el.text or "").strip() if pub_el is not None and pub_el.text else ""
        source = (src_el.text or "").strip() if src_el is not None and src_el.text else ""
        desc = (desc_el.text or "") if desc_el is not None and desc_el.text else ""
        if title and link:
            items.append({"title": title, "link": link, "pubDate": pub,
                          "source": source, "desc": desc})
    return items


def norm_title(t):
    t = t.lower()
    t = re.sub(r"[\s\-–—|:,!.\"'“”‘’()\[\]]+", "", t)
    return t


def item_day(pub):
    """RSS pubDate -> UTC date, returns None on parse failure."""
    try:
        dt = parsedate_to_datetime(pub)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date()
    except Exception:
        return None


def trim_summary(text, limit=200):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in [". ", "! ", "? "]:
        i = cut.rfind(sep)
        if i > 80:
            return cut[: i + 1].strip()
    return cut.rstrip() + "..."


def fetch_news(target):
    """Returns the news list (up to 12 items; fewer if real data is short)."""
    seen = set()
    scored = []
    for url, src_name in NEWS_FEEDS:
        _, rss = http_get(url, timeout=25, max_bytes=800000)
        if not rss:
            log(f"  [warn] news feed fetch failed: {src_name}")
            continue
        for it in parse_rss_items(rss):
            if item_day(it["pubDate"]) != target:
                continue
            title = it["title"]
            if FLUFF_RE.search(title):
                continue
            nt = norm_title(title)
            if not nt or nt in seen:
                continue
            if not looks_ai(title + " " + it["desc"]):
                continue
            seen.add(nt)
            summary = trim_summary(clean_html(it["desc"]))
            if not summary:
                continue
            score = sum(2 for kw in BIG_KW if kw in title.lower())
            scored.append((score, {
                "title": title,
                "summary": summary,
                "source": it["source"] or src_name,
                "url": it["link"],
            }))
        time.sleep(0.5)
    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:12]]


# ---------------------------------------------------------------- GitHub trends
def github_api(path):
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    headers = dict(UA)
    headers["Accept"] = "application/vnd.github+json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read(500000).decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        log(f"  [warn] GitHub API {e.code}: {path[:90]}")
        if e.code == 403:
            log("  [warn] GitHub API rate limited (403); consider setting GITHUB_TOKEN")
    except Exception as e:
        log(f"  [warn] GitHub API request failed: {e}")
    return None


def fetch_github(target, want=8):
    """Returns the github list: recently created AI repos sorted by stars."""
    since = (target - timedelta(days=7)).isoformat()
    queries = [
        f"AI agent in:name,description created:>={since}",
        f"llm in:name,description created:>={since}",
        f"topic:machine-learning created:>={since}",
    ]
    repos = {}
        path = "/search/repositories?" + urllib.parse.urlencode(
            {"q": q, "sort": "stars", "order": "desc", "per_page": 15}
        )
        data = github_api(path)
        if not data:
            continue
        for r in data.get("items", []):
            blob = f"{r.get('name', '')} {r.get('description') or ''}"
            if not looks_ai(blob):
                continue
            repos[r["full_name"]] = r
        time.sleep(2)  # unauthenticated search API is limited to 10 req/min

    ranked = sorted(repos.values(), key=lambda r: r.get("stargazers_count", 0), reverse=True)
    out = []
    for r in ranked[:want]:
        desc = (r.get("description") or "").strip()[:160]
        stars = format_stars(r.get("stargazers_count", 0))
        lang = r.get("language") or "Unknown"
        created = (r.get("created_at") or "")[:10]
        note = " \u00b7 ".join([f"Created {created}", f"{stars} stars", lang])
        out.append(
            {
                "name": r["full_name"],
                "description": desc,
                "url": r.get("html_url") or f"https://github.com/{r['full_name']}",
                "stars": stars,
                "language": lang,
                "note": note,
            }
        )
    return out


# ---------------------------------------------------------------- AI new products
PRODUCT_FEEDS = NEWS_FEEDS  # reuse publisher RSS, filter by launch keywords

LAUNCH_KW = ["launch", "launches", "launched", "unveil", "introduc", "debut",
             "release", "announce"]

TAG_RULES = [
    ("Agents", ["agent", "agents"]),
    ("LLM", ["llm", "gpt", "Muse", "gemini", "model", "deepseek", "qwen",
             "llama", "mistral"]),
    ("Image", ["image", "diffusion", "midjourney", "photo", "painting", "drawing"]),
    ("Video", ["video", "sora"]),
    ("Voice", ["voice", "tts", "speech", "text-to-speech", "voice synthesis"]),
    ("Audio", ["audio", "music", "podcast", "sound"]),
    ("Developer Tools", ["code", "coding", "developer", "copilot", "ide",
                         "debug", "programmer"]),
    ("Search", ["search"]),
    ("Productivity", ["productivity", "note", "todo", "workflow", "meeting",
                      "office"]),
    ("Hardware", ["wearable", "device", "chip", "glasses", "robot"]),
]


def tag_for(text):
    tl = (text or "").lower()
    for tag, kws in TAG_RULES:
        if any(kw in tl for kw in kws):
            return tag
    return "AI Tools"


def hn_show_hn_ai(target):
    """AI-related Show HN posts from Hacker News on the target day."""
    start = int(datetime(target.year, target.month, target.day, tzinfo=timezone.utc).timestamp())
    end = start + 86400
    url = (
        "https://hn.algolia.com/api/v1/search?tags=show_hn&hitsPerPage=60&numericFilters="
        + urllib.parse.quote(f"created_at_i>{start},created_at_i<{end}")
    )
    _, body = http_get(url, timeout=25)
    out = []
    if not body:
        return out
    try:
        data = json.loads(body)
    except Exception:
        return out
    for h in data.get("hits", []):
        title = (h.get("title") or "").strip()
        link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        if not title or not looks_ai(title):
            continue
        name = re.sub(r"^Show HN:\s*", "", title, flags=re.I).strip()
        out.append({"name": name, "url": link, "raw_title": title})
    return out


def fetch_products(target, want=7, exclude_urls=()):
    seen = set()
    products = []

    def push(name, description, url, tag):
        key = (name.lower(), urllib.parse.urlparse(url).netloc)
        if not name or key in seen:
            return False
        seen.add(key)
        products.append(
            {"name": name[:80], "description": description[:160], "url": url, "tag": tag}
        )
        return True

    excl = set(exclude_urls or ())
    # 1) launch-keyword items from publisher RSS feeds
    for url, src_name in PRODUCT_FEEDS:
        if len(products) >= want:
            break
        _, rss = http_get(url, timeout=25, max_bytes=800000)
        if not rss:
            continue
        for it in parse_rss_items(rss):
            if len(products) >= want:
                break
            if item_day(it["pubDate"]) != target:
                continue
            blob = it["title"] + " " + clean_html(it["desc"])
            if not looks_ai(blob):
                continue
            if not any(k in blob.lower() for k in LAUNCH_KW):
                continue
            if it["link"] in excl:
                continue
            name = it["title"]
            desc = clean_html(it["desc"])[:160] or name[:160]
            push(name, desc, it["link"], tag_for(blob))
        time.sleep(0.5)

    # 2) top up from Hacker News Show HN
    if len(products) < want:
        for h in hn_show_hn_ai(target):
            if len(products) >= want:
                break
            if h["url"] in excl:
                continue
            base = re.sub(r"^Show HN:\s*", "", h["raw_title"], flags=re.I).strip()
            desc = f"{base[:120].rstrip()} \u00b7 Spotted on Hacker News Show HN"
            push(h["name"], desc, h["url"], tag_for(h["raw_title"]))

    return products[:want]


# ---------------------------------------------------------------- main
def parse_date_arg(argv):
    if len(argv) >= 2:
        s = argv[1]
    else:
        s = (date.today() - timedelta(days=1)).isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        raise ValueError(f"Bad date format, expected YYYY-MM-DD: {s}")
    d = date.fromisoformat(s)
    if d > date.today():
        raise ValueError(f"Date cannot be in the future: {s}")
    return d


def main():
    try:
        target = parse_date_arg(sys.argv)
    except ValueError as e:
        log(f"[error] {e}")
        return 2
    log(f"=== ai-daily collect {target.isoformat()} ===")

    news, github, products = [], [], []
    try:
        log("[1/3] Collecting AI news ...")
        news = fetch_news(target)
        log(f"  -> {len(news)} news items")
    except Exception as e:
        log(f"  [error] news collection failed: {e}")
    try:
        log("[2/3] Collecting GitHub AI trends ...")
        github = fetch_github(target)
        log(f"  -> {len(github)} repos")
    except Exception as e:
        log(f"  [error] GitHub collection failed: {e}")
    try:
        log("[3/3] Collecting AI new products ...")
        products = fetch_products(target, exclude_urls=[n["url"] for n in news])
        log(f"  -> {len(products)} products")
    except Exception as e:
        log(f"  [error] product collection failed: {e}")

    if not news and not github and not products:
        log("[error] all three categories failed, writing nothing")
        return 1

    payload = {
        "date": target.isoformat(),
        "published_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
        "news": news,
        "github": github,
        "products": products,
    }
    os.makedirs(CONTENT, exist_ok=True)
    out_path = os.path.join(CONTENT, f"{target.isoformat()}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log(f"=== wrote {out_path} (news={len(news)}, github={len(github)}, products={len(products)}) ===")
    for name, items in (("news", news), ("github", github), ("products", products)):
        if not items:
            log(f"  [warn] {name} is an empty array")
    return 0


if __name__ == "__main__":
    sys.exit(main())
