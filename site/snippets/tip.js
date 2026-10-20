/* Sweet Hub tip jar — PayPal "Buy me a coffee".
 * Requires: <div class="tip-jar" id="tip-jar">…</div> on the page (see tip.html).
 * The jar stays hidden until the PayPal Client ID is configured server-side.
 * PayPal buttons render lazily when the popover first opens (SDK can't
 * initialize buttons inside a hidden container).
 */
(function () {
  function init() {
  var jar = document.getElementById("tip-jar");
  if (!jar) return;
  var API = "https://sweet-hub-api.dylan-xm.workers.dev";
  var selected = "1.99";
  var buttonsRendered = false;
  var sdkReady = false;

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
      s.onload = function () { sdkReady = true; tryRender(); };
      s.onerror = function () { console.error("tip: paypal sdk failed to load"); };
      document.head.appendChild(s);
      // If popover is already open (inline layout), render now
      tryRender();
    })
    .catch(function () {});

  function tryRender() {
    if (buttonsRendered || !sdkReady || !window.paypal) return;
    var pop = document.getElementById("tip-popover");
    // Only render when the popover is visible (SDK fails in hidden containers)
    var visible = !pop || !pop.hidden;
    if (!visible) return;
    buttonsRendered = true;
    initButtons();
  }

  // Exposed for tip-fab.js to call when the popover opens
  window.SweetTip = window.SweetTip || {};
  window.SweetTip.renderButtons = tryRender;

  // Also watch for popover visibility changes
  var popEl = document.getElementById("tip-popover");
  if (popEl && window.MutationObserver) {
    new MutationObserver(function () { tryRender(); })
      .observe(popEl, { attributes: true, attributeFilter: ["hidden"] });
  }

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
        onCancel: function () { /* user closed popup */ },
      })
      .render("#tip-paypal-btn");
  }
}
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
