import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const pages = readdirSync(new URL("docs/", root)).filter((f) => f.endsWith(".html")).map((f) => "docs/" + f);

// Public-facing text: pages, README, CLAIMS, figure labels, the share card.
const DASH_FILES = [...pages, "README.md", "CLAIMS.md", "scripts/make_figures.py"];
// Overstatements found in the November 2026 fact pass. CLAIMS.md is excluded here
// because its audit note quotes them.
const BANNED = ["plausible", "believable", "most people", "simple fix", "simple check",
  "never need a human", "asking 4 times", "1 in 750"];

test("no em or en dashes in public text", () => {
  for (const f of DASH_FILES) {
    const lines = read(f).split("\n");
    lines.forEach((line, i) => {
      assert.ok(!/[–—]/.test(line), `${f}:${i + 1} has a dash: ${line.trim().slice(0, 80)}`);
    });
  }
});

test("none of the overstatements from the fact pass", () => {
  for (const f of [...pages, "README.md"]) {
    const text = read(f).toLowerCase();
    for (const b of BANNED) assert.ok(!text.includes(b), `${f} contains "${b}"`);
  }
});
