"""Safely set the Supabase DB password in .env, no manual editing.

Prompts for the password with HIDDEN input (nothing echoes, nothing lands in
shell history), URL-encodes it to handle any special characters, and rewrites
ONLY the password portion of the DATABASE_URL line in .env. Everything else in
.env is left untouched.

Run:  python scripts/set_db_password.py
"""
import getpass
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

ENV = Path(__file__).resolve().parents[1] / ".env"


def main() -> int:
    if not ENV.exists():
        print("No .env file found. Run: cp .env.example .env")
        return 1

    lines = ENV.read_text().splitlines()
    idx = next((i for i, ln in enumerate(lines) if ln.startswith("DATABASE_URL=")), None)
    if idx is None:
        print("No DATABASE_URL= line in .env. Add one (copy the URI from Supabase → Connect).")
        return 1

    url = lines[idx][len("DATABASE_URL="):].strip()
    parts = urlsplit(url)
    if not parts.username or not parts.hostname:
        print("DATABASE_URL doesn't look like a full URI. Re-copy it from Supabase → Connect → URI.")
        return 1

    print(f"Current connection: user={parts.username}  host={parts.hostname}  port={parts.port}")
    print("Paste the database password from Supabase (input is hidden), then press Enter.")
    pw = getpass.getpass("DB password: ").strip()
    if not pw:
        print("Empty password, nothing changed.")
        return 1

    # Rebuild netloc as user:ENCODED_PW@host:port  (encode pw so special chars are URL-safe)
    userinfo = f"{parts.username}:{quote(pw, safe='')}"
    host = parts.hostname + (f":{parts.port}" if parts.port else "")
    new_netloc = f"{userinfo}@{host}"
    new_url = urlunsplit((parts.scheme, new_netloc, parts.path, parts.query, parts.fragment))

    lines[idx] = f"DATABASE_URL={new_url}"
    ENV.write_text("\n".join(lines) + "\n")
    print(f"\n✓ Updated DATABASE_URL in .env (password length {len(pw)} written, encoded, hidden).")
    print("Now run:  ./.venv/bin/python scripts/verify_setup.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
