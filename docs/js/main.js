// Loads the data and starts everything. The page text already holds every number, so
// if the data fails to load the first screen and Chapter 1 still read correctly; the
// dot field, quiz, explorer and console show a short notice instead.

import { computeFacts, STATIC_FACTS } from "./facts.js";
import { parallax } from "./scroll.js";
import { initOne, initDots } from "./story.js";
import { initQuiz } from "./quiz.js";
import { initExplorer, initConsole } from "./explorer.js";

function fillFacts(runs) {
  const all = { ...computeFacts(runs), ...STATIC_FACTS };
  document.querySelectorAll("[data-fact]").forEach((n) => {
    const v = all[n.dataset.fact];
    if (v != null && n.textContent !== String(v)) n.textContent = String(v);
  });
}

// Bump when runs.json changes shape, so a browser holding an older cached copy
// fetches the new one instead of mixing new code with old data.
const DATA_VERSION = "2026-11-21";
const REQUIRED = ["qid", "flagged"];

async function load() {
  try {
    const r = await fetch("data/runs.json?v=" + DATA_VERSION);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();
    const missing = REQUIRED.filter((c) => !(d.columns || []).includes(c));
    if (missing.length) throw new Error("data is missing " + missing.join(", "));
    return d.runs;
  } catch (e) {
    // The written numbers stay on the page; only the data-driven parts show a notice.
    console.warn("Yardstick: could not load runs.json:", e.message);
    return null;
  }
}

parallax();
const runs = await load();
if (runs) fillFacts(runs);
initOne(document.querySelector('[data-story="one"]'), runs);
initDots(document.querySelector('[data-story="dots"]'), runs);
initQuiz(runs);
initExplorer(runs);
initConsole(runs);
