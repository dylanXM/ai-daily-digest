/* Dark mode toggle: follows system by default, manual choice saved to localStorage */
(function(){
  var KEY = "ai-daily-theme";
  var root = document.documentElement;
  function systemTheme(){
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function current(){
    try { return localStorage.getItem(KEY) || systemTheme(); }
    catch(e){ return systemTheme(); }
  }
  function apply(t){ root.setAttribute("data-theme", t); }
  apply(current());
  try {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function(e){
      if (!localStorage.getItem(KEY)) apply(e.matches ? "dark" : "light");
    });
  } catch(e){}
  document.addEventListener("DOMContentLoaded", function(){
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function(){
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(next);
      try { localStorage.setItem(KEY, next); } catch(e){}
    });
  });
})();
/* Sweet Hub stats beacon — include on every page.
 * Requires: <meta name="hub-site" content="tools-hub|localcraft|wallpapers|game-hub">
 * 1 write per pageview in D1 (PV), plus an anonymous visitor id persisted
 * in localStorage ("hub_vid") so the console can also report daily UV.
 * The vid is a random id, not tied to any identity. Reports without a
 * vid (old cached copies) still count toward PV only. Operator visits
 * (Muse's own sessions) are marked with a "muse-" vid prefix via the
 * muse_op cookie — set by the admin console at login, or self-planted
 * by any visit carrying ?muse_op=1 (see below).
 */
(function () {
  try {
    var m = document.querySelector('meta[name="hub-site"]');
    if (!m || !m.content) return;
    var url = "https://sweet-hub-api.dylan-xm.workers.dev/api/collect";
    var vid = null;
    try {
      // Self-planting (2026-11-02): any browser that opens a page with
      // ?muse_op=1 plants the muse_op cookie on this domain itself
      // (same spec the console uses: Path=/, Max-Age 1y, SameSite=Lax,
      // Secure on https), so every later visit from that browser is
      // marked automatically — no console login needed. The cookie is
      // planted on the registrable domain (e.g. sweetai.work) so one
      // marked visit covers all subdomains; where that domain is a
      // public suffix (e.g. pages.dev) the browser rejects the Domain
      // cookie and we fall back to a host-only cookie, which still
      // marks this exact site.
      try {
        if (new URLSearchParams(location.search || "").get("muse_op") === "1") {
          var spec = "; Path=/; Max-Age=31536000; SameSite=Lax" +
            (location.protocol === "https:" ? "; Secure" : "");
          var labels = (location.hostname || "").split(".");
          var base = labels.length >= 2 ? labels.slice(-2).join(".") : location.hostname;
          document.cookie = "muse_op=1; Domain=." + base + spec;
          if (!/(?:^|;\s*)muse_op=1(?:;|$)/.test(document.cookie || "")) {
            document.cookie = "muse_op=1" + spec;
          }
        }
      } catch (e) {}
      // Operator marking (2026-11-02): the admin console sets a
      // muse_op=1 cookie on .sweetai.work when the operator logs in.
      // Visits from a browser carrying that cookie are Muse's own
      // logged-in / test sessions, so their vid is stored in the
      // "muse-<uuid>" form and the console can exclude them from the
      // stats with one switch. Ordinary visitors keep bare UUIDs.
      var isOp = /(?:^|;\s*)muse_op=1(?:;|$)/.test(document.cookie || "");
      vid = localStorage.getItem("hub_vid");
      if (isOp && vid && vid.indexOf("muse-") !== 0) {
        vid = "muse-" + vid;
        localStorage.setItem("hub_vid", vid);
      }
      if (!vid) {
        vid = (window.crypto && crypto.randomUUID) ? crypto.randomUUID()
          : "v" + Date.now().toString(36) + Math.random().toString(36).slice(2, 14);
        if (isOp) vid = "muse-" + vid;
        localStorage.setItem("hub_vid", vid);
      }
    } catch (e) { vid = null; }
    // Acquisition attribution (2026-11-02): carry the landing page's
    // utm_* params + referrer with the pageview so traffic can be split
    // by source/campaign. Also stashed in sessionStorage so a later
    // in-session action (e.g. a checkout click) can attribute itself to
    // the same campaign — that moment is the only chance to capture it.
    var utm = { utm_source: "", utm_medium: "", utm_campaign: "", referrer: "" };
    try {
      var q = new URLSearchParams(location.search || "");
      utm.utm_source = (q.get("utm_source") || "").slice(0, 128);
      utm.utm_medium = (q.get("utm_medium") || "").slice(0, 128);
      utm.utm_campaign = (q.get("utm_campaign") || "").slice(0, 128);
      utm.referrer = (document.referrer || "").slice(0, 512);
      if (utm.utm_source || utm.utm_medium || utm.utm_campaign) {
        try { sessionStorage.setItem("hub_utm", JSON.stringify(utm)); } catch (e) {}
      }
    } catch (e) {}
    var payload = JSON.stringify({ site: m.content, event: "pv", vid: vid,
      utm_source: utm.utm_source, utm_medium: utm.utm_medium,
      utm_campaign: utm.utm_campaign, referrer: utm.referrer });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url, payload);
    } else {
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true,
      }).catch(function () {});
    }
  } catch (e) { /* never break the page */ }
})();
/* Sweet Hub tip jar — PayPal "Buy me a coffee".
 * Requires: <div class="tip-jar" id="tip-jar">…</div> on the page (see tip.html).
 * The jar stays hidden until the PayPal Client ID is configured server-side.
 */
(function () {
  var jar = document.getElementById("tip-jar");
  if (!jar) return;
  var API = "https://sweet-hub-api.dylan-xm.workers.dev";
  var selected = "1.99";

  function amount() {
    var v;
    if (selected === "custom") {
      v = parseFloat(document.getElementById("tip-amount").value);
    } else {
      v = parseFloat(selected);
    }
    if (!isFinite(v) || v < 0.5) v = 0.5;
    if (v > 500) v = 500;
    return v.toFixed(2);
  }

  function initPills() {
    var pills = jar.querySelectorAll(".tip-pill");
    var customRow = document.getElementById("tip-custom");
    pills.forEach(function (p) {
      p.addEventListener("click", function () {
        pills.forEach(function (x) { x.classList.remove("on"); });
        p.classList.add("on");
        selected = p.getAttribute("data-amount");
        customRow.style.display = selected === "custom" ? "flex" : "none";
      });
    });
  }

  fetch(API + "/api/paypal/config")
    .then(function (r) { return r.json(); })
    .then(function (cfg) {
      if (!cfg || !cfg.clientId) return; // PayPal not configured yet
      jar.style.display = "block";
      initPills();
      var s = document.createElement("script");
      s.src =
        "https://www.paypal.com/sdk/js?client-id=" +
        encodeURIComponent(cfg.clientId) +
        "&currency=USD&intent=capture";
      s.onload = initButtons;
      document.head.appendChild(s);
    })
    .catch(function () {});

  function initButtons() {
    if (!window.paypal) return;
    paypal
      .Buttons({
        style: { layout: "vertical", color: "black", shape: "pill", label: "paypal", tagline: false, height: 40 },
        createOrder: function (data, actions) {
          return actions.order.create({
            purchase_units: [
              {
                description: "Tip — Buy me a coffee",
                amount: { currency_code: "USD", value: amount() },
              },
            ],
          });
        },
        onApprove: function (data, actions) {
          return actions.order.capture().then(function (details) {
            var cap = details.purchase_units[0].payments.captures[0];
            return fetch(API + "/api/tip/record", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                orderID: data.orderID,
                captureID: cap.id,
                amount: cap.amount.value,
                page_url: location.href,
              }),
            }).then(function () {
              document.getElementById("tip-thanks").style.display = "block";
              document.getElementById("tip-paypal-btn").style.display = "none";
              document.getElementById("tip-amounts").style.display = "none";
              document.getElementById("tip-custom").style.display = "none";
            });
          });
        },
        onError: function (err) { console.error("tip error", err); },
      })
      .render("#tip-paypal-btn");
  }
})();