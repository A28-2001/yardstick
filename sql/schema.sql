-- Yardstick results schema (Supabase Postgres).  Spec §7.
-- Target databases stay as local SQLite files; only results live here.
-- Apply with: psql "$DATABASE_URL" -f sql/schema.sql

CREATE TABLE IF NOT EXISTS questions (
    question_id         TEXT PRIMARY KEY,
    db_id               TEXT NOT NULL,
    question_text       TEXT NOT NULL,
    gold_sql            TEXT NOT NULL,
    gold_result_hash    TEXT NOT NULL,
    gold_row_count      INTEGER NOT NULL,
    gold_col_count      INTEGER NOT NULL,
    spider_difficulty   TEXT NOT NULL,     -- easy, medium, hard, extra
    tier                TEXT NOT NULL,     -- simple, moderate, complex
    schema_ddl          TEXT NOT NULL,
    split               TEXT NOT NULL,     -- train or test
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS variants (
    variant_id          TEXT PRIMARY KEY,  -- V1, V2, V3, V4
    prompt_strategy     TEXT NOT NULL,     -- zero-shot, few-shot
    model               TEXT NOT NULL,     -- groq, claude
    prompt_version      TEXT NOT NULL,     -- git hash or semver
    config_path         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id              BIGSERIAL PRIMARY KEY,
    question_id         TEXT REFERENCES questions(question_id),
    variant_id          TEXT REFERENCES variants(variant_id),
    replicate           INTEGER DEFAULT 1,
    raw_output          TEXT NOT NULL,     -- full model response, ALWAYS store (§7.1)
    extracted_sql       TEXT,              -- null if extraction failed
    extraction_success  BOOLEAN NOT NULL,
    self_confidence     NUMERIC,
    input_tokens        INTEGER NOT NULL,
    output_tokens       INTEGER NOT NULL,
    cost_usd            NUMERIC NOT NULL,
    latency_ms          INTEGER NOT NULL,
    temperature         NUMERIC NOT NULL,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (question_id, variant_id, replicate)
);

CREATE TABLE IF NOT EXISTS executions (
    execution_id            BIGSERIAL PRIMARY KEY,
    run_id                  BIGINT REFERENCES runs(run_id) UNIQUE,
    executed                BOOLEAN NOT NULL,       -- did it run at all
    execution_error         TEXT,
    result_hash             TEXT,
    result_row_count        INTEGER,
    result_col_count        INTEGER,
    exact_match             BOOLEAN,                -- ordered comparison
    set_match               BOOLEAN,                -- THE primary correctness flag (§9.2)
    execution_time_ms       NUMERIC,
    timed_out               BOOLEAN NOT NULL DEFAULT false,
    error_type              TEXT                    -- see §9.5 taxonomy
);

CREATE TABLE IF NOT EXISTS question_features (
    question_id             TEXT PRIMARY KEY REFERENCES questions(question_id),
    question_token_count    INTEGER,
    question_char_count     INTEGER,
    schema_table_count      INTEGER,
    schema_column_count     INTEGER,
    schema_ddl_token_count  INTEGER,
    question_entity_count   INTEGER,
    has_superlative         BOOLEAN,
    has_comparison          BOOLEAN,
    has_aggregation_cue     BOOLEAN,
    has_temporal_cue        BOOLEAN,
    has_negation            BOOLEAN,
    clause_count            INTEGER,
    numeric_mention_count   INTEGER,
    -- Added from §11.3 schema-feature list (not in the §7 DDL, reconciled here):
    foreign_key_count       INTEGER,
    max_table_column_count  INTEGER
    -- HARD CONSTRAINT (§11.3): every column here is computable from question
    -- text + schema DDL ALONE. No feature may derive from the gold SQL.
);

-- Helpful indexes for the analysis phase (not in spec; safe additions).
CREATE INDEX IF NOT EXISTS idx_questions_tier   ON questions(tier);
CREATE INDEX IF NOT EXISTS idx_questions_split  ON questions(split);
CREATE INDEX IF NOT EXISTS idx_questions_db_id  ON questions(db_id);
CREATE INDEX IF NOT EXISTS idx_runs_variant     ON runs(variant_id);
CREATE INDEX IF NOT EXISTS idx_runs_question    ON runs(question_id);
