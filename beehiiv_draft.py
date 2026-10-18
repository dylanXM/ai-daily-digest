#!/usr/bin/env python3
"""
Beehiiv newsletter draft for AI Daily Digest -- DRAFT, pending user credentials.

Reads the day's content JSON (content/YYYY-MM-DD.json) and either:
  1. creates a DRAFT post in Beehiiv via the Create Post API (default), or
  2. renders a standalone HTML file to paste into Beehiiv's editor (--render-only,
     no API key needed -- works on the free Launch plan no matter what).

Credentials come from environment variables (never hardcode them):
  BEEHIIV_PUB_ID   e.g. pub_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
                   (Beehiiv dashboard -> Settings -> Publication ID)
  BEEHIIV_API_KEY  (Beehiiv dashboard -> Settings -> Integrations -> API)

Usage:
  BEEHIIV_PUB_ID=... BEEHIIV_API_KEY=... python3 beehiiv_draft.py [--date 2026-10-17]
  python3 beehiiv_draft.py --render-only [--date 2026-10-17] [--out /tmp/newsletter.html]

API reference: POST https://api.beehiiv.com/v2/publications/{pub_id}/posts
  body: {"title": ..., "body_content": "<html>", "status": "draft"}
  auth: Authorization: Bearer <api_key>
  (beehiiv docs: "Using the Send API and Create post endpoint";
   body_content must use inline styles -- <style>/<link> tags are stripped)

Stdlib only, matching the project's build.py convention.
"""

import argparse
import html
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, "content")
API_BASE = "https://api.beehiiv.com/v2"


def load_content(day: str) -> dict:
    path = os.path.join(CONTENT_DIR, f"{day}.json")
    if not os.path.exists(path):
        # fall back to the newest available file
        files = sorted(f for f in os.listdir(CONTENT_DIR) if f.endswith(".json"))
        if not files:
            sys.exit(f"no content JSON found in {CONTENT_DIR}")
        path = os.path.join(CONTENT_DIR, files[-1])
        print(f"[info] {day}.json not found, using {files[-1]}", file=sys.stderr)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def build_html(data: dict) -> tuple[str, str]:
    """Return (title, body_html). Inline styles only (beehiiv strips <style>)."""
    day = data.get("date", str(date.today()))
    title = f"AI Daily Digest \u2014 {day}"

    parts = []
    parts.append(
        '<table width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="font-family:Arial,Helvetica,sans-serif;color:#111111;'
        'font-size:16px;line-height:1.6;max-width:600px;margin:0 auto;display:block;">'
    )
    parts.append(
        f'<h1 style="font-size:24px;margin:0 0 4px;">\U0001f916 AI Daily Digest</h1>'
        f'<p style="color:#666666;font-size:14px;margin:0 0 24px;">{esc(day)}'
        " \u00b7 Top AI news, GitHub trends &amp; new AI products, curated daily.</p>"
    )

    # --- Section 1: news ---
    news = data.get("news") or []
    if news:
        parts.append('<h2 style="font-size:20px;border-bottom:2px solid #111111;'
                     'padding-bottom:6px;">\U0001f4f0 Top AI News</h2>')
        for item in news:
            parts.append(
                f'<h3 style="font-size:17px;margin:18px 0 6px;">'
                f'<a href="{esc(item.get("url"))}" style="color:#1a56db;text-decoration:none;">'
                f'{esc(item.get("title"))}</a></h3>'
                f'<p style="margin:0 0 4px;">{esc(item.get("summary"))}</p>'
                f'<p style="margin:0 0 12px;color:#888888;font-size:13px;">'
                f'Source: {esc(item.get("source"))}</p>'
            )

    # --- Section 2: GitHub trends ---
    repos = data.get("github") or []
    if repos:
        parts.append('<h2 style="font-size:20px;border-bottom:2px solid #111111;'
                     'padding-bottom:6px;margin-top:28px;">\U0001f680 GitHub AI Trends</h2>')
        for r in repos:
            meta = " \u00b7 ".join(
                x for x in [
                    f'\u2b50 {esc(r.get("stars"))}' if r.get("stars") else "",
                    esc(r.get("language")) if r.get("language") else "",
                ] if x
            )
            parts.append(
                f'<h3 style="font-size:17px;margin:18px 0 6px;">'
                f'<a href="{esc(r.get("url"))}" style="color:#1a56db;text-decoration:none;">'
                f'{esc(r.get("name"))}</a>'
                + (f' <span style="color:#888888;font-size:13px;">{meta}</span>' if meta else "")
                + "</h3>"
                f'<p style="margin:0 0 4px;">{esc(r.get("description"))}</p>'
                + (f'<p style="margin:0 0 12px;color:#555555;font-size:14px;">'
                   f'{esc(r.get("note"))}</p>' if r.get("note") else "")
            )

    # --- Section 3: new products ---
    products = data.get("products") or []
    if products:
        parts.append('<h2 style="font-size:20px;border-bottom:2px solid #111111;'
                     'padding-bottom:6px;margin-top:28px;">\U0001f195 New AI Products</h2>')
        for p in products:
            tag = (f' <span style="background:#eef2ff;color:#1a56db;font-size:12px;'
                   f'padding:2px 8px;border-radius:10px;">{esc(p.get("tag"))}</span>'
                   if p.get("tag") else "")
            parts.append(
                f'<h3 style="font-size:17px;margin:18px 0 6px;">'
                f'<a href="{esc(p.get("url"))}" style="color:#1a56db;text-decoration:none;">'
                f'{esc(p.get("name"))}</a>{tag}</h3>'
                f'<p style="margin:0 0 12px;">{esc(p.get("description"))}</p>'
            )

    parts.append(
        '<p style="color:#888888;font-size:13px;margin-top:28px;border-top:1px solid #dddddd;'
        'padding-top:12px;">Thanks for reading AI Daily Digest. '
        "Reply to this email with feedback \u2014 we read every reply.</p>"
        "</td></tr></table>"
    )
    return title, "".join(parts)


def create_draft_api(pub_id: str, api_key: str, title: str, body_html: str) -> dict:
    """POST a draft to Beehiiv. Returns the parsed response JSON."""
    url = f"{API_BASE}/publications/{pub_id}/posts"
    payload = json.dumps({
        "title": title,
        "body_content": body_html,
        "status": "draft",  # never auto-publish; user reviews & sends manually
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {"http_status": resp.status, "data": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        hint = ""
        if e.code == 401:
            hint = "API Key 无效或已过期，请去 Beehiiv 后台 Settings -> Integrations -> API 重新复制。"
        elif e.code == 403:
            hint = ("API 返回 403：当前套餐可能不包含 Send API（发稿 API）权限，"
                    "免费 Launch 版大概率受限。改用 --render-only 模式生成 HTML 手动粘贴，"
                    "效果一样（反正也要人工检查再发送）；等订阅量起来再考虑升级套餐。")
        elif e.code == 422:
            hint = "请求参数校验失败，检查 publication ID 与字段格式。"
        raise RuntimeError(f"Beehiiv API error {e.code}: {body}\n{hint}") from None


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a Beehiiv draft for AI Daily Digest.")
    ap.add_argument("--date", default=str(date.today()),
                    help="content date YYYY-MM-DD (default: today; falls back to newest file)")
    ap.add_argument("--render-only", action="store_true",
                    help="only render HTML to a file for manual paste (no API call)")
    ap.add_argument("--out", default="",
                    help="output path for --render-only (default: /tmp/ai-daily-newsletter-<date>.html)")
    args = ap.parse_args()

    data = load_content(args.date)
    title, body_html = build_html(data)

    if args.render_only:
        out = args.out or f"/tmp/ai-daily-newsletter-{data.get('date', args.date)}.html"
        full = ("<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                f"<title>{esc(title)}</title></head><body>{body_html}</body></html>")
        with open(out, "w", encoding="utf-8") as f:
            f.write(full)
        print(f"HTML written to {out}")
        print("Paste it into Beehiiv: Write -> new post -> use an HTML snippet block, "
              "or paste into the editor, then review & send.")
        return

    pub_id = os.environ.get("BEEHIIV_PUB_ID", "").strip()
    api_key = os.environ.get("BEEHIIV_API_KEY", "").strip()
    if not pub_id or not api_key:
        sys.exit("missing credentials: set BEEHIIV_PUB_ID and BEEHIIV_API_KEY env vars, "
                 "or run with --render-only for the no-API path.")

    result = create_draft_api(pub_id, api_key, title, body_html)
    post = (result.get("data") or {}).get("data", {})
    print(f"Draft created (HTTP {result['http_status']}): {post.get('id', '?')}")
    web_url = post.get("web_url") or post.get("url")
    if web_url:
        print(f"Review it in Beehiiv: {web_url}")
    else:
        print("Open Beehiiv -> Posts -> Drafts to review and send.")


if __name__ == "__main__":
    main()
