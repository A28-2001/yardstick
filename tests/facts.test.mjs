import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { computeFacts, STATIC_FACTS, CLAIMS_TEXT, exampleRuns } from "../docs/js/facts.js";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const runs = JSON.parse(read("docs/data/runs.json")).runs;
const facts = computeFacts(runs);
const all = { ...facts, ...STATIC_FACTS };

test("facts computed from runs.json equal the verified values", () => {
  assert.deepEqual(facts, {
    total: 600, questions: 150, wrong: 104, silent: 93, loud: 11, confidentAll: 581,
    noWarning: 84, noWarningShare: "81%", caughtNoWarning: 77,
    flaggedRuns: 168, flaggedShare: "28%", flaggedQuestions: 42,
    caught: 87, missed: 17, falseAlarms: 81,
    projectionNoWarning: 11, strictNoWarning: 73, strictWrong: 93, strictShare: "78%",
  });
});

test("first-screen example matches the data", () => {
  const ex = Object.fromEntries(exampleRuns(runs).map((r) => [r.v, r]));
  assert.equal(ex.V2.ok, false);
  assert.equal(ex.V2.ran, true);
  assert.equal(ex.V2.conf, 0.9);
  assert.ok(ex.V3.ok && ex.V4.ok);
  assert.ok(Object.values(ex).every((r) => r.flagged));
});

test("every fact appears in CLAIMS.md", () => {
  const claims = read("CLAIMS.md");
  for (const [key, text] of Object.entries(CLAIMS_TEXT)) {
    assert.ok(claims.includes(text(facts)), `${key}: "${text(facts)}" not found in CLAIMS.md`);
  }
});

test("every data-fact value written in the pages equals the computed value", () => {
  const pages = readdirSync(new URL("docs/", root)).filter((f) => f.endsWith(".html"));
  for (const page of pages) {
    const html = read("docs/" + page);
    for (const m of html.matchAll(/data-fact="([A-Za-z]+)"[^>]*>([^<]*)</g)) {
      assert.ok(m[1] in all, `${page}: unknown fact "${m[1]}"`);
      assert.equal(m[2], String(all[m[1]]), `${page}: ${m[1]} written as "${m[2]}"`);
    }
  }
});
