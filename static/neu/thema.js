"use strict";
/* Neues Design: Plotly-Diagramme an die Farben anpassen (Schrift, transparenter Hintergrund).
   Die Daten und Farbskalen der Diagramme bleiben unverändert. */

(function () {
  const SCHRIFT = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif';
  const DUNKELGRUEN = "#1D3630";
  const original = Plotly.react;

  Plotly.react = function (gd, data, layout, config) {
    const l = Object.assign({}, layout || {});
    l.font = Object.assign({ family: SCHRIFT, color: DUNKELGRUEN, size: 12 }, l.font || {});
    if (!("paper_bgcolor" in l)) l.paper_bgcolor = "rgba(0,0,0,0)";
    if (!("plot_bgcolor" in l)) l.plot_bgcolor = "rgba(0,0,0,0)";
    for (const achse of ["xaxis", "yaxis"]) {
      if (l[achse]) l[achse] = Object.assign({ gridcolor: "#E1DFDA", zerolinecolor: "#BECAC4", linecolor: "#BECAC4" }, l[achse]);
    }
    return original.call(this, gd, data, l, config);
  };

  /* Navigationsleiste: nach dem Hero etwas kräftiger */
  window.addEventListener("scroll", () => {
    document.body.classList.toggle("gescrollt", window.scrollY > 40);
  }, { passive: true });
})();
