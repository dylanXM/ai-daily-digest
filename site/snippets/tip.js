/* Sweet Hub tip jar — PayPal "Buy me a coffee".
 * Requires: <div class="tip-jar" id="tip-jar">…</div> on the page (see tip.html).
 * The jar stays hidden until the PayPal Client ID is configured server-side.
 */
(function () {
  function init() {
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
        "&currency=USD&intent=capture&disable-funding=card";
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
}
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();