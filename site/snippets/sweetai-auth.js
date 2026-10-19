/* SweetAI shared auth — Google one-click login for all sites.
 * Requires: <div id="auth-area"></div> in header, GSI script loaded.
 * API: https://game-hub-api.dylan-xm.workers.dev
 * Token stored in localStorage('sweetai_token').
 */
(function () {
  var API = "https://game-hub-api.dylan-xm.workers.dev";
  var TOKEN_KEY = "sweetai_token";

  window.SweetAI = window.SweetAI || {};
  var S = window.SweetAI;

  S.token = function () { return localStorage.getItem(TOKEN_KEY); };
  S.user = null;

  S.api = function (path, opts) {
    opts = opts || {};
    var headers = { "Content-Type": "application/json" };
    var t = S.token();
    if (t) headers["Authorization"] = "Bearer " + t;
    return fetch(API + path, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then(function (r) {
      if (r.status === 401) { S.logout(true); }
      return r.json().catch(function () { return {}; });
    });
  };

  S.requireLogin = function () {
    if (!S.token() || !S.user) {
      S.toast("Please sign in with Google to continue");
      var a = document.getElementById("auth-area");
      if (a) a.scrollIntoView({ behavior: "smooth", block: "center" });
      return false;
    }
    return true;
  };

  S.toast = function (msg) {
    var t = document.getElementById("sweetai-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "sweetai-toast";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.classList.remove("show"); }, 3200);
  };

  S.logout = function (silent) {
    localStorage.removeItem(TOKEN_KEY);
    S.user = null;
    if (!silent) renderAuth();
  };

  function renderAuth() {
    var area = document.getElementById("auth-area");
    if (!area) return;
    if (S.user) {
      area.innerHTML =
        '<span class="sweetai-user">' +
        (S.user.avatar ? '<img src="' + S.user.avatar.replace(/"/g, "") + '" alt="" class="sweetai-avatar">' : "") +
        '<span class="sweetai-name">' + escapeHtml(S.user.name || S.user.email) + "</span>" +
        '<button type="button" id="sweetai-logout" class="sweetai-link">Sign out</button></span>';
      var out = document.getElementById("sweetai-logout");
      if (out) out.addEventListener("click", function () { S.logout(); });
    } else {
      area.innerHTML = '<div id="sweetai-gsi-btn"></div>';
      initGsiButton();
    }
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var gsiTries = 0;
  var gsiCfg = null;
  function gsiTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "filled_black" : "outline";
  }
  function renderGsiButton() {
    var el = document.getElementById("sweetai-gsi-btn");
    if (!el || !window.google || !google.accounts || !google.accounts.id || !gsiCfg || !gsiCfg.google_client_id) return false;
    google.accounts.id.initialize({
      client_id: gsiCfg.google_client_id,
      callback: onCredential,
    });
    el.innerHTML = "";
    google.accounts.id.renderButton(el, { theme: gsiTheme(), size: "medium", shape: "pill", locale: "en" });
    return true;
  }
  function initGsiButton() {
    S.api("/api/auth/config").then(function (c) { gsiCfg = c; tryRender(); });
    function tryRender() {
      if (renderGsiButton()) return;
      if (++gsiTries < 40) {
        setTimeout(tryRender, 250);
      }
    }
    // Re-render the button when the site theme toggles (light/dark).
    if (window.MutationObserver) {
      new MutationObserver(function () { renderGsiButton(); })
        .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    }
  }

  function onCredential(resp) {
    S.api("/api/auth/google", { method: "POST", body: { id_token: resp.credential } })
      .then(function (d) {
        if (d && d.ok) {
          localStorage.setItem(TOKEN_KEY, d.token);
          S.user = d.user;
          renderAuth();
          document.dispatchEvent(new CustomEvent("sweetai:login"));
        } else {
          S.toast("Sign-in failed. Please try again.");
        }
      })
      .catch(function () { S.toast("Sign-in failed. Please try again."); });
  }

  // Validate existing token on load
  document.addEventListener("DOMContentLoaded", function () {
    var t = S.token();
    if (t) {
      S.api("/api/auth/me").then(function (d) {
        S.user = d && d.user ? d.user : null;
        if (!S.user) localStorage.removeItem(TOKEN_KEY);
        renderAuth();
      });
    } else {
      renderAuth();
    }
  });
})();
