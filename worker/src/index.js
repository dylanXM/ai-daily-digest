// ai-daily-subscribe — self-hosted subscription service for AI Daily Digest.
// Stores emails in KV (shared TOOL_STATS namespace, keys prefixed "aidaily:sub:").
// Endpoints:
//   POST /subscribe    {email, source?}  -> validate, dedupe, store {email, ts, source}
//   POST /unsubscribe  {email}           -> remove the record
//   GET  /u?e=<email>&t=<token>          -> signed unsubscribe link from digest emails;
//                                           token = HMAC-SHA256(env.AIDAILY_KEY, email) hex[:32]
//   GET  /export                         -> Authorization: Bearer <AIDAILY_KEY>;
//                                           returns the subscriber email list (digest sender only)
// CORS: browser posts only from https://ai-daily-news.sweetai.work.

const ALLOWED_ORIGIN = "https://ai-daily-news.sweetai.work";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const PREFIX = "aidaily:sub:";

function corsHeaders(request) {
  const origin = request.headers.get("Origin") || "";
  return origin === ALLOWED_ORIGIN
    ? {
        "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        Vary: "Origin",
      }
    : { Vary: "Origin" };
}

function json(request, obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(request) },
  });
}

async function readBody(request) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

function validEmail(raw) {
  const email = String(raw || "").trim().toLowerCase();
  return EMAIL_RE.test(email) && email.length <= 254 ? email : null;
}

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function unsubToken(key, email) {
  const enc = new TextEncoder();
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    enc.encode(key),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", cryptoKey, enc.encode(email));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 32);
}

function htmlPage(title, body) {
  return new Response(
    `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${title}</title></head>` +
      `<body style="font-family:system-ui,sans-serif;max-width:560px;margin:48px auto;padding:0 16px">` +
      `<h1>${title}</h1><p>${body}</p>` +
      `<p><a href="https://ai-daily-news.sweetai.work/">AI Daily Digest</a></p></body></html>`,
    { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      const origin = request.headers.get("Origin") || "";
      if (origin && origin !== ALLOWED_ORIGIN) return new Response(null, { status: 403 });
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }

    if (url.pathname === "/" && request.method === "GET") {
      return json(request, { ok: true, service: "ai-daily-subscribe" });
    }

    // Signed unsubscribe link (from digest emails).
    if (url.pathname === "/u" && request.method === "GET") {
      const email = validEmail(url.searchParams.get("e"));
      const token = url.searchParams.get("t") || "";
      if (!email || !env.AIDAILY_KEY) return htmlPage("Invalid link", "This unsubscribe link is invalid.");
      const expected = await unsubToken(env.AIDAILY_KEY, email);
      if (!timingSafeEqual(token, expected)) {
        return new Response("Invalid token", { status: 400 });
      }
      await env.SUBS.delete(PREFIX + email);
      return htmlPage(
        "Unsubscribed",
        `${email} has been removed from the AI Daily Digest list. Sorry to see you go — you can re-subscribe on any issue page at any time.`
      );
    }

    // Key-gated subscriber export for the digest sender.
    if (url.pathname === "/export" && request.method === "GET") {
      const auth = request.headers.get("Authorization") || "";
      const presented = auth.startsWith("Bearer ") ? auth.slice(7) : "";
      if (!env.AIDAILY_KEY || !timingSafeEqual(presented, env.AIDAILY_KEY)) {
        return json(request, { ok: false, error: "unauthorized" }, 401);
      }
      const emails = [];
      let cursor;
      do {
        const page = await env.SUBS.list({ prefix: PREFIX, cursor, limit: 1000 });
        for (const k of page.keys) emails.push(k.name.slice(PREFIX.length));
        cursor = page.list_complete ? undefined : page.cursor;
      } while (cursor);
      emails.sort();
      return json(request, { ok: true, count: emails.length, subscribers: emails });
    }

    if (request.method !== "POST" || !["/subscribe", "/unsubscribe"].includes(url.pathname)) {
      return json(request, { ok: false, error: "not found" }, 404);
    }

    // Cross-origin browser posts are only accepted from the site itself.
    const origin = request.headers.get("Origin") || "";
    if (origin && origin !== ALLOWED_ORIGIN) {
      return json(request, { ok: false, error: "forbidden origin" }, 403);
    }

    const body = await readBody(request);
    const email = validEmail(body?.email);
    if (!email) return json(request, { ok: false, error: "invalid email" }, 400);

    const key = PREFIX + email;

    if (url.pathname === "/unsubscribe") {
      await env.SUBS.delete(key);
      return json(request, { ok: true, unsubscribed: true });
    }

    const existing = await env.SUBS.get(key);
    if (existing) return json(request, { ok: true, already: true });

    const source =
      typeof body?.source === "string" && body.source ? body.source.slice(0, 64) : "web";
    await env.SUBS.put(key, JSON.stringify({ email, ts: new Date().toISOString(), source }));
    return json(request, { ok: true, subscribed: true });
  },
};
