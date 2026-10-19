/* Floating tip button toggle — load after tip.js.
 * Opens/closes the tip popover; tip.js handles PayPal inside #tip-jar.
 * Black/white minimal style to match the tip card. */
(function () {
  function init() {
    var fab = document.getElementById("tip-fab");
    var pop = document.getElementById("tip-popover");
    if (!fab || !pop) return;
    var closeBtn = document.getElementById("tip-popover-close");

    // Hide the FAB entirely if PayPal isn't configured (tip.js leaves #tip-jar hidden)
    var jar = document.getElementById("tip-jar");
    var checkTimer = setInterval(function () {
      if (jar && jar.style.display === "block") {
        fab.style.display = "flex";
        clearInterval(checkTimer);
      }
    }, 500);
    // Give up after 10s — keep hidden
    setTimeout(function () { clearInterval(checkTimer); }, 10000);
    fab.style.display = "none";

    function open() { pop.hidden = false; }
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
