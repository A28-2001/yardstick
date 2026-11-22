// Chapter 1 (one mistake, the query card) and Chapter 2 (the 600-dot field).

import { observeSteps } from "./scroll.js";
import { exampleRuns, EXAMPLE_QID } from "./facts.js";

const SVGNS = "http://www.w3.org/2000/svg";

/* ---------------------------------------------------------------- chapter 1 */
export function initOne(scrolly, runs) {
  // The query text comes from the data when it loaded; the HTML already holds the same
  // text, so the chapter reads correctly without it.
  if (runs) {
    const ex = Object.fromEntries(exampleRuns(runs).map((r) => [r.v, r]));
    if (ex.V2) document.getElementById("ex-sql").textContent = ex.V2.sql;
    if (ex.V2) document.getElementById("ex-gold").textContent = ex.V2.gold;
  }
  const rows = [...scrolly.querySelectorAll("[data-show]")];
  observeSteps(scrolly, (n) => {
    rows.forEach((r) => {
      r.classList.toggle("vis", Number(r.dataset.show) <= n);
      r.classList.toggle("cur", Number(r.dataset.show) === n);
    });
  });
}

/* ---------------------------------------------------------------- chapter 2 */
const COLS = 30, GAP = 12, R = 4.3, PAD = 8, LABEL = 24;

const LEGENDS = {
  1: [["lw", "wrong (this question)"], ["", "right"]],
  2: [["lw", "wrong"], ["", "right"]],
  3: [["lw", "wrong, ran with no error"], ["lh", "wrong, failed with an error"], ["", "right"]],
  4: [["lw", "wrong"], ["", "right"], ["", "faded: stated confidence under 90%"]],
  5: [["lw", "wrong"], ["", "right"]],
  6: [["lg", "mistake caught"], ["lw", "missed, no error"], ["lh", "missed, failed with an error"], ["", "right"]],
};

export function initDots(scrolly, runs) {
  const host = scrolly.querySelector("#dotfield");
  const legend = host.querySelector("#dotlegend");
  if (!runs) {
    host.querySelector("#dots-nodata").hidden = false;
    legend.hidden = true;
    observeSteps(scrolly, () => {});
    return;
  }
  // Base order keeps the four answers to a question side by side.
  const data = runs.slice().sort((a, b) => (a.qid < b.qid ? -1 : a.qid > b.qid ? 1 : a.v < b.v ? -1 : 1));
  const rowsNeeded = Math.ceil(data.length / COLS) + 7; // room for two blocks, a gap and labels
  const W = COLS * GAP + PAD * 2, H = rowsNeeded * GAP + PAD * 2 + LABEL * 2;
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "600 dots, one per answer. The text beside it describes each step.");
  const labels = [0, 1].map(() => {
    const t = document.createElementNS(SVGNS, "text");
    t.setAttribute("class", "gl"); svg.appendChild(t); return t;
  });
  const dots = data.map((r) => {
    const c = document.createElementNS(SVGNS, "circle");
    c.setAttribute("r", R);
    if (r.qid === EXAMPLE_QID) c.classList.add("ex");
    svg.appendChild(c);
    return { r, c };
  });
  host.insertBefore(svg, legend);

  const place = (groups) => {
    let row = 0;
    groups.forEach((g, gi) => {
      const label = labels[gi];
      if (g.label) {
        label.textContent = g.label;
        label.setAttribute("x", PAD);
        label.setAttribute("y", PAD + row * GAP + 13);
        row += LABEL / GAP;
      }
      g.items.forEach((d, i) => {
        const x = PAD + GAP / 2 + (i % COLS) * GAP;
        const y = PAD + GAP / 2 + (row + Math.floor(i / COLS)) * GAP;
        d.c.style.transform = `translate(${x}px, ${y}px)`;
      });
      row += Math.ceil(g.items.length / COLS) + 1;
    });
    labels.forEach((l, i) => { if (!groups[i] || !groups[i].label) l.textContent = ""; });
  };

  const wrongFirst = (a, b) => Number(a.r.ok) - Number(b.r.ok);
  const show = (n) => {
    dots.forEach(({ r, c }) => {
      const wrong = !r.ok;
      c.classList.toggle("w", n === 1 ? wrong && r.qid === EXAMPLE_QID : wrong && !(n >= 6 && r.flagged));
      c.classList.toggle("g", n >= 6 && wrong && r.flagged);
      c.classList.toggle("hollow", n >= 3 && wrong && !r.ran);
      c.classList.toggle("dim", n === 4 && !(r.conf !== null && r.conf >= 0.9));
    });
    if (n <= 1) place([{ items: dots }]);
    else if (n <= 4) place([{ items: dots.slice().sort(wrongFirst) }]);
    else {
      const f = dots.filter((d) => d.r.flagged).sort(wrongFirst);
      const u = dots.filter((d) => !d.r.flagged).sort(wrongFirst);
      place([{ label: `Flagged by the check: ${f.length} answers`, items: f },
             { label: `Not flagged: ${u.length} answers`, items: u }]);
    }
    legend.innerHTML = "";
    (LEGENDS[n] || LEGENDS[1]).forEach(([cls, txt]) => {
      const s = document.createElement("span");
      if (cls) s.className = cls;
      s.textContent = txt;
      legend.appendChild(s);
    });
  };
  observeSteps(scrolly, show);
}
