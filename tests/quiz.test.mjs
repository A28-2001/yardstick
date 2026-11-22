import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildPool, QN } from "../docs/js/quiz.js";
import { EXAMPLE_QID } from "../docs/js/facts.js";

const runs = JSON.parse(readFileSync(new URL("../docs/data/runs.json", import.meta.url))).runs;

// Small seeded generator so failures are reproducible.
function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

test("every pool has exactly 3 wrong and 3 right, none projection-only, not the example", () => {
  for (let seed = 1; seed <= 1000; seed++) {
    const pool = buildPool(runs, mulberry32(seed));
    assert.equal(pool.length, QN);
    assert.equal(pool.filter((r) => r.silent).length, 3);
    assert.equal(pool.filter((r) => r.ok).length, 3);
    assert.ok(pool.every((r) => r.err !== "wrong_projection"));
    assert.ok(pool.every((r) => r.qid !== EXAMPLE_QID));
  }
});

test("order is actually shuffled: both kinds appear first", () => {
  const firsts = new Set();
  for (let seed = 1; seed <= 200; seed++) firsts.add(buildPool(runs, mulberry32(seed))[0].ok);
  assert.deepEqual([...firsts].sort(), [false, true]);
});
