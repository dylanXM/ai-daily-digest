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
