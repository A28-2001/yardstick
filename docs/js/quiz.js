// Quiz logic. Pure functions here (pool building, shuffling) so tests/quiz.test.mjs can
// check them under Node; the DOM rendering is added in the page phase.

import { EXAMPLE_QID } from "./facts.js";

export const QN = 6;

export function shuffle(a, rng = Math.random) {
  a = a.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Readable examples only, and a deliberate mix: if every round were a failure the
// honest answer would just be "no" every time. Excluded:
//  - wrong_projection: right information with an extra or missing column; scored wrong
//    under strict matching, but a reader would fairly call it right.
//  - the first-screen example, which the reader has already seen answered.
export function eligible(r) {
  return Boolean(r.sql && r.gold && r.ran) &&
    r.sql.length < 190 && r.gold.length < 190 && r.q.length < 120 &&
    r.err !== "wrong_projection" && r.qid !== EXAMPLE_QID;
}

// Three wrong and three right, then shuffled. A fixed alternating order could be
// learned and scored perfectly without reading any SQL.
export function buildPool(runs, rng = Math.random) {
  const pool = runs.filter(eligible);
  const bad = shuffle(pool.filter((r) => r.silent), rng);
  const good = shuffle(pool.filter((r) => r.ok), rng);
  const half = QN >> 1;
  return shuffle(bad.slice(0, half).concat(good.slice(0, QN - half)), rng);
}

/* ------------------------------------------------------------------ the page */
import { STATIC_FACTS, computeFacts } from "./facts.js";

const el = (t, cls, txt) => { const e = document.createElement(t); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };

export function initQuiz(runs) {
  const host = document.getElementById("quiz");
  const prog = document.getElementById("qprog");
  if (!runs) {
    host.innerHTML = '<div class="nodata">Couldn\'t load the data, so the quiz can\'t run.</div>';
    return;
  }
  const facts = computeFacts(runs);
  let pool = buildPool(runs), qi = 0, score = [], answered = false, started = false;

  function start() {
    host.innerHTML = ""; prog.textContent = "not started";
    const w = el("div", "start");
    w.appendChild(el("p", "lead", "Six queries an AI wrote, one at a time, each with the question it was meant to answer. Say whether it returns the right rows."));
    const p2 = el("p"); p2.innerHTML = "<b>You do not see the correct answer until you commit</b>, because a real reviewer does not have it either.";
    w.appendChild(p2);
    const go = el("button", "go", "Start the quiz"); go.type = "button";
    go.onclick = () => { started = true; qi = 0; score = []; round(); };
    w.appendChild(go);
    const m = el("div", "meta"); m.innerHTML = "6 queries &middot; about a minute &middot; keyboard: <kbd>Y</kbd> right, <kbd>N</kbd> wrong, <kbd>Enter</kbd> next";
    w.appendChild(m);
    host.appendChild(w);
  }

  function keyHint(stage) {
    const k = el("div", "keys");
    k.innerHTML = stage === "next" ? "<b>Keyboard</b> <span><kbd>Enter</kbd>next query</span>"
      : "<b>Keyboard</b> <span><kbd>Y</kbd>right rows</span> <span><kbd>N</kbd>wrong rows</span> <span><kbd>Enter</kbd>next</span>";
    return k;
  }

  function strip() {
    const s = el("div", "score"); s.style.marginTop = "1rem";
    const d = el("div", "dots");
    for (let i = 0; i < QN; i++) d.appendChild(el("span", "dot" + (score[i] === true ? " rt" : score[i] === false ? " wr" : "")));
    s.appendChild(d);
    s.appendChild(el("span", null, score.filter((x) => x).length + " of " + score.length + " right so far"));
    return s;
  }

  function round() {
    host.innerHTML = "";
    if (qi >= pool.length) return final();
    prog.textContent = "query " + (qi + 1) + " of " + QN;
    const r = pool[qi]; answered = false;
    const meta = el("div", "qmeta");
    [r.t + " question", "database: " + r.db, r.m + " model", r.p].forEach((t) => meta.appendChild(el("span", "chip", t)));
    host.appendChild(meta);
    const ask = el("div", "ask"); ask.appendChild(el("span", null, "The question")); ask.appendChild(document.createTextNode(r.q));
    host.appendChild(ask);
    const pre = el("pre", "sql"); pre.textContent = r.sql; host.appendChild(pre);
    const ch = el("div", "choices");
    const yes = el("button", null, "Returns the right rows"), no = el("button", null, "Returns the wrong rows");
    yes.type = no.type = "button";
    yes.onclick = () => answer(true); no.onclick = () => answer(false);
    ch.append(yes, no); host.appendChild(ch);
    host.appendChild(keyHint("answer"));
    host.appendChild(strip());
  }

  function answer(saidRight) {
    if (answered) return; answered = true;
    const r = pool[qi], right = saidRight === r.ok;
    score[qi] = right;
    host.querySelectorAll(".choices button").forEach((b) => { b.disabled = true; });
    const rev = el("div", "reveal");
    rev.appendChild(el("p", "verdict " + (right ? "rt" : "wr"), right
      ? (r.ok ? "Correct. That query returns the right rows." : "Correct. That query is wrong.")
      : (r.ok ? "Not quite. That query was actually right." : "Not quite. That query returned the wrong rows, with no error.")));
    const side = el("div", "side");
    const a = el("div"); a.appendChild(el("div", "lb", "What the human wrote"));
    const ac = el("code"); ac.textContent = r.gold; a.appendChild(ac); a.appendChild(el("div", "n", r.grows + " rows"));
    const b = el("div"); b.appendChild(el("div", "lb", "What the AI wrote"));
    const bc = el("code"); bc.textContent = r.sql; b.appendChild(bc);
    b.appendChild(el("div", "n", (r.prows == null ? "n/a" : r.prows) + " rows" + (r.conf != null ? ", stated confidence " + Math.round(r.conf * 100) + "%" : "")));
    side.append(a, b); rev.appendChild(side);
    const nx = el("div", "choices");
    const btn = el("button", null, qi + 1 >= pool.length ? "See the result" : "Next query"); btn.type = "button";
    btn.onclick = () => { qi++; round(); };
    nx.appendChild(btn); rev.appendChild(nx); rev.appendChild(keyHint("next"));
    host.appendChild(rev); host.appendChild(strip());
    btn.focus({ preventScroll: true });
  }

  function final() {
    prog.textContent = "done";
    const n = score.filter((x) => x).length, pct = Math.round((100 * n) / score.length);
    const mech = parseInt(STATIC_FACTS.balancedAccuracy, 10);
    const box = el("div", "final");
    const h = el("p"); h.innerHTML = "<b>You scored " + n + " out of " + score.length + " (" + pct + "%).</b>";
    box.appendChild(h);
    box.appendChild(el("p", null, "The set was half right and half wrong, so guessing scores 50%. You judged SQL against a database you have never seen, with no correct answer to compare against: roughly the position of a reviewer on a real team. In the whole test, " + facts.silent + " of the " + facts.wrong + " mistakes ran without any error."));
    const board = el("div", "board");
    [["You, by eye", pct, "you"], ["Guessing at random", 50, "chance"], ["The four-answer check, on all 600", mech, "mech"]].forEach(([lab, v, cls]) => {
      const row = el("div", "brow"), track = el("div", "btrack"), fill = el("div", "bfill " + cls);
      track.appendChild(fill);
      row.append(el("div", "bl", lab), track, el("div", "bval", v + "%"));
      board.appendChild(row);
      setTimeout(() => { fill.style.width = v + "%"; }, 60);
    });
    board.appendChild(el("p", "hint", "All three judge whether an answer is right on a balanced mix of right and wrong. The check needs no correct answer to compare against: it flags a question when its four answers do not all return the same rows. That caught " + facts.caught + " of the " + facts.wrong + " mistakes and flagged " + facts.falseAlarms + " right answers along the way."));
    box.appendChild(board);
    box.appendChild(el("div", "beat", pct >= mech ? "You matched the four-answer check." : pct > 50 ? "Better than chance, and below the four-answer check." : "At or below chance. That is what a reviewer sees: SQL that runs, with no correct answer to compare it to."));
    const share = el("div", "shareRow");
    const sb = el("button", null, "Copy my result"), again = el("button", null, "Try six more");
    sb.type = again.type = "button";
    sb.onclick = () => {
      const txt = "I scored " + n + "/" + score.length + " spotting wrong AI-written SQL by eye. Yardstick, a pre-registered test of 600 AI answers: " + location.href.split("#")[0];
      const done = () => { let s = share.querySelector(".said"); if (!s) { s = el("span", "said"); share.appendChild(s); } s.textContent = "copied"; setTimeout(() => { s.textContent = ""; }, 2200); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, () => {});
    };
    again.onclick = () => { pool = buildPool(runs); start(); };
    share.append(sb, again); box.appendChild(share);
    host.appendChild(box); host.appendChild(strip());
  }

  document.addEventListener("keydown", (e) => {
    const t = e.target;
    if (!started || (t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT" || t.tagName === "SELECT"))) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (!answered) {
      const b = host.querySelectorAll(".choices button");
      if (b.length === 2 && k === "y") { e.preventDefault(); b[0].click(); return; }
      if (b.length === 2 && k === "n") { e.preventDefault(); b[1].click(); return; }
    }
    if (k === "enter" || k === "arrowright") {
      const nxt = host.querySelector(".reveal .choices button");
      if (nxt) { e.preventDefault(); nxt.click(); }
    }
  });

  start();
}
