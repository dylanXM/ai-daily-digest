#!/usr/bin/env python3
"""
beehiiv_draft.py — 从 AI Daily Digest 的每日 JSON 生成 beehiiv newsletter 草稿。

用法:
    export BEEHIIV_PUBLICATION_ID="<publication_id>"
    export BEEHIIV_API_KEY="<api_key>"
    python3 beehiiv_draft.py [YYYY-MM-DD] [--dry-run]

不带日期时使用 content/ 目录下最新的 JSON。--dry-run 只打印将要发送的
payload，不调用 API。默认行为：创建 status=draft 的草稿，绝不会直接发出。

API 参考: https://www.beehiiv.com/support/article/36759164012439-using-the-send-api-and-create-post-endpoint
  POST https://api.beehiiv.com/v2/publications/{publication_id}/posts
  Auth: Bearer <api_key>
  body: { title, subtitle, blocks: [...], status: "draft" }
  注意: 不传 status 会立即发布给所有免费订阅者，所以必须显式传 "draft"。
"""

import html
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE / "content"
LOG_DIR = BASE / "logs"
SITE_URL = "https://ai-daily-news.sweetai.work"
API_BASE = "https://api.beehiiv.com/v2"


def esc(text):
    return html.escape(str(text or ""), quote=True)


def news_blocks(news):
    blocks = [{"type": "heading", "level": 1, "text": "Top AI News"}]
    for item in news:
        blocks.append({"type": "heading", "level": 3, "text": esc(item.get("title", ""))})
        if item.get("summary"):
            blocks.append({"type": "paragraph", "plaintext": esc(item["summary"])})
        src = esc(item.get("source", ""))
        url = esc(item.get("url", ""))
        if url:
            blocks.append({
                "type": "html",
                "html": f'<p style="font-size:14px;color:#666;">Source: {src} &nbsp;·&nbsp; '
                        f'<a href="{url}">Read more →</a></p>',
            })
    return blocks


def github_blocks(repos):
    blocks = [{"type": "heading", "level": 1, "text": "Trending on GitHub"}]
    for repo in repos:
        name = esc(repo.get("name", ""))
        stars = esc(repo.get("stars", ""))
        lang = esc(repo.get("language", ""))
        meta = " · ".join(p for p in [stars and f"⭐ {stars}", lang] if p)
        blocks.append({"type": "heading", "level": 3, "text": f"{name}  {meta}".strip()})
        desc = repo.get("description") or repo.get("note") or ""
        if desc:
            blocks.append({"type": "paragraph", "plaintext": esc(desc)})
        url = esc(repo.get("url", ""))
        if url:
            blocks.append({
                "type": "html",
                "html": f'<p style="font-size:14px;color:#666;"><a href="{url}">View on GitHub →</a></p>',
            })
    return blocks


def product_blocks(products):
    blocks = [{"type": "heading", "level": 1, "text": "New AI Products"}]
    for prod in products:
        name = esc(prod.get("name", ""))
        tag = esc(prod.get("tag", ""))
        title = f"{name}  [{tag}]" if tag else name
        blocks.append({"type": "heading", "level": 3, "text": title.strip()})
        if prod.get("description"):
            blocks.append({"type": "paragraph", "plaintext": esc(prod["description"])})
        url = esc(prod.get("url", ""))
        if url:
            blocks.append({
                "type": "html",
                "html": f'<p style="font-size:14px;color:#666;"><a href="{url}">Visit product →</a></p>',
            })
    return blocks


def build_payload(data):
    date = data.get("date", "")
    news = data.get("news", [])
    repos = data.get("github", [])
    products = data.get("products", [])

    blocks = [
        {"type": "paragraph",
         "plaintext": f"Your daily briefing on what's happening in AI — {date}."},
    ]
    if news:
        blocks += news_blocks(news)
    if repos:
        blocks += github_blocks(repos)
    if products:
        blocks += product_blocks(products)
    blocks.append({
        "type": "html",
        "html": '<hr><p style="font-size:13px;color:#888;">Read the full archive at '
                f'<a href="{SITE_URL}">{SITE_URL}</a>. '
                "You're receiving this because you subscribed to AI Daily Digest.</p>",
    })

    return {
        "title": f"AI Daily Digest — {date}",
        "subtitle": (f"{len(news)} AI stories · {len(repos)} trending repos · "
                     f"{len(products)} new products"),
        "blocks": blocks,
        "status": "draft",  # 草稿：用户在 beehiiv 后台检查后手动发送
    }


def create_draft(publication_id, api_key, payload):
    url = f"{API_BASE}/publications/{publication_id}/posts"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def latest_json():
    files = sorted(CONTENT_DIR.glob("*.json"))
    if not files:
        raise SystemExit("content/ 目录下没有 JSON 文件")
    return files[-1]


# ---------------------------------------------------------------------------
# --render-only: 把 newsletter 渲染成可直接粘贴进 Beehiiv HTML block 的独立 HTML
# ---------------------------------------------------------------------------

EMAIL_SHELL_OPEN = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title></head>""" \
    """<body><table width="100%" cellpadding="0" cellspacing="0"><tr>""" \
    """<td style="font-family:Arial,Helvetica,sans-serif;color:#111111;font-size:16px;""" \
    """line-height:1.6;max-width:600px;margin:0 auto;display:block;">"""
EMAIL_SHELL_CLOSE = """<p style="color:#888888;font-size:13px;margin-top:28px;border-top:1px solid #dddddd;""" \
    """padding-top:12px;">Thanks for reading. Reply to this email with feedback — we read every reply.</p>""" \
    """</td></tr></table></body></html>"""
H2 = ('<h2 style="font-size:20px;border-bottom:2px solid #111111;padding-bottom:6px;'
      '{extra}">{text}</h2>')
H3_LINK = ('<h3 style="font-size:17px;margin:18px 0 6px;"><a href="{url}" '
           'style="color:#1a56db;text-decoration:none;">{text}</a>{meta}</h3>')


def render_daily_html(data):
    date = data.get("date", "")
    parts = [EMAIL_SHELL_OPEN.format(title=f"AI Daily Digest \u2014 {date}")]
    parts.append('<h1 style="font-size:24px;margin:0 0 4px;">\U0001f916 AI Daily Digest</h1>')
    parts.append(
        f'<p style="color:#666666;font-size:14px;margin:0 0 24px;">{esc(date)} \u00b7 '
        "Top AI news, GitHub trends &amp; new AI products, curated daily.</p>")

    news = data.get("news", [])
    if news:
        parts.append(H2.format(extra="", text="\U0001f4f0 Top AI News"))
        for item in news:
            parts.append(H3_LINK.format(url=esc(item.get("url", "#")),
                                        text=esc(item.get("title", "")), meta=""))
            if item.get("summary"):
                parts.append(f'<p style="margin:0 0 4px;">{esc(item["summary"])}</p>')
            if item.get("source"):
                parts.append(f'<p style="margin:0 0 12px;color:#888888;font-size:13px;">'
                             f'Source: {esc(item["source"])}</p>')

    repos = data.get("github", [])
    if repos:
        parts.append(H2.format(extra="margin-top:28px;", text="\U0001f680 GitHub AI Trends"))
        for repo in repos:
            stars = esc(repo.get("stars", ""))
            lang = esc(repo.get("language", ""))
            meta_bits = " \u00b7 ".join(p for p in [stars and f"\u2b50 {stars}", lang] if p)
            meta = (f' <span style="color:#888888;font-size:13px;">{meta_bits}</span>'
                    if meta_bits else "")
            parts.append(H3_LINK.format(url=esc(repo.get("url", "#")),
                                        text=esc(repo.get("name", "")), meta=meta))
            desc = repo.get("description") or repo.get("note") or ""
            if desc:
                parts.append(f'<p style="margin:0 0 12px;">{esc(desc)}</p>')

    products = data.get("products", [])
    if products:
        parts.append(H2.format(extra="margin-top:28px;", text="\U0001f195 New AI Products"))
        for prod in products:
            tag = esc(prod.get("tag", ""))
            meta = (f' <span style="background:#eef2ff;color:#1a56db;font-size:12px;'
                    f'padding:2px 8px;border-radius:10px;">{tag}</span>' if tag else "")
            parts.append(H3_LINK.format(url=esc(prod.get("url", "#")),
                                        text=esc(prod.get("name", "")), meta=meta))
            if prod.get("description"):
                parts.append(f'<p style="margin:0 0 12px;">{esc(prod["description"])}</p>')

    parts.append(EMAIL_SHELL_CLOSE)
    return "".join(parts)


# ---------------------------------------------------------------------------
# --weekly: SweetAI Weekly — 全网精华 5 板块（每周一美东生成）
# ---------------------------------------------------------------------------

def _iso_week(anchor):
    from datetime import date as _date
    d = _date.fromisoformat(anchor) if isinstance(anchor, str) else anchor
    return d.isocalendar()[1]


def _load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def render_weekly_html(anchor_date):
    """anchor_date: YYYY-MM-DD（流水线传来的 YESTERDAY，即周一前一天的周日）。"""
    from datetime import date as _date, timedelta
    anchor = _date.fromisoformat(anchor_date)
    week_no = _iso_week(anchor)
    week_label = f"{anchor.isocalendar()[0]}-W{week_no:02d}"

    parts = [EMAIL_SHELL_OPEN.format(title=f"SweetAI Weekly \u2014 {week_label}")]
    parts.append('<h1 style="font-size:24px;margin:0 0 4px;">\u2728 SweetAI Weekly</h1>')
    parts.append(
        f'<p style="color:#666666;font-size:14px;margin:0 0 24px;">Week {esc(week_label)} \u00b7 '
        "The best of AI, tools and the wider web \u2014 curated by SweetAI.</p>")

    # 1) 本周 AI 要闻回顾：近 7 天去重
    seen, week_news = set(), []
    for i in range(7):
        day = anchor - timedelta(days=i)
        day_data = _load_json(CONTENT_DIR / f"{day.isoformat()}.json", {})
        for item in day_data.get("news", []):
            key = (item.get("title") or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                week_news.append(item)
            if len(week_news) >= 8:
                break
        if len(week_news) >= 8:
            break
    if week_news:
        parts.append(H2.format(extra="", text="\U0001f4f0 This Week in AI"))
        for item in week_news:
            parts.append(H3_LINK.format(url=esc(item.get("url", "#")),
                                        text=esc(item.get("title", "")), meta=""))
            if item.get("summary"):
                parts.append(f'<p style="margin:0 0 4px;">{esc(item["summary"])}</p>')
            if item.get("source"):
                parts.append(f'<p style="margin:0 0 12px;color:#888888;font-size:13px;">'
                             f'Source: {esc(item["source"])}</p>')

    # 2) Tool Spotlight：tools.json 按 ISO 周轮换
    tools_data = _load_json(Path.home() / "workspace/ai-tools/content/tools.json", {})
    tools = tools_data.get("tools", []) if isinstance(tools_data, dict) else []
    if tools:
        tool = tools[week_no % len(tools)]
        tid = tool.get("id", "")
        parts.append(H2.format(extra="margin-top:28px;", text="\U0001f6e0\ufe0f Tool Spotlight"))
        parts.append(H3_LINK.format(
            url=f"https://tools-hub.sweetai.work/tool/{tid}.html",
            text=esc(tool.get("name", "")), meta=""))
        if tool.get("tagline"):
            parts.append(f'<p style="margin:0 0 4px;font-weight:bold;">{esc(tool["tagline"])}</p>')
        if tool.get("description"):
            desc = esc(tool["description"])[:400]
            parts.append(f'<p style="margin:0 0 12px;">{desc}</p>')

    # 3) Localcraft 推荐：快照按 ISO 周轮换
    lc_tools = _load_json(CONTENT_DIR / "localcraft_tools.json", [])
    if lc_tools:
        lc = lc_tools[week_no % len(lc_tools)]
        route = lc.get("route", "")
        parts.append(H2.format(extra="margin-top:28px;", text="\U0001f9f0 From Localcraft"))
        parts.append(H3_LINK.format(
            url=f"https://tools.sweetai.work/{route}/",
            text=esc(lc.get("name", "")), meta=""))
        parts.append('<p style="margin:0 0 12px;color:#555555;font-size:14px;">'
                     "Free, private, runs 100% in your browser \u2014 no uploads, no sign-up.</p>")

    # 4) Wallpaper of the Week：wallhaven 热链图
    wp_data = _load_json(Path.home() / "workspace/wallpapers/content/wallpapers.json", [])
    wallpapers = wp_data if isinstance(wp_data, list) else wp_data.get("wallpapers", [])
    if wallpapers:
        wp = wallpapers[week_no % len(wallpapers)]
        wid = wp.get("id", "")
        img = wp.get("image", "")
        parts.append(H2.format(extra="margin-top:28px;",
                               text="\U0001f5bc\ufe0f Wallpaper of the Week"))
        if img:
            parts.append(
                f'<p style="margin:12px 0;"><a href="https://wallpapers.sweetai.work/w/{wid}/">'
                f'<img src="{esc(img)}" alt="{esc(wid)}" '
                'style="width:100%;max-width:560px;border-radius:8px;"></a></p>')
        parts.append(
            f'<p style="margin:0 0 12px;"><a href="https://wallpapers.sweetai.work/w/{wid}/" '
            f'style="color:#1a56db;">Download this wallpaper \u2192</a></p>')

    # 5) Game of the Week：评分 Top 池按 ISO 周轮换，Steam 封面热链
    game_data = _load_json(Path.home() / "workspace/game-hub/content/games.json", [])
    games = game_data if isinstance(game_data, list) else game_data.get("games", [])
    if games:
        pool = sorted(games, key=lambda g: g.get("rating", 0), reverse=True)[:60]
        game = pool[week_no % len(pool)]
        gid = game.get("id", "")
        parts.append(H2.format(extra="margin-top:28px;", text="\U0001f3ae Game of the Week"))
        if game.get("cover"):
            parts.append(
                f'<p style="margin:12px 0;"><a href="https://games.sweetai.work/game/{gid}.html">'
                f'<img src="{esc(game["cover"])}" alt="{esc(game.get("name", ""))}" '
                'style="width:100%;max-width:560px;border-radius:8px;"></a></p>')
        parts.append(H3_LINK.format(url=f"https://games.sweetai.work/game/{gid}.html",
                                    text=esc(game.get("name", "")), meta=""))
        if game.get("tagline"):
            parts.append(f'<p style="margin:0 0 4px;font-weight:bold;">{esc(game["tagline"])}</p>')
        if game.get("description"):
            parts.append(f'<p style="margin:0 0 12px;">{esc(game["description"])[:400]}</p>')

    parts.append(EMAIL_SHELL_CLOSE)
    return "".join(parts)


def main():
    raw = sys.argv[1:]
    weekly = "--weekly" in raw
    render_only = "--render-only" in raw
    dry_run = "--dry-run" in raw

    def flag_value(name):
        if name in raw:
            i = raw.index(name)
            if i + 1 < len(raw):
                return raw[i + 1]
        return None

    if render_only:
        out_path = flag_value("--out")
        date_arg = flag_value("--date")
        if not out_path or not date_arg:
            raise SystemExit("用法: beehiiv_draft.py [--weekly] --render-only --date YYYY-MM-DD --out PATH")
        if weekly:
            html_out = render_weekly_html(date_arg)
            label = "SweetAI Weekly"
        else:
            json_path = CONTENT_DIR / f"{date_arg}.json"
            if not json_path.exists():
                raise SystemExit(f"找不到文件: {json_path}")
            data = json.loads(json_path.read_text(encoding="utf-8"))
            html_out = render_daily_html(data)
            label = f"AI Daily Digest {date_arg}"
        Path(out_path).write_text(html_out, encoding="utf-8")
        print(f"HTML written to {out_path}")
        print("Paste it into Beehiiv: Write -> new post -> use an HTML snippet block, "
              "or paste into the editor, then review & send.")
        print(f"[beehiiv] {label} rendered, {len(html_out)} bytes")
        return

    # 旧行为：API 建草稿（免费版 API 只读，此路径已搁置，保留备用）
    args = [a for a in raw if a != "--dry-run"]
    json_path = Path(args[0]) if args else latest_json()
    if not json_path.is_absolute():
        json_path = CONTENT_DIR / f"{args[0]}.json"
    if not json_path.exists():
        raise SystemExit(f"找不到文件: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    payload = build_payload(data)
    print(f"[beehiiv] 内容日期: {data.get('date')}，blocks: {len(payload['blocks'])}")

    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:3000])
        print("... (dry-run，未发送)")
        return

    publication_id = os.environ.get("BEEHIIV_PUBLICATION_ID", "").strip()
    api_key = os.environ.get("BEEHIIV_API_KEY", "").strip()
    if not publication_id or not api_key:
        raise SystemExit("缺少环境变量 BEEHIIV_PUBLICATION_ID / BEEHIIV_API_KEY")

    status, result = create_draft(publication_id, api_key, payload)
    if status in (200, 201, 202):
        post_id = (result.get("data") or {}).get("id", "?")
        print(f"[beehiiv] 草稿已创建: post_id={post_id}")
        LOG_DIR.mkdir(exist_ok=True)
        (LOG_DIR / f"beehiiv_{data.get('date')}.done").write_text(post_id + "\n")
    else:
        raise SystemExit(f"创建草稿失败 (HTTP {status}): {result}")


if __name__ == "__main__":
    main()
