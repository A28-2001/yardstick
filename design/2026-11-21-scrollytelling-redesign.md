# Yardstick site redesign: scrollytelling spec

Date: 2026-11-21. Status: draft for review. Nothing in this spec is built yet.

## 1. Goal and success criteria

**Goal.** A first-time visitor understands what the page is and what it found from the first screen alone, then can follow one real mistake, see the whole result, try the quiz, and read what to do about it. The core meaning of the study does not change.

**Readers.** A hiring manager at an AI company (5 seconds, then maybe the method), and a smart non-technical reader who does not know SQL.

**Done means all of these hold:**
1. The first screen is the locked hero9 design (section 3), on phone and desktop, light and dark.
2. Every number on both pages is computed from public data, matches `CLAIMS.md`, and is checked by a test.
3. All tests pass locally (section 7).
4. Screen checks pass: phone, tablet, desktop, light, dark, reduced motion; no sideways overflow; no console errors; every story step reachable.
5. Aakash has looked at the finished page and said yes. Only then is anything pushed.

No more AI critic scoring rounds. They were stopped on 2026-11-21 after scores plateaued and flipped between rounds.

## 2. Hard rules

- No em or en dashes anywhere: pages, README, figures, commits.
- No overstating. Every factual line is checked against the data before it is written; anything not in `CLAIMS.md` is either verified and added, or cut.
- Do not edit `PREREGISTRATION.md` or any `results/*.csv`.
- 100% free. No paid services, no framework, no build step.
- `.env` is never committed.
- Work happens on a local `redesign` branch. Nothing is pushed (not even the branch, since the repo is public) until Aakash approves the finished page.

## 3. First screen (locked)

Source: `hero9.html` mockup (session scratchpad). Content, exactly:

- Byline: "By Aakash Mehta, AI implementation engineer · July 2026 · LinkedIn", then "I built this test and the check it measures, and published the code."
- Headline: "In my test of AI looking up answers in a database, most of its mistakes came with no warning."
- Lede: "If you use AI to answer questions about data, this is how it can mislead you. The check I tested: ask the same question four times (two AI models, each once with a few solved examples and once without). When the four answers disagree, a person looks."
- Result box:
  - **84** of 104 wrong answers came with no warning. "150 questions, 4 answers each: 600 answers, 104 of them wrong. For 84, there was no error and the AI rated its own confidence 90% or higher."
  - **77** of those 84 were caught by the check. "The cost: 28% of answers went to a person, and about half of those were actually right."
- Buttons: "Spot the wrong answer" (6 real examples, 1 minute) jumps to the quiz. "How it was tested" (Method, data and code) jumps to the method appendix.
- Example card (university records, "Which year had the most degrees awarded?"):
  - 2002, one AI answer: no error, confidence 90%; it counted how many campuses reported each year instead of adding up the degrees.
  - 2004, the correct answer: the other three answers said 2004.
  - Caught by the check: the four answers disagreed, so this question went to a person.
- Small print: "For technical readers: text-to-SQL on the public Spider benchmark, 150 questions. Meta's open Llama 3.1 8B and 3.3 70B, each prompted with and without solved examples (600 answers). Confidence is the figure the AI gave when asked. Pre-registered. Not tested on newer frontier models."

Facts behind it (all verified 2026-11-21):

| Line | Source |
|---|---|
| 104 of 600 wrong; 84 with no error and confidence at least 0.9 | `runs.json`, `CLAIMS.md` |
| 77 of 84 caught | flag rule: the 4 answers to a question do not all return the same rows |
| 28% of answers flagged (168 of 600); about half right (81 of 168) | same flag rule |
| Example: V2 (8B, few-shot) returned 2002 with confidence 0.9, query ran. V1, V3, V4 all returned 2004 (V1 is scored wrong only because it also returned an extra column). Gold returns 2004. | re-executed on `databases/csu_1/csu_1.sqlite` |

Parallax on the first screen: one drifting ghost of the example card behind the text, nothing more.

## 4. The story, top to bottom

**Chapter 1, one mistake.** The same degrees question as the first screen, so the page tells one story. Six pinned steps beside scrolling text:
1. The question.
2. What V2 wrote (`GROUP BY Year ORDER BY COUNT(Degrees)`).
3. It ran with no error and returned 2002.
4. The right query adds the degrees (`SUM`) and returns 2004.
5. Asked how sure it was, it said 90%.
6. The other three answers said 2004, so the four disagree and the question is flagged.

*Change from the approved Section 1:* that section used the professors question. Switching to the degrees question keeps the first screen and Chapter 1 on one example. If you prefer the professors question, it was already verified (all four answers wrong, all ran, all flagged).

**Chapter 2, zoom out.** The 600-dot field. It opens with this question's four dots lit, labelled "the question you just watched": two red (V1, V2) and two neutral (V3, V4). V1's dot carries a note: "right year, extra column: counted wrong under strict scoring". Then the dot steps:
- 104 wrong
- 93 of them ran with no error
- 581 of all 600 answers came with stated confidence of 90% or more
- 168 flagged by the check
- 87 of the 104 caught, 17 missed

**Chapter 3, your turn.** The quiz: always 3 wrong and 3 right, in shuffled order, then the scoreboard. Projection-only "wrong" cases (right information, extra or missing column) are excluded from the quiz pool, because a reader would fairly call them right.

**Chapter 4, what to do about it.** One dark band. The check as a practical rule, with its costs stated plainly:
- 81 correct answers flagged for nothing
- 17 mistakes missed
- about a tenth of a cent per question at list prices ($0.17 for all 600 runs)
- a two-setup version was never measured
- it was never deployed anywhere

**Chapter 5, what didn't work.** Three short cards, one number each:
- Solved examples in the prompt: no significant gain (+8 points on complex questions, p = 0.42).
- The AI's own confidence is a weak signal (AUC 0.647, where 0.5 is a coin flip; agreement scores 0.861).
- Routing by predicted difficulty did not reliably beat random (78.3% against a 75.5% average for random).

**Appendix.** The 600-run explorer with the variant picker, the SQL console, a short method summary (pre-registration, Spider, McNemar exact test, bootstrap CIs, Benjamini Hochberg), and the strictness note: "A wrong answer is counted strictly: right information with an extra or missing column counts as wrong. 11 of the 84 are this kind; without them it is 73 of 93 (78%), so the headline holds." Links to the report, GitHub and `CLAIMS.md`.

**Removed from today's page:** "Why this exists" and "What this is" boxes, the method chips, the four-number strip, the bar chart (it stays in the report), and the hotel example (inn_1), which is projection-only and not a real mistake.

## 5. Look and motion

**Type.** Source Serif 4 for headlines and big numbers, IBM Plex Sans for body, IBM Plex Mono for SQL and small labels. Four sizes. Fonts are self-hosted under SIL Open Font License (download approved).

**Colour.** Each colour means one thing:
- Red: a wrong answer.
- Green: a correct answer, or a mistake the check caught.
- Blue: something to click.
- Paper, panel, ink, two greys and a line colour for everything else.

*Change from the approved Section 2:* that section had correct answers in grey and the check in blue. hero9, now locked, uses green for correct and caught, so the palette follows hero9. In the Chapter 2 dot field, correct answers stay neutral grey so the red ones stand out; green is used only for "caught".

**Surfaces.** Page, card, and one dark band (Chapter 4 only).

**Motion.**
- Normal scrolling. No scroll-jacking.
- At most two depth layers per screen: the ghost card on the first screen, a faint chapter number behind each chapter opening.
- Story graphics pin while text scrolls past. Dots glide to new groups over about a second; card rows fade in.
- Reduced motion: no parallax, instant changes, every step still readable.
- Phone: graphic pinned to the top half, text cards scroll underneath.

**Accessibility.** Colour is never the only signal (errored mistakes are hollow dots, every step has a text legend). WCAG AA contrast in light and dark. Quiz keeps Y, N and Enter keys. Dark mode follows the device setting only.

**Report page.** Keeps its layout, adopts the same tokens and fonts. Its five figures are redrawn in the new palette with the self-hosted fonts.

## 6. How it is built

Plain HTML, CSS and JavaScript served from `docs/`. Today's `docs/index.html` (73 KB) is split:

| File | Job |
|---|---|
| `docs/index.html` | Text and structure only |
| `docs/css/tokens.css` | Colours, fonts, sizes, dark mode; shared with the report |
| `docs/css/site.css` | Layout and components |
| `docs/js/scroll.js` | Parallax and pinned story steps |
| `docs/js/story.js` | Chapter 1 card and Chapter 2 dots |
| `docs/js/quiz.js` | Quiz and scoreboard |
| `docs/js/explorer.js` | 600-run table and variant picker |
| `docs/js/sqlengine.js` | The SQL engine, no page code mixed in |
| `docs/js/main.js` | Loads data and starts everything |
| `docs/fonts/` | Self-hosted font files |

**Numbers come from data.**
- `scripts/export_web_data.py` adds a `flagged` field to every run in `runs.json`, so 168, 87 and 81 are reproducible from public data.
- Every story number sits in a tagged span, filled from data on load. The same value is also written into the HTML for link previews, search engines and readers without JavaScript.
- The degrees example is selected by its question ID; its SQL and results come from the data.

**If data fails to load.** The first screen and Chapter 1 still read correctly from the written values. The dot field, quiz and explorer show "Couldn't load the data" instead of breaking.

**Out of scope.** Generation pipeline fixes (local response logging, ORDER BY row-order determinism) stay a separate job. No new model runs.

## 7. Tests

Node's built-in test runner; nothing to install.
1. SQL engine, including the old bug where `NOT` was ignored.
2. Quiz: always 3 right and 3 wrong, order actually shuffled, no projection-only cases.
3. Facts: every number on both pages equals the value computed from `runs.json` and the value in `CLAIMS.md`.
4. Wording: no em or en dashes and none of the banned phrases in pages, README and figure text.

A GitHub Actions workflow runs these on every push. It is committed with the work and starts running only once the code is pushed.

## 8. Shipping

1. Build on the local `redesign` branch.
2. Run the tests and the screen checks (section 1, item 4), with screenshots I take myself.
3. Re-run the fact extraction over the new pages; fix or cut anything not in `CLAIMS.md`.
4. First screen appears before the 288 KB `runs.json` finishes loading.
5. New share card with the hero9 headline, under a new filename (replacing `card-quiz-v4.png`) so LinkedIn refetches it. Aakash runs the LinkedIn Post Inspector once after the merge.
6. Aakash reviews the page in the browser pane and approves.
7. Push and merge to `main` in one step. GitHub Pages updates. One revert undoes it.

**After this job.** Job 3 rewrites the README's first screen to match. Outside the repo, mehtaakash.com still has two stale lines (location, and "a cheap verifier" instead of four setups).

## 9. Changes from the approved sections, for review

1. First screen is hero9, not the earlier C-then-A mockup (different headline and buttons).
2. Chapter 1 uses the degrees question instead of the professors question.
3. Green means correct or caught; blue means clickable (was: grey correct, blue check).
4. Acceptance no longer uses AI critic scores; it is tests, screen checks, fact re-run and your approval.
5. Added: projection-only cases leave the quiz pool, a strictness note in the appendix, and the hotel example is removed.
