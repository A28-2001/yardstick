import { test } from "node:test";
import assert from "node:assert/strict";
import { runQuery } from "../docs/js/sqlengine.js";

const rows = [
  { v: "V1", t: "simple", ok: true, ran: true, err: null, conf: 1.0, db: "a" },
  { v: "V1", t: "complex", ok: false, ran: true, err: "wrong_join", conf: 0.9, db: "b" },
  { v: "V2", t: "simple", ok: false, ran: false, err: "schema_error", conf: null, db: "a" },
  { v: "V3", t: "moderate", ok: true, ran: true, err: null, conf: 0.8, db: "c" },
];
const q = (s) => runQuery(s, rows).rows;

test("WHERE with booleans, including 0/1", () => {
  assert.deepEqual(q("SELECT v FROM runs WHERE ok = true"), [["V1"], ["V3"]]);
  assert.deepEqual(q("SELECT v FROM runs WHERE ok = 1"), [["V1"], ["V3"]]);
  assert.deepEqual(q("SELECT t FROM runs WHERE ok = false"), [["complex"], ["simple"]]);
});

test("every NOT form is applied, never dropped", () => {
  assert.deepEqual(q("SELECT t FROM runs WHERE NOT ok = true"), [["complex"], ["simple"]]);
  assert.deepEqual(q("SELECT v FROM runs WHERE err NOT LIKE 'wrong_join'"), q("SELECT v FROM runs WHERE NOT err LIKE 'wrong_join'"));
  assert.deepEqual(q("SELECT t FROM runs WHERE conf IS NOT NULL").length, 3);
  assert.deepEqual(q("SELECT t FROM runs WHERE NOT conf IS NULL").length, 3);
  assert.deepEqual(q("SELECT t FROM runs WHERE v NOT IN ('V1', 'V2')"), [["moderate"]]);
});

test("GROUP BY, aggregates, ORDER BY and LIMIT", () => {
  const r = runQuery("SELECT v, COUNT(*) FROM runs GROUP BY v ORDER BY v DESC LIMIT 2", rows);
  assert.deepEqual(r.rows, [["V3", 1], ["V2", 1]]);
  assert.equal(r.total, 3);
});

test("unknown column is a clear error", () => {
  assert.throws(() => q("SELECT nope FROM runs"), /No column/);
});
