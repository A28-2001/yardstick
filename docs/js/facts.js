// Every number the story shows, computed from runs.json, plus the few that come from
// analysis scripts rather than per-run data. The page fills each <span data-fact="key">
// from here; tests/facts.test.mjs checks the written HTML, these values and CLAIMS.md agree.

export const EXAMPLE_QID = "q795bbdf3dc7d"; // csu_1: "Which year has the most degrees conferred?"

const NO_WARNING_CONF = 0.9;

const pct = (a, b) => Math.round((100 * a) / b) + "%";

export function noWarning(r) {
  return !r.ok && r.ran && r.conf !== null && r.conf >= NO_WARNING_CONF;
}

export function computeFacts(runs) {
  const wrong = runs.filter((r) => !r.ok);
  const nw = runs.filter(noWarning);
  const flagged = runs.filter((r) => r.flagged);
  const proj = nw.filter((r) => r.err === "wrong_projection");
  const strictWrong = wrong.length - proj.length;
  const strictNoWarning = nw.length - proj.length;
  return {
    total: runs.length,
    questions: new Set(runs.map((r) => r.qid)).size,
    wrong: wrong.length,
    silent: runs.filter((r) => r.silent).length,
    loud: wrong.filter((r) => !r.ran).length,
    confidentAll: runs.filter((r) => r.conf !== null && r.conf >= NO_WARNING_CONF).length,
    noWarning: nw.length,
    noWarningShare: pct(nw.length, wrong.length),
    caughtNoWarning: nw.filter((r) => r.flagged).length,
    flaggedRuns: flagged.length,
    flaggedShare: pct(flagged.length, runs.length),
    flaggedQuestions: new Set(flagged.map((r) => r.qid)).size,
    caught: wrong.filter((r) => r.flagged).length,
    missed: wrong.filter((r) => !r.flagged).length,
    falseAlarms: flagged.filter((r) => r.ok).length,
    projectionNoWarning: proj.length,
    strictNoWarning,
    strictWrong,
    strictShare: pct(strictNoWarning, strictWrong),
  };
}

export function exampleRuns(runs) {
  return runs.filter((r) => r.qid === EXAMPLE_QID);
}

// From analysis scripts, not runs.json. Each names its CLAIMS.md row.
export const STATIC_FACTS = {
  fewshotComplexPts: "+8", //     "Few-shot lift (pre-registered)", results/primary_analysis.csv
  fewshotComplexP: "0.42", //     same row; mcnemar_p 0.424
  aucConfidence: "0.647", //      "Predicting correctness, AUC"
  aucAgreement: "0.861", //       same row
  routerAccuracy: "78.3%", //     "Difficulty routing accuracy"
  randomAverage: "75.5%", //      "Random routing at the same budget"
  listCost: "$0.17", //           "List-price cost of the 600 runs"
};

// The text each fact must appear as in CLAIMS.md (checked by tests/facts.test.mjs).
export const CLAIMS_TEXT = {
  wrong: (f) => `| ${f.wrong} |`,
  silent: (f) => `${f.silent} of ${f.wrong}`,
  loud: (f) => `| ${f.loud}, all invented`,
  confidentAll: (f) => `${f.confidentAll} of ${f.total}`,
  noWarning: (f) => `${f.noWarning} of ${f.wrong}`,
  caughtNoWarning: (f) => `${f.caughtNoWarning} of ${f.noWarning}`,
  flaggedRuns: (f) => `${f.flaggedRuns} of ${f.total} outputs, ${f.flaggedShare}`,
  flaggedQuestions: (f) => `${f.flaggedQuestions} of ${f.questions}`,
  caught: (f) => `${f.caught} of ${f.wrong}`,
  missed: (f) => `${f.missed} of ${f.wrong}`,
  falseAlarms: (f) => `${f.falseAlarms} of ${f.flaggedRuns}`,
  projectionNoWarning: (f) => `${f.projectionNoWarning} of ${f.noWarning}`,
  strictNoWarning: (f) => `${f.strictNoWarning} of ${f.strictWrong} (${f.strictShare})`,
  fewshotComplexP: () => `p = ${STATIC_FACTS.fewshotComplexP}`,
  fewshotComplexPts: () => `complex ${STATIC_FACTS.fewshotComplexPts} pts`,
  aucConfidence: () => `stated confidence ${STATIC_FACTS.aucConfidence}`,
  aucAgreement: () => `agreement ${STATIC_FACTS.aucAgreement}`,
  routerAccuracy: () => `| ${STATIC_FACTS.routerAccuracy} at`,
  randomAverage: () => `average ${STATIC_FACTS.randomAverage}`,
  listCost: () => `| ${STATIC_FACTS.listCost} (`,
};
