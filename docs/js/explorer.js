// The appendix: the 600-answer table with its setup picker, and the SQL console.
// Moved from the original single-file page; every number is counted from the data.

import { runQuery } from "./sqlengine.js";

const el = (t, cls, txt) => { const e = document.createElement(t); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const outcome = (r) => (r.ok ? "correct" : r.silent ? "silent" : "loud");

const VMETA = {
  V1: { m: "8B", p: "no examples" }, V2: { m: "8B", p: "solved examples" },
  V3: { m: "70B", p: "no examples" }, V4: { m: "70B", p: "solved examples" },
};

export function initExplorer(runs) {
  if (!runs) {
    document.getElementById("xcount").textContent = "";
    document.getElementById("xbody").innerHTML = '<tr><td colspan="7"><div class="nodata">Couldn\'t load the data.</div></td></tr>';
    return;
  }
  const F = { v: new Set(), t: new Set(), o: new Set() };
  let sortK = null, sortDir = 1;

  const stats = (v) => {
    const rows = runs.filter((r) => r.v === v), ok = rows.filter((r) => r.ok).length;
    const wrong = rows.length - ok, silent = rows.filter((r) => r.silent).length;
    return { n: rows.length, ok, wrong, silent, acc: rows.length ? ok / rows.length : 0, hidden: wrong ? silent / wrong : 0 };
  };

  function vcard(v) {
    const card = document.getElementById("vcard"), say = document.getElementById("vsay");
    card.innerHTML = ""; say.innerHTML = "";
    if (!v) {
      const best = stats("V3"), worst = stats("V1");
      say.textContent = `Showing all ${runs.length} answers. Pick a setup to see it on its own. The most accurate setup (V3, ${Math.round(best.acc * 100)}% correct) had ${best.silent} of its ${best.wrong} mistakes run without any error. The least accurate (V1, ${Math.round(worst.acc * 100)}% correct) had ${worst.silent} of ${worst.wrong}.`;
      return;
    }
    const s = stats(v), meta = VMETA[v];
    [["Model", meta.m, ""], ["Prompt", meta.p, ""], ["Accuracy", Math.round(s.acc * 100) + "%", s.ok + " of " + s.n],
     ["Wrong", String(s.wrong), "answers"], ["Wrong with no error", Math.round(s.hidden * 100) + "%", s.silent + " of " + s.wrong]]
      .forEach(([k, val, small], i) => {
        const d = el("div", i === 4 ? "hot" : null);
        d.appendChild(el("span", "k", k));
        const vv = el("span", "v", val); if (small) vv.appendChild(el("small", null, small));
        d.appendChild(vv); card.appendChild(d);
      });
    say.innerHTML = `<b>${v}</b> is the ${meta.m} model with ${meta.p}. It answered ${Math.round(s.acc * 100)}% correctly. Of the ${s.wrong} it got wrong, <b>${s.silent} gave no error at all</b>. The table is filtered to this setup.`;
  }

  // One source of truth: the dropdown and the chips both write F.v, then both redraw.
  function syncVariant() {
    const sel = document.getElementById("vpick");
    const only = F.v.size === 1 ? [...F.v][0] : "";
    if (sel.value !== only) sel.value = only;
    document.querySelectorAll("#filters .tog[data-v]").forEach((b) => b.setAttribute("aria-pressed", F.v.has(b.dataset.v) ? "true" : "false"));
    vcard(only);
  }

  function filters() {
    const host = document.getElementById("filters");
    host.innerHTML = "";
    const group = (label, key, vals, labels) => {
      const g = el("div", "fg");
      g.appendChild(el("span", "lab", label));
      vals.forEach((val, i) => {
        const b = el("button", "tog", labels ? labels[i] : val);
        b.type = "button"; b.setAttribute("aria-pressed", "false");
        if (key === "v") b.dataset.v = val;
        b.onclick = () => {
          const on = b.getAttribute("aria-pressed") === "true";
          b.setAttribute("aria-pressed", on ? "false" : "true");
          if (on) F[key].delete(val); else F[key].add(val);
          if (key === "v") syncVariant();
          draw();
        };
        g.appendChild(b);
      });
      host.appendChild(g);
    };
    group("Setup", "v", ["V1", "V2", "V3", "V4"], ["V1 8B", "V2 8B + examples", "V3 70B", "V4 70B + examples"]);
    group("Difficulty", "t", ["simple", "moderate", "complex"]);
    group("Outcome", "o", ["correct", "silent", "loud"], ["correct", "wrong, no error", "wrong, error"]);
    const clear = el("button", "tog", "reset"); clear.type = "button"; clear.style.marginLeft = "auto";
    clear.onclick = () => { F.v.clear(); F.t.clear(); F.o.clear(); host.querySelectorAll(".tog").forEach((b) => b.setAttribute("aria-pressed", "false")); syncVariant(); draw(); };
    host.appendChild(clear);
    document.getElementById("vpick").onchange = (e) => { F.v.clear(); if (e.target.value) F.v.add(e.target.value); syncVariant(); draw(); };
    syncVariant();
  }

  function draw() {
    let rows = runs.filter((r) => (!F.v.size || F.v.has(r.v)) && (!F.t.size || F.t.has(r.t)) && (!F.o.size || F.o.has(outcome(r))));
    if (sortK) rows = rows.slice().sort((a, b) => {
      let x = sortK === "outcome" ? outcome(a) : a[sortK], y = sortK === "outcome" ? outcome(b) : b[sortK];
      if (x == null) x = -Infinity; if (y == null) y = -Infinity;
      return (x < y ? -1 : x > y ? 1 : 0) * sortDir;
    });
    document.getElementById("xcount").textContent = rows.length + " of " + runs.length + " answers";
    const body = document.getElementById("xbody");
    body.innerHTML = "";
    if (!rows.length) { body.innerHTML = '<tr><td colspan="7"><div class="empty">No answers match those filters.</div></td></tr>'; return; }
    rows.slice(0, 400).forEach((r) => {
      const tr = el("tr");
      [r.v, r.t, r.db, r.q].forEach((v) => tr.appendChild(el("td", null, v)));
      const o = outcome(r), td = el("td");
      td.appendChild(el("span", "tag " + (o === "correct" ? "ok" : o === "silent" ? "si" : "lo"), o === "correct" ? "correct" : o === "silent" ? "wrong, no error" : "wrong, error"));
      tr.appendChild(td);
      tr.appendChild(el("td", "num", r.conf == null ? "n/a" : Math.round(r.conf * 100) + "%"));
      tr.appendChild(el("td", "num", r.prows == null ? "n/a" : String(r.prows)));
      tr.onclick = () => detail(tr, r);
      tr.onmouseenter = () => peek(r);
      body.appendChild(tr);
    });
    if (rows.length > 400) body.insertAdjacentHTML("beforeend", '<tr><td colspan="7"><div class="empty">Showing the first 400. Filter to narrow.</div></td></tr>');
  }

  function peek(r) {
    const host = document.getElementById("peek"), o = outcome(r);
    host.innerHTML = "";
    host.appendChild(el("span", "pk", o === "correct" ? "correct:" : o === "silent" ? "wrong, no error:" : "wrong, error:"));
    const c = el("code"); c.textContent = r.sql || "(no parseable SQL)"; host.appendChild(c);
  }

  function detail(tr, r) {
    const nxt = tr.nextSibling;
    if (nxt && nxt.classList && nxt.classList.contains("detail")) { nxt.remove(); return; }
    const d = el("tr", "detail"), td = el("td"); td.colSpan = 7;
    const g = el("div", "dgrid");
    const a = el("div"); a.appendChild(el("div", "lb", "Human answer, " + r.grows + " rows"));
    const ac = el("code"); ac.textContent = r.gold; a.appendChild(ac);
    const b = el("div"); b.appendChild(el("div", "lb", "AI answer, " + (r.prows == null ? "did not run" : r.prows + " rows") + (r.err ? ", " + r.err : "")));
    const bc = el("code"); bc.textContent = r.sql || "(no parseable SQL)"; b.appendChild(bc);
    g.append(a, b); td.appendChild(g); d.appendChild(td);
    tr.parentNode.insertBefore(d, tr.nextSibling);
  }

  document.querySelectorAll("#xtable th.s").forEach((th) => {
    th.tabIndex = 0;
    const go = () => { const k = th.dataset.k; if (sortK === k) sortDir = -sortDir; else { sortK = k; sortDir = 1; } draw(); };
    th.onclick = go;
    th.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } };
  });
  filters(); draw();
}

const EXAMPLES = [
  ["Wrong with no error, stated 100% sure", "SELECT v, t, db, conf, q FROM runs WHERE silent = true AND conf = 1 LIMIT 25"],
  ["Accuracy by setup", "SELECT v, COUNT(*), AVG(ok) FROM runs GROUP BY v"],
  ["Share wrong with no error, by difficulty", "SELECT t, COUNT(*), AVG(silent) FROM runs GROUP BY t"],
  ["Which mistakes failed with an error", "SELECT v, t, err, db FROM runs WHERE ran = false LIMIT 25"],
  ["Flagged by the check", "SELECT v, ok, db, q FROM runs WHERE flagged = true LIMIT 25"],
  ["Where the 70B model still failed", "SELECT t, db, q, err FROM runs WHERE m = '70B' AND ok = false LIMIT 25"],
];

export function initConsole(runs) {
  const box = document.getElementById("sqlbox"), out = document.getElementById("cout"), errHost = document.getElementById("cerr");
  function show(res) {
    out.innerHTML = "";
    out.appendChild(el("div", "okline", res.total + (res.total === 1 ? " row" : " rows") + (res.rows.length < res.total ? ", showing " + res.rows.length : "")));
    if (!res.rows.length) return;
    const wrap = el("div", "scroll"); wrap.style.marginTop = ".6rem";
    const tb = el("table"), th = el("thead"), htr = el("tr");
    res.cols.forEach((c) => htr.appendChild(el("th", null, c)));
    th.appendChild(htr); tb.appendChild(th);
    const bd = el("tbody");
    res.rows.forEach((r) => {
      const tr = el("tr");
      r.forEach((v) => tr.appendChild(el("td", typeof v === "number" ? "num" : null, v == null ? "n/a" : typeof v === "boolean" ? String(v) : String(v))));
      bd.appendChild(tr);
    });
    tb.appendChild(bd); wrap.appendChild(tb); out.appendChild(wrap);
  }
  function execute() {
    errHost.innerHTML = ""; out.innerHTML = "";
    if (!runs) { errHost.appendChild(el("div", "err", "Couldn't load the data, so there is nothing to query.")); return; }
    const text = box.value.trim().replace(/;+\s*$/, "");
    if (!text) return;
    try { show(runQuery(text, runs)); } catch (e) { errHost.appendChild(el("div", "err", e.message)); }
  }
  const ex = document.getElementById("examples");
  EXAMPLES.forEach(([label, sql]) => {
    const b = el("button", null, label); b.type = "button";
    b.onclick = () => { box.value = sql; execute(); };
    ex.appendChild(b);
  });
  document.getElementById("runbtn").onclick = execute;
  box.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); execute(); } });
  execute();
}
