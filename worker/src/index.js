// ai-daily-subscribe — self-hosted subscription collector for AI Daily Digest.
// Stores emails in KV (shared TOOL_STATS namespace, keys prefixed "aidaily:sub:").
// Endpoints:
//   POST /subscribe    {email, source?}  -> validate, dedupe, store {email, ts, source}
//   POST /unsubscribe  {email}          -> remove the record
// CORS: only https://ai-daily-news.sweetai.work is allowed.

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
