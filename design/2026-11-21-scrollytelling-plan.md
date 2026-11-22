# Yardstick redesign: build plan

Spec: `design/2026-11-21-scrollytelling-redesign.md` (approved 2026-11-21).
Branch: local `redesign`. Nothing is pushed until Aakash approves the finished page (task 14).

Each task ends with its own check and a local commit. Rules for every task: no em or en dashes, every number traced to data and `CLAIMS.md`, no edits to `PREREGISTRATION.md` or `results/*.csv`, `.env` never committed.

Starting point (checked 2026-11-21): `docs/index.html` is one 73 KB file with CSS at lines 22 to 446 and one script at lines 651 to 1554 (quiz, explorer, SQL engine, examples, count-up). It loads `data/runs.json` (288 KB, 600 runs, no question id, no flag field). `.github/workflows/` exists and is empty. Node v23.10.0 is installed.

---

## Phase A: data and logic (no visible change yet)

### Task 1. Branch and baseline
- Create local branch `redesign` from `main`. Commit the spec and this plan.
- Screenshot today's site (desktop, phone, light, dark) into the scratchpad as the "before" record.
- **Check:** `git branch` shows `redesign`; `git status` clean.

### Task 2. Add `qid` and `flagged` to `runs.json`
- In `scripts/export_web_data.py`: add `q.question_id` as `qid`, and a `flagged` field per run. A question is flagged when its four answers do not all return the same result set. Reuse the agreement code in `scripts/analyze_calibration.py` / `yardstick/comparison.py` (result-set canonical hash) instead of writing a second version.
- Add `"wrong_projection"` handling only through the existing `err` field (no new field needed).
- Re-export `docs/data/runs.json` from the local Postgres (start command in project memory).
- **Check:** a short script prints flagged runs = 168, flagged questions = 42, caught wrong = 87 of 104, flagged correct = 81, caught no-warning = 77 of 84. Existing fields are byte-identical to before for every run (diff the old and new files after dropping the two new keys).

### Task 3. `docs/js/facts.js`: every story number from data
- Pure ES module, no page code. Exports `computeFacts(runs)` returning a keyed object: `total` 600, `questions` 150, `wrong` 104, `silent` 93, `noWarning` 84, `confident` 581, `flaggedRuns` 168, `flaggedShare` 28%, `caught` 87, `missed` 17, `caughtNoWarning` 77, `falseAlarms` 81, `projectionNoWarning` 11, and the degrees example (selected by `qid`).
- Numbers that come from analysis scripts, not `runs.json` (AUC 0.647 / 0.861, p = 0.42, routing 78.3% / 75.5%, $0.17): kept in one `STATIC_FACTS` object in the same file, each with a comment naming its `CLAIMS.md` row.
- **Check:** task 6 test covers it.

### Task 4. `docs/js/sqlengine.js`
- Move the engine (tokenize, Parser, truthy, eq, aggregate, round, runQuery and helpers, today about lines 1113 to 1385) into an ES module that exports `runQuery(sql, rows)`. No DOM code in it.
- **Check:** task 6 test covers it, including `NOT LIKE`, `NOT IN`, `IS NOT NULL` and leading `NOT`.

### Task 5. `docs/js/quiz.js` logic split
- Pure function `buildPool(runs, rng)`: 3 wrong and 3 right, shuffled, excluding `err == "wrong_projection"` and the degrees example. DOM rendering stays separate in the same module.
- **Check:** task 6 test covers it.

### Task 6. Tests (`tests/` with `node --test`)
1. `sqlengine.test.mjs`: a fixed set of queries against a small fixture table, including every `NOT` form.
2. `quiz.test.mjs`: 1,000 seeded draws, each with exactly 3 wrong and 3 right, no projection-only items, first-position item varies.
3. `facts.test.mjs`: `computeFacts(runs.json)` equals the expected values; every `data-fact` value written in `docs/index.html` and `docs/report.html` equals the computed value; every fact value appears in `CLAIMS.md`.
4. `wording.test.mjs`: no U+2013 or U+2014 in `docs/*.html`, `README.md`, `CLAIMS.md`, figure text; none of the banned phrases ("plausible", "most people", "simple fix", "simple check", "never need a human").
- **Check:** `node --test tests/` all green. Commit.

---

## Phase B: the page

### Task 7. Tokens, fonts, base CSS
- Download woff2 files for Source Serif 4 (600), IBM Plex Sans (400, 500, 600) and IBM Plex Mono (400, 500) from the `@fontsource` packages on jsDelivr (SIL OFL, approved). Put them in `docs/fonts/` with the OFL licence text.
- `docs/css/tokens.css`: the hero9 palette (paper, panel, ink, mid, soft, line, acc blue, bad red, good green), dark values under `prefers-color-scheme`, four type sizes, `@font-face` rules.
- `docs/css/site.css`: layout, card, buttons, dark band, reduced-motion rules.
- **Check:** WCAG AA contrast computed for every text/background pair in light and dark (small script, printed table). Commit.

### Task 8. First screen
- Rebuild `docs/index.html` head and first screen from `hero9.html`, using the shared CSS, real links (LinkedIn, GitHub, report, `CLAIMS.md`), and `data-fact` spans holding the written values.
- Ghost-card parallax layer (one layer) in `docs/js/scroll.js`; off under reduced motion.
- **Check:** my own screenshots at 1440x900 and 390x844 (light, dark) match hero9; first screen renders with `runs.json` blocked. Commit.

### Task 9. Chapter 1 (one mistake) and Chapter 2 (dot field)
- `docs/js/story.js`: pinned graphic with step triggers via `IntersectionObserver` in `scroll.js`.
- Chapter 1: six steps from the spec; SQL and results read from the degrees example in data.
- Chapter 2: 600 dots on canvas or SVG; opens with this question's four dots lit (V1 carries the strict-scoring note); five steps with legends; errored mistakes drawn hollow.
- **Check:** every step reachable by scrolling and by keyboard; reduced motion shows final states; phone pins the graphic to the top half. Commit.

### Task 10. Chapter 3 (quiz), Chapters 4 and 5, appendix
- Quiz UI on the task 5 logic, Y / N / Enter kept, scoreboard.
- Chapter 4 dark band and Chapter 5 three cards, all numbers from `facts.js`.
- Appendix: `docs/js/explorer.js` (600-run table, variant picker, moved from today's code), SQL console on `sqlengine.js`, method summary with the strictness note, links. `docs/js/main.js` loads data and starts everything; on fetch failure shows "Couldn't load the data" in those blocks only.
- Remove: Why/What boxes, method chips, number strip, bar chart, hotel example.
- **Check:** quiz never shows a projection-only case; explorer and console work; data-blocked page still reads. Commit.

### Task 11. Report page
- `docs/report.html` adopts `tokens.css` and the fonts; layout unchanged; numbers get `data-fact` spans so the facts test covers them.
- `scripts/make_figures.py`: new palette, register the TTF versions of the same fonts with matplotlib (download TTFs from the `google/fonts` GitHub repo, same licence), regenerate the five figures.
- **Check:** figures open and read correctly in light and dark pages; facts test green. Commit.

### Task 12. Share card and metadata
- New share card with the hero9 headline at 2x, new filename (`card-v5.png`); update `og:image` and `twitter:image`.
- **Check:** card is sharp at 1200x630 and contains no dashes. Commit.

---

## Phase C: verify and ship

### Task 13. Full verification
- `node --test tests/` green.
- Screens: 390, 768, 1440 wide; light and dark; reduced motion on. No sideways overflow (`scrollWidth == clientWidth`), no console errors, every story step reachable.
- Speed: first screen paints before `runs.json` finishes (throttled check).
- Fact re-run: extract every numeric claim from both pages and the README; each one is in `CLAIMS.md` or gets checked and added, or cut.
- GitHub Actions workflow `.github/workflows/tests.yml` committed (runs `node --test` on push; starts only once pushed).

### Task 14. Review and ship
- Aakash reviews the page in the browser pane.
- After a clear yes: push `redesign`, merge to `main`, confirm GitHub Pages serves the new page. Aakash runs the LinkedIn Post Inspector once.
- Rollback: one `git revert` of the merge commit.

---

## Order and size

| Phase | Tasks | Rough size |
|---|---|---|
| A: data and logic | 1 to 6 | about one session |
| B: page | 7 to 12 | about two sessions (tasks 9 and 10 are the largest) |
| C: verify and ship | 13 to 14 | about half a session, then your review |

## Not in this plan
- No new model runs.
- Pipeline fixes (local response logging, ORDER BY determinism) stay a separate job.
- README first screen is job 3.
- mehtaakash.com fixes are outside this repo.
