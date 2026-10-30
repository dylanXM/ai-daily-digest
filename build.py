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
import shutil
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
BASE_URL = "https://ai-daily-news.sweetai.work"
SITE_NAME = "AI Daily Digest"
SITE_DESC = "Every morning at 9:00 AM Eastern Time, a roundup of the previous day's AI news, trending AI projects on GitHub, and new AI products."

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Shared Sweet Hub snippets. Copied into site/snippets/ so Cloudflare Pages
# builds work (the build server has no access to ~/workspace).
def _read_snippet(name):
    p = Path(__file__).parent / "site" / "snippets" / name
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        print(f"[warn] snippet {name} not found, skipping")
        return ""

# Floating tip button: gift FAB + popover (replaces the old inline tip jar).
_TIP_FAB_HTML = re.sub(r"\A\s*<!--.*?-->\s*", "",
                       _read_snippet("tip-fab.html"), flags=re.S)
_TIP_FAB_CSS = _read_snippet("tip-fab.css")
_TIP_FAB_JS = _read_snippet("tip-fab.js")
# SweetAI shared Google login.
_AUTH_CSS = _read_snippet("sweetai-auth.css")
_AUTH_JS = _read_snippet("sweetai-auth.js")
# SweetAI network bar (cross-site footer links).
_NETWORK_BAR_HTML = _read_snippet("network-bar.html")


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
        .replace("{{OG_IMAGE}}", f"{BASE_URL}/assets/og.png")
        .replace("{{HOME_URL}}", f"{BASE_URL}/")
        .replace("{{ARCHIVE_URL}}", f"{BASE_URL}/archive.html")
        .replace("{{FEED_URL}}", f"{BASE_URL}/feed.xml")
        .replace("{{SPONSOR_URL}}", f"{BASE_URL}/sponsor.html")
        .replace("{{CSS}}", css)
        .replace("{{JS}}", js)
        .replace("{{CONTENT}}", content)
        .replace("{{TIP_FAB}}", _TIP_FAB_HTML)
        .replace("{{NETWORK_BAR}}", _NETWORK_BAR_HTML)
    )


def en_date(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%B %-d, %Y")
    except ValueError:
        return date_str


def fmt_published(published_at, fallback_date):
    """Format an ISO-8601 timestamp like 2026-10-18T09:00:00-04:00 nicely."""
    try:
        dt = datetime.fromisoformat(published_at)
        return dt.strftime("%b %-d, %Y, %-I:%M %p (UTC%z)")
    except (ValueError, TypeError):
        return fallback_date


# ---------- SEO helpers (search-traffic: long-tail issue titles/descriptions) ----------

def _trim_words(text, limit):
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:.\u2014- ")
    return cut + "\u2026"


def issue_headline(issue):
    """The issue's headline entity: first news title, else top repo / product."""
    for item in issue.get("news", []):
        if item.get("title"):
            return item["title"].strip()
    for repo in issue.get("github", []):
        if repo.get("name"):
            return repo["name"].strip()
    for prod in issue.get("products", []):
        if prod.get("name"):
            return prod["name"].strip()
    return "Daily AI Digest"


def issue_title(issue):
    """Long-tail title, e.g. 'AI News October 26, 2026: <headline> \u2014 AI Daily Digest'."""
    return f"AI News {en_date(issue['date'])}: {_trim_words(issue_headline(issue), 90)} \u2014 {SITE_NAME}"


def issue_desc(issue):
    """Meta description spliced from the issue's real news titles (no invented copy)."""
    titles = [n["title"].strip() for n in issue.get("news", []) if n.get("title")]
    parts = []
    if titles:
        parts.append("AI news: " + "; ".join(titles[:3]))
    repos = [r["name"].strip() for r in issue.get("github", []) if r.get("name")]
    if repos:
        parts.append("Trending on GitHub: " + ", ".join(repos[:3]))
    prods = [x["name"].strip() for x in issue.get("products", []) if x.get("name")]
    if prods:
        parts.append("New AI products: " + ", ".join(prods[:2]))
    desc = ". ".join(parts)
    if desc:
        desc += f". Daily AI digest for {en_date(issue['date'])}."
    else:
        desc = SITE_DESC
    return _trim_words(desc, 320)


def render_recent_index(issues):
    """Homepage index block: latest 7 issues with date + headline, for search/internal discovery."""
    items = []
    for issue in issues[:7]:
        date_str = issue["date"]
        items.append(
            f'<a class="archive-item" href="{BASE_URL}/{date_str}.html">'
            f'<span class="archive-date">\U0001F4C5 {en_date(date_str)}</span>'
            f'<span class="archive-stats">{escape(_trim_words(issue_headline(issue), 110))}</span>'
            f'<span class="archive-arrow">\u2192</span></a>'
        )
    return (
        '<section class="section"><div class="section-head"><h2>Recent Issues</h2>'
        f'<span class="count">{min(len(issues), 7)} issues</span></div>\n'
        + "\n".join(items) + "\n</section>"
    )


SUBSCRIBE_ENDPOINT = "https://ai-daily-subscribe.dylan-xm.workers.dev/subscribe"

SUBSCRIBE_BLOCK = """
<div class="subscribe-box">
  <h3>📬 Get AI Daily in your inbox</h3>
  <p>The same digest — AI news, trending GitHub projects, and new AI products — delivered every morning.</p>
  <form class="subscribe-form" data-subscribe-form>
    <input type="email" required placeholder="you@example.com" aria-label="Email address">
    <button type="submit">Subscribe</button>
  </form>
  <p class="subscribe-note">One email per morning. No spam, unsubscribe anytime.</p>
  <p class="subscribe-msg" data-subscribe-msg role="status"></p>
</div>
<script>
document.querySelectorAll('[data-subscribe-form]').forEach(function(f){
  f.addEventListener('submit', async function(e){
    e.preventDefault();
    var input = f.querySelector('input[type=email]');
    var msg = document.querySelector('[data-subscribe-msg]');
    var btn = f.querySelector('button');
    btn.disabled = true; msg.textContent = 'Subscribing\\u2026';
    try {
      var r = await fetch('__SUBSCRIBE_ENDPOINT__', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({email: input.value, source: 'ai-daily-web'})});
      var d = await r.json().catch(function(){ return {}; });
      if (r.ok && d.ok) {
        msg.textContent = d.already ? 'You are already subscribed — see you tomorrow morning.' : 'Subscribed! Your first digest arrives tomorrow morning.';
        f.reset();
      } else {
        msg.textContent = 'Please enter a valid email address.';
      }
    } catch (err) {
      msg.textContent = 'Something went wrong — please try again.';
    }
    btn.disabled = false;
  });
});
</script>
""".replace("__SUBSCRIBE_ENDPOINT__", SUBSCRIBE_ENDPOINT)


def render_sponsor(template, css, js):
    content = (
        '<div class="hero"><span class="hero-eyebrow">Sponsorship</span>'
        "<h1>Sponsor AI Daily Digest</h1>"
        "<p>AI Daily Digest is a daily briefing for people who build with and follow AI: "
        "the previous day's AI news, trending AI projects on GitHub, and new AI products — "
        "published on the web every morning at 9:00 AM ET, with a Chinese WeChat edition the same morning.</p></div>"
        '<section class="section"><div class="section-head"><h2>Placements</h2></div>'
        '<div class="product-grid">'
        '<article class="product-card"><span class="product-tag">Headline</span>'
        '<div class="product-name">Headline Sponsor</div>'
        '<p class="product-desc">Your brand at the top of the day\'s edition — the first thing readers see '
        "on the homepage and the day's issue page, with your name, one line about what you do, and your link.</p></article>"
        '<article class="product-card"><span class="product-tag">Section</span>'
        '<div class="product-name">Section Sponsor</div>'
        '<p class="product-desc">A sponsor block inside one section of the daily edition — AI News, '
        "Trending on GitHub, or New AI Products — matched to the readers most relevant to what you ship.</p></article>"
        '<article class="product-card"><span class="product-tag">WeChat</span>'
        '<div class="product-name">WeChat Edition</div>'
        '<p class="product-desc">A sponsor mention in the Chinese edition of the digest, published the same '
        "morning on our WeChat Official Account for Chinese readers.</p></article>"
        "</div></section>"
        '<div class="subscribe-box"><h3>🌱 Founding Sponsor</h3>'
        "<p>We are onboarding a small number of founding sponsors while the digest grows. "
        "Founding sponsors get founding placement and a direct line to us as formats evolve.</p>"
        "<p><strong>Founding rate — contact us</strong></p>"
        '<p style="margin-top:12px"><a class="btn" href="mailto:contact@sweetai.work?subject=AI%20Daily%20Digest%20sponsorship">contact@sweetai.work</a></p>'
        '<p class="subscribe-note">Tell us what you are launching and which placement you have in mind — we reply with availability and next steps.</p></div>'
    )
    return fill_template(
        template,
        f"Sponsor | {SITE_NAME}",
        "Sponsor AI Daily Digest: headline, section, and WeChat edition placements for AI products and tools.",
        f"{BASE_URL}/sponsor.html",
        content,
        css,
        js,
    )


# Cross-site promo: Tools Hub directory.
TOOLSHUB_PROMO = """
<div class="cross-promo"><h3>&#x1F6E0;&#xFE0F; Looking for AI tools?</h3>
<p>Browse <a href="https://tools-hub.sweetai.work/">200+ AI tools on Tools Hub</a> &mdash;
our curated directory across 10 categories, from chatbots to video generators.</p></div>
"""


def render_index(template, css, js, latest, issues):
    published = fmt_published(latest.get("published_at", ""), latest["date"])
    hero = (
        f'<div class="hero">'
        f'<span class="hero-eyebrow">Daily · Published 9:00 AM ET</span>'
        f"<h1>Today's AI Digest</h1>"
        f'<p>The most important AI news, the hottest AI projects on GitHub, and the newest AI products from the previous day — in 3 minutes.</p>'
        f'<div class="hero-meta"><span>🗓 {en_date(latest["date"])}</span>'
        f'<span class="publish-time">Published: {escape(published)}</span></div>'
        f"</div>"
    )
    content = hero + SUBSCRIBE_BLOCK + issue_sections(latest) + render_recent_index(issues) + TOOLSHUB_PROMO
    if len(issues) > 1:
        content += (
            f'<div class="more-link">'
            f'<a class="btn" href="{BASE_URL}/archive.html">Browse the full archive →</a></div>'
        )
    # Homepage sidebar ad slot
    content += "\n<!-- ADSENSE: sidebar -->\n<div class=\"ad-slot\"></div>"
    return fill_template(template, issue_title(latest), issue_desc(latest), f"{BASE_URL}/", content, css, js)


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
    content = hero + SUBSCRIBE_BLOCK + issue_sections(issue) + TOOLSHUB_PROMO
    content += "\n<!-- ADSENSE: sidebar -->\n<div class=\"ad-slot\"></div>"
    return fill_template(template, issue_title(issue), issue_desc(issue), f"{BASE_URL}/{date_str}.html", content, css, js)


def render_archive(template, css, js, issues):
    # Group by month (issues arrive newest-first).
    months = []
    by_month = {}
    for issue in issues:
        key = issue["date"][:7]
        if key not in by_month:
            by_month[key] = []
            months.append(key)
        by_month[key].append(issue)

    def archive_row(issue, label):
        date_str = issue["date"]
        return (
            f'<a class="archive-item" href="{BASE_URL}/{date_str}.html">'
            f'<span class="archive-date">\U0001F4C5 {en_date(date_str)}</span>'
            f'<span class="archive-stats">{escape(_trim_words(label, 120))}</span>'
            f'<span class="archive-arrow">\u2192</span></a>'
        )

    def topic_section(anchor, emoji, title, pick):
        rows = []
        for issue in issues:
            label = pick(issue)
            if label:
                rows.append(archive_row(issue, label))
        return (
            f'<section class="section" id="{anchor}"><div class="section-head">'
            f'<h2>{emoji} {title}</h2><span class="count">{len(rows)} issues</span></div>\n'
            + "\n".join(rows) + "\n</section>"
        )

    month_blocks = []
    month_links = []
    for key in months:
        try:
            mlabel = datetime.strptime(key + "-01", "%Y-%m-%d").strftime("%B %Y")
        except ValueError:
            mlabel = key
        month_links.append(f'<a href="#archive-{key}">{mlabel}</a>')
        rows = []
        for issue in by_month[key]:
            n = len(issue.get("news", []))
            g = len(issue.get("github", []))
            pr = len(issue.get("products", []))
            rows.append(archive_row(issue, f"{issue_headline(issue)}  \u00b7  \U0001F4F0 {n} \u00b7 \U0001F4BB {g} \u00b7 \U0001F680 {pr}"))
        month_blocks.append(
            f'<section class="section" id="archive-{key}"><div class="section-head">'
            f'<h2>{mlabel}</h2><span class="count">{len(rows)} issues</span></div>\n'
            + "\n".join(rows) + "\n</section>"
        )

    topics_nav = (
        '<nav class="section"><div class="section-head"><h2>Browse by Topic</h2></div>'
        '<p><a href="#ai-news">AI News</a> \u00b7 <a href="#github-trending">GitHub Trending</a> \u00b7 '
        '<a href="#new-products">New Products</a> \u00b7 ' + " \u00b7 ".join(month_links) + "</p></nav>"
    )
    content = (
        '<div class="hero"><span class="hero-eyebrow">All issues</span>'
        "<h1>Archive \u2014 Daily AI News, GitHub Trending &amp; New AI Products</h1>"
        "<p>Browse every daily AI digest by month and topic: the day's top AI news story, "
        "trending GitHub AI projects, and new AI product launches.</p></div>"
        + topics_nav
        + "\n".join(month_blocks)
        + topic_section("ai-news", "\U0001F4F0", "AI News \u2014 Top Story by Issue",
                        lambda i: i["news"][0]["title"] if i.get("news") else "")
        + topic_section("github-trending", "\U0001F4BB", "GitHub Trending \u2014 Top Project by Issue",
                        lambda i: i["github"][0]["name"] if i.get("github") else "")
        + topic_section("new-products", "\U0001F680", "New Products \u2014 Top Launch by Issue",
                        lambda i: i["products"][0]["name"] if i.get("products") else "")
    )
    desc = ("Archive of AI Daily Digest: daily AI news, trending GitHub AI projects, and new AI products, "
            "grouped by month with top stories for every issue.")
    return fill_template(
        template, f"Archive \u2014 AI News by Date & Topic | {SITE_NAME}", desc, f"{BASE_URL}/archive.html", content, css, js
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
    urls = [f"{BASE_URL}/", f"{BASE_URL}/archive.html", f"{BASE_URL}/sponsor.html"]
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


def render_ads_txt():
    # Google AdSense ads.txt (publisher ID verified from the user's AdSense account)
    return "google.com, pub-1672880630267493, DIRECT, f08c47fec0942fa0\n"


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
    # Shared snippets: floating tip button + SweetAI Google login.
    # Order: theme.js (tip PayPal logic) -> tip-fab.js -> sweetai-auth.js
    css = css + "\n" + _TIP_FAB_CSS + "\n" + _AUTH_CSS
    js = js + "\n" + _TIP_FAB_JS + "\n" + _AUTH_JS

    latest = issues[0]
    outputs = {
        "index.html": render_index(template, css, js, latest, issues),
        "archive.html": render_archive(template, css, js, issues),
        "sponsor.html": render_sponsor(template, css, js),
        "feed.xml": render_feed(issues),
        "sitemap.xml": render_sitemap(issues),
        "robots.txt": render_robots(),
        "ads.txt": render_ads_txt(),
    }
    for issue in issues:
        outputs[f"{issue['date']}.html"] = render_issue_page(template, css, js, issue)

    for name, text in outputs.items():
        path = DIST_DIR / name
        path.write_text(text, encoding="utf-8")
        print(f"[ok] {path.relative_to(ROOT)} ({len(text.encode('utf-8'))} bytes)")

    # Static assets (logo, og image) copied verbatim into dist/assets/.
    assets_src = SITE_DIR / "assets"
    if assets_src.is_dir():
        assets_dst = DIST_DIR / "assets"
        assets_dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(assets_src.iterdir()):
            if f.is_file():
                shutil.copyfile(f, assets_dst / f.name)
                print(f"[ok] dist/assets/{f.name} ({f.stat().st_size} bytes)")

    print(f"\nBuild complete: {len(issues)} issues, {len(outputs)} files -> {DIST_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
