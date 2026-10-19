/* Floating tip button toggle — load after tip.js.
 * Opens/closes the tip popover; tip.js handles PayPal inside #tip-jar.
 * The FAB shows immediately; PayPal loads in the background via tip.js. */
(function () {
  function init() {
    var fab = document.getElementById("tip-fab");
    var pop = document.getElementById("tip-popover");
    if (!fab || !pop) return;
    var closeBtn = document.getElementById("tip-popover-close");

    // Show the button right away — don't wait for PayPal config.
    // tip.js reveals the tip card content once PayPal is ready.
    fab.style.display = "flex";

    function open() {
      pop.hidden = false;
      // Render PayPal buttons now that the popover is visible
      if (window.SweetTip && window.SweetTip.renderButtons) {
        // Small delay to ensure layout is done
        setTimeout(function () { window.SweetTip.renderButtons(); }, 50);
      }
    }
    function close() { pop.hidden = true; }
    fab.addEventListener("click", function (e) {
      e.stopPropagation();
      pop.hidden ? open() : close();
    });
    if (closeBtn) closeBtn.addEventListener("click", close);
    document.addEventListener("click", function (e) {
      if (!pop.hidden && !pop.contains(e.target)) close();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
