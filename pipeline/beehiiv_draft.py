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


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv[1:]

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
