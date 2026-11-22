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
