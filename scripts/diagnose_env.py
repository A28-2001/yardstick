"""Safe .env diagnostic, reveals the STRUCTURE of your config without printing
any secret values. Helps debug auth failures.  Run: python scripts/diagnose_env.py
"""
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# override=True so .env wins over any stale shell export (e.g. GROQ_API_KEY in ~/.zshrc)
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

print("API keys (values hidden):")
for k, expected in [("GROQ_API_KEY", "gsk_"), ("ANTHROPIC_API_KEY", "sk-ant-")]:
    v = os.getenv(k) or ""
    prefix_ok = v.startswith(expected)
    issues = []
    if not v:
        issues.append("EMPTY")
    if v != v.strip():
        issues.append("has leading/trailing whitespace")
    if not prefix_ok and v:
        issues.append(f"does NOT start with {expected!r}")
    print(f"  {k}: length={len(v)}, starts_with={v[:len(expected)]!r} "
          f"(expected {expected!r})  {'OK' if not issues else '⚠ ' + '; '.join(issues)}")

print("\nDATABASE_URL (password hidden):")
raw = os.getenv("DATABASE_URL") or ""
if not raw:
    print("  EMPTY")
else:
    u = urlparse(raw)
    kind = ("SESSION/TXN POOLER" if u.hostname and "pooler.supabase.com" in u.hostname
            else "DIRECT" if u.hostname and u.hostname.startswith("db.")
            else "unknown")
    print(f"  connection type : {kind}")
    print(f"  username        : {u.username!r}   "
          f"({'pooler-style postgres.<ref> ✓' if u.username and '.' in u.username else 'plain postgres'})")
    print(f"  host            : {u.hostname}")
    print(f"  port            : {u.port}")
    print(f"  dbname          : {u.path.lstrip('/')}")
    pw = u.password or ""
    print(f"  password length : {len(pw)}  "
          f"{'⚠ EMPTY' if not pw else ''}")
    problems = []
    if "[" in raw or "]" in raw:
        problems.append("contains leftover [ ] placeholder brackets, replace them")
    if pw and pw != pw.strip():
        problems.append("password has whitespace")
    print("  status          :", "OK" if not problems else "⚠ " + "; ".join(problems))
