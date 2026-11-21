"use strict";
// Appearance (studio principle 10): the in-app Light or Dark choice, set on <html> before the first paint
// so a page set to Light never flashes dark. Auto (no attribute) follows the phone. A separate file because
// the CSP allows no inline script. The key sits outside the "charlie:" prefix, so Reset demo keeps it.
(function () {
  try {
    var v = localStorage.getItem("charlie-appearance");
    if (v === "light" || v === "dark") document.documentElement.setAttribute("data-theme", v);
  } catch (_) { /* blocked storage: follow the phone */ }
})();
