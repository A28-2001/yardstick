"""Phase 0 exit-criteria verifier (spec §14, Phase 0).

Exit criteria checked:
  1. .env loads and required vars are present
  2. Supabase Postgres connects; results-schema tables exist
  3. API calls to BOTH Groq models succeed — cheap/8B (V1,V2) and strong/70B (V3,V4)
  4. A SQLite database opens READ-ONLY and executes a query

Everything runs on Groq's free tier; there is no paid provider in this design.

Run:  python scripts/verify_setup.py

Missing credentials are reported as SKIP (yellow), not FAIL, so this can be run
incrementally as you fill in .env. Phase 0 is complete when checks 2, 3, 4 pass.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
_MARK = {PASS: "\033[92m✓\033[0m", FAIL: "\033[91m✗\033[0m", SKIP: "\033[93m—\033[0m"}


def _first(exc: BaseException) -> str:
    """First line of an error message, or the type name if empty (never IndexErrors)."""
    s = str(exc).strip()
    return s.splitlines()[0] if s else type(exc).__name__


def _row(status: str, name: str, detail: str = "") -> tuple[str, str, str]:
    print(f"  {_MARK[status]} {status:<4} {name}" + (f"  ({detail})" if detail else ""))
    return status, name, detail


def check_env() -> tuple[str, str, str]:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return _row(FAIL, "env", "python-dotenv not installed — run: pip install -r requirements.txt")
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return _row(SKIP, "env", "no .env yet — copy .env.example to .env and fill in")
    # override=True: .env is authoritative, beating any stale value exported in the
    # shell (e.g. an old GROQ_API_KEY in ~/.zshrc), which otherwise silently wins.
    load_dotenv(env_path, override=True)
    present = [k for k in ("GROQ_API_KEY", "ANTHROPIC_API_KEY", "DATABASE_URL") if os.getenv(k)]
    return _row(PASS if present else SKIP, "env", f".env loaded; set: {', '.join(present) or 'none'}")


def check_postgres() -> tuple[str, str, str]:
    url = os.getenv("DATABASE_URL")
    if not url or "[PASSWORD]" in url or "[HOST]" in url:
        return _row(SKIP, "supabase-postgres", "DATABASE_URL not set")
    try:
        import psycopg
    except ImportError:
        return _row(FAIL, "supabase-postgres", "psycopg not installed")
    try:
        with psycopg.connect(url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public'"
                )
                tables = {r[0] for r in cur.fetchall()}
        expected = {"questions", "variants", "runs", "executions", "question_features"}
        missing = expected - tables
        if missing:
            return _row(FAIL, "supabase-postgres",
                        f"connected but missing tables: {sorted(missing)} — apply sql/schema.sql")
        return _row(PASS, "supabase-postgres", f"connected; all {len(expected)} tables present")
    except Exception as e:  # noqa: BLE001
        return _row(FAIL, "supabase-postgres", _first(e))


def check_groq() -> tuple[str, str, str]:
    """Both models we actually use: cheap/8B (V1,V2) and strong/70B (V3,V4)."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return _row(SKIP, "groq-api", "GROQ_API_KEY not set")
    try:
        from groq import Groq
    except ImportError:
        return _row(FAIL, "groq-api", "groq not installed")
    cheap = os.getenv("GROQ_MODEL_CHEAP", "llama-3.1-8b-instant")
    strong = os.getenv("GROQ_MODEL_STRONG", "llama-3.3-70b-versatile")
    client = Groq(api_key=key)
    for model in (cheap, strong):
        try:
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with the single word: ok"}],
                max_tokens=5,
                temperature=0,
            )
        except Exception as e:  # noqa: BLE001
            return _row(FAIL, "groq-api", f"{model}: {_first(e)}")
    return _row(PASS, "groq-api", f"{cheap} ✓  {strong} ✓")


def check_sqlite_readonly() -> tuple[str, str, str]:
    """Verify the read-only URI mechanism the execution sandbox relies on (§8.2)."""
    tmp = Path(tempfile.gettempdir()) / "yardstick_ro_check.sqlite"
    try:
        con = sqlite3.connect(tmp)
        con.executescript("CREATE TABLE t(x); INSERT INTO t VALUES (1),(2),(3);")
        con.commit()
        con.close()

        uri = f"file:{tmp}?mode=ro"
        ro = sqlite3.connect(uri, uri=True)
        n = ro.execute("SELECT count(*) FROM t").fetchone()[0]
        # confirm writes are actually rejected in read-only mode
        write_blocked = False
        try:
            ro.execute("INSERT INTO t VALUES (4)")
        except sqlite3.OperationalError:
            write_blocked = True
        ro.close()
        if n == 3 and write_blocked:
            return _row(PASS, "sqlite-readonly", "opened mode=ro, read 3 rows, writes blocked")
        return _row(FAIL, "sqlite-readonly", f"rows={n} write_blocked={write_blocked}")
    except Exception as e:  # noqa: BLE001
        return _row(FAIL, "sqlite-readonly", _first(e))
    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    print("Yardstick — Phase 0 verification\n")
    results = [
        check_env(),
        check_postgres(),
        check_groq(),
        check_sqlite_readonly(),
    ]
    print()
    statuses = [r[0] for r in results]
    core = {name: st for st, name, _ in results
            if name in {"supabase-postgres", "groq-api", "sqlite-readonly"}}
    if any(s == FAIL for s in statuses):
        print("Phase 0 NOT complete — resolve the FAIL rows above.")
        return 1
    if all(core.get(n) == PASS for n in core):
        print("Phase 0 exit criteria MET ✓  (DB, both providers, read-only SQLite all verified)")
        return 0
    print("No failures, but some checks SKIPPED — fill in .env and re-run to complete Phase 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
