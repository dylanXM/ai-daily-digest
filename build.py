#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Daily Digest - static site builder

Usage:
    python3 build.py            # reads content/*.json, generates dist/

Dependencies: Python 3 standard library only (json / html / datetime / pathlib / xml.sax.saxutils)
Input data contract: content/<date>.json (produced by the content pipeline; this script only reads).
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import escape
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
SITE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"

# Replace with the real domain after deployment (no trailing slash).
# Used for canonical / RSS / sitemap.
BASE_URL = "https://ai-daily.example.com"
SITE_NAME = "AI Daily Digest"
SITE_DESC = "Every morning at 10:00 (Beijing time), a roundup of the previous day's AI news, trending AI projects on GitHub, and new AI products."

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------- data loading ----------

def load_issues():
    """Read all contract-compliant JSON files under content/, newest first."""
    issues = []
    if not CONTENT_DIR.exists():
        return issues
    for path in sorted(CONTENT_DIR.glob("*.json")):
        if not DATE_RE.match(path.stem):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[warn] skipping {path.name}: {e}")
            continue
        data.setdefault("date", path.stem)
        data.setdefault("news", [])
        data.setdefault("github", [])
        data.setdefault("products", [])
        issues.append(data)
    issues.sort(key=lambda d: d["date"], reverse=True)
    return issues


# ---------- section rendering ----------

def render_news(news):
    parts = []
    for i, item in enumerate(news):
        title = escape(item.get("title", "Untitled"))
        summary = escape(item.get("summary", ""))
        source = escape(item.get("source", ""))
        url = escape(item.get("url", ""), quote=True)
        link = f'<a class="ext-link" href="{url}" target="_blank" rel="noopener">Read original ↗</a>' if url else ""
        parts.append(
            f'<article class="card">'
            f'<h3 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>'
            f'<p class="card-summary">{summary}</p>'
            f'<div class="card-meta"><span class="source">{source}</span>{link}</div>'
            f"</article>"
        )
        # Reserve an in-feed ad slot every 3 news items
        if (i + 1) % 3 == 0 and (i + 1) < len(news):
            parts.append("<!-- ADSENSE: in-feed -->\n<div class=\"ad-slot\"></div>")
    if not parts:
        parts.append('<p class="empty">No news today.</p>')
    return "\n".join(parts)


def render_github(repos):
    parts = []
    for i, repo in enumerate(repos, start=1):
        name = escape(repo.get("name", ""))
        desc = escape(repo.get("description", ""))
        url = escape(repo.get("url", ""), quote=True)
        stars = escape(repo.get("stars", ""))
        lang = escape(repo.get("language", ""))
        note = escape(repo.get("note", ""))
        lang_html = f'<span><span class="lang-dot"></span>{lang}</span>' if lang else ""
        stars_html = f'<span class="repo-stars">★ {stars}</span>' if stars else ""
        note_html = f'<p class="repo-note">{note}</p>' if note else ""
        parts.append(
            f'<article class="repo-card">'
            f'<div class="repo-rank">{i}</div>'
            f'<div class="repo-body">'
            f'<div class="repo-name"><a href="{url}" target="_blank" rel="noopener">{name}</a></div>'
            f'<p class="repo-desc">{desc}</p>'
            f"{note_html}"
            f'<div class="repo-meta">{lang_html}{stars_html}</div>'
            f"</div></article>"
        )
    if not parts:
        parts.append('<p class="empty">No trending repos today.</p>')
    return "\n".join(parts)


def render_products(products):
    parts = []
    for item in products:
        name = escape(item.get("name", ""))
        desc = escape(item.get("description", ""))
        url = escape(item.get("url", ""), quote=True)
        tag = escape(item.get("tag", ""))
        tag_html = f'<span class="product-tag">{tag}</span>' if tag else ""
        parts.append(
            f'<article class="product-card">{tag_html}'
            f'<div class="product-name"><a href="{url}" target="_blank" rel="noopener">{name}</a></div>'
            f'<p class="product-desc">{desc}</p></article>'
        )
    inner = "\n".join(parts) if parts else '<p class="empty">No new products today.</p>'
    return f'<div class="product-grid">\n{inner}\n</div>'


def section(emoji, title, body, count):
    return (
        f'<section class="section">'
        f'<div class="section-head"><h2>{emoji} {title}</h2>'
        f'<span class="count">{count} items</span></div>\n{body}\n</section>'
    )


def issue_sections(issue):
    news = issue.get("news", [])
    github = issue.get("github", [])
    products = issue.get("products", [])
    parts = [
        section("📰", "AI News", render_news(news), len(news)),
        "<!-- ADSENSE: in-article -->",
        section("💻", "Trending on GitHub", render_github(github), len(github)),
        "<!-- ADSENSE: in-article -->",
        section("🚀", "New AI Products", render_products(products), len(products)),
    ]
    return "\n".join(parts)


def page_urls(date_str):
    return {
        "home": f"{BASE_URL}/",
        "archive": f"{BASE_URL}/archive.html",
        "issue": f"{BASE_URL}/{date_str}.html",
        "feed": f"{BASE_URL}/feed.xml",
    }


# ---------- page rendering ----------

def fill_template(template, title, meta_desc, canonical, content, css, js):
    return (
        template.replace("{{TITLE}}", escape(title))
        .replace("{{META_DESC}}", escape(meta_desc))
        .replace("{{CANONICAL}}", escape(canonical, quote=True))
        .replace("{{HOME_URL}}", f"{BASE_URL}/")
        .replace("{{ARCHIVE_URL}}", f"{BASE_URL}/archive.html")
        .replace("{{FEED_URL}}", f"{BASE_URL}/feed.xml")
        .replace("{{CSS}}", css)
        .replace("{{JS}}", js)
        .replace("{{CONTENT}}", content)
    )


def en_date(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%B %-d, %Y")
    except ValueError:
        return date_str


def fmt_published(published_at, fallback_date):
    """Format an ISO-8601 timestamp like 2026-10-18T10:00:00+08:00 nicely."""
    try:
        dt = datetime.fromisoformat(published_at)
        return dt.strftime("%b %-d, %Y, %-I:%M %p (UTC%z)")
    except (ValueError, TypeError):
        return fallback_date


def render_index(template, css, js, latest, issues):
    published = fmt_published(latest.get("published_at", ""), latest["date"])
    hero = (
        f'<div class="hero">'
        f'<span class="hero-eyebrow">Daily · Published 10:00 AM</span>'
        f"<h1>Today's AI Digest</h1>"
        f'<p>The most important AI news, the hottest AI projects on GitHub, and the newest AI products from the previous day — in 3 minutes.</p>'
        f'<div class="hero-meta"><span>🗓 {en_date(latest["date"])}</span>'
        f'<span class="publish-time">Published: {escape(published)}</span></div>'
        f"</div>"
    )
    content = hero + issue_sections(latest)
    if len(issues) > 1:
        content += (
            f'<div class="more-link">'
            f'<a class="btn" href="{BASE_URL}/archive.html">Browse the full archive →</a></div>'
        )
    # Homepage sidebar ad slot
    content += "\n<!-- ADSENSE: sidebar -->\n<div class=\"ad-slot\"></div>"
    title = f"{en_date(latest['date'])} AI Digest | {SITE_NAME}"
    return fill_template(template, title, SITE_DESC, f"{BASE_URL}/", content, css, js)


def render_issue_page(template, css, js, issue):
    date_str = issue["date"]
    published = fmt_published(issue.get("published_at", ""), date_str)
    hero = (
        f'<div class="hero">'
        f'<span class="hero-eyebrow">From the archive</span>'
        f"<h1>{en_date(date_str)} · AI Digest</h1>"
        f'<div class="hero-meta"><span class="publish-time">Published: {escape(published)}</span></div>'
        f"</div>"
    )
    content = hero + issue_sections(issue)
    content += "\n<!-- ADSENSE: sidebar -->\n<div class=\"ad-slot\"></div>"
    title = f"{en_date(date_str)} AI Digest | {SITE_NAME}"
    desc = f"AI news, trending GitHub AI projects, and new AI products for {en_date(date_str)}."
    return fill_template(template, title, desc, f"{BASE_URL}/{date_str}.html", content, css, js)


def render_archive(template, css, js, issues):
    items = []
    for issue in issues:
        date_str = issue["date"]
        n = len(issue.get("news", []))
        g = len(issue.get("github", []))
        p = len(issue.get("products", []))
        items.append(
            f'<a class="archive-item" href="{BASE_URL}/{date_str}.html">'
            f'<span class="archive-date">🗓 {en_date(date_str)}</span>'
            f'<span class="archive-stats">📰 {n} · 💻 {g} · 🚀 {p}</span>'
            f'<span class="archive-arrow">→</span></a>'
        )
    content = (
        '<div class="hero"><span class="hero-eyebrow">All issues</span>'
        "<h1>Archive</h1><p>Browse every daily AI digest by date.</p></div>"
        '<section class="section">\n' + "\n".join(items) + "\n</section>"
    )
    return fill_template(
        template, f"Archive | {SITE_NAME}", SITE_DESC, f"{BASE_URL}/archive.html", content, css, js
    )


# ---------- RSS ----------

def render_feed(issues):
    items = []
    for issue in issues:
        date_str = issue["date"]
        link = f"{BASE_URL}/{date_str}.html"
        desc = (f"This issue covers {len(issue.get('news', []))} AI news stories, "
                f"{len(issue.get('github', []))} trending GitHub AI projects, "
                f"and {len(issue.get('products', []))} new AI products.")
        pub = issue.get("published_at", date_str)
        try:
            dt = datetime.fromisoformat(pub)
        except ValueError:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
        pub_rfc = dt.strftime("%a, %d %b %Y %H:%M:%S %z")
        items.append(
            f"<item>\n<title>{xml_escape(f'{en_date(date_str)} · AI Daily Digest')}</title>\n"
            f"<link>{xml_escape(link)}</link>\n"
            f"<guid>{xml_escape(link)}</guid>\n"
            f"<pubDate>{pub_rfc}</pubDate>\n"
            f"<description>{xml_escape(desc)}</description>\n</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n'
        f"<title>{xml_escape(SITE_NAME)}</title>\n"
        f"<link>{xml_escape(BASE_URL + '/')}</link>\n"
        f"<description>{xml_escape(SITE_DESC)}</description>\n"
        f'<atom:link href="{xml_escape(BASE_URL + "/feed.xml")}" rel="self" type="application/rss+xml"/>\n'
        "<language>en</language>\n"
        + "\n".join(items)
        + "\n</channel>\n</rss>\n"
    )


# ---------- sitemap / robots ----------

def render_sitemap(issues):
    urls = [f"{BASE_URL}/", f"{BASE_URL}/archive.html"]
    urls += [f"{BASE_URL}/{i['date']}.html" for i in issues]
    entries = "\n".join(
        f"<url><loc>{xml_escape(u)}</loc></url>" for u in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n</urlset>\n"
    )


def render_robots():
    return (
        f"User-agent: *\n"
        f"Allow: /\n\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )


# ---------- main ----------

def main():
    issues = load_issues()
    if not issues:
        print("[error] no usable JSON data under content/, nothing generated.")
        return 1

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    template = (SITE_DIR / "base.html").read_text(encoding="utf-8")
    css = (SITE_DIR / "style.css").read_text(encoding="utf-8")
    js = (SITE_DIR / "theme.js").read_text(encoding="utf-8")

    latest = issues[0]
    outputs = {
        "index.html": render_index(template, css, js, latest, issues),
        "archive.html": render_archive(template, css, js, issues),
        "feed.xml": render_feed(issues),
        "sitemap.xml": render_sitemap(issues),
        "robots.txt": render_robots(),
    }
    for issue in issues:
        outputs[f"{issue['date']}.html"] = render_issue_page(template, css, js, issue)

    for name, text in outputs.items():
        path = DIST_DIR / name
        path.write_text(text, encoding="utf-8")
        print(f"[ok] {path.relative_to(ROOT)} ({len(text.encode('utf-8'))} bytes)")

    print(f"\nBuild complete: {len(issues)} issues, {len(outputs)} files -> {DIST_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
