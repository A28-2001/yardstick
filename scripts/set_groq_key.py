"""Safely set GROQ_API_KEY in .env, hidden input, no manual editing.

Prompts for the key with HIDDEN input (nothing echoes, nothing lands in shell
history), sanity-checks the format, and rewrites ONLY the GROQ_API_KEY line.

Run:  python scripts/set_groq_key.py
"""
import getpass
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / ".env"


def main() -> int:
    if not ENV.exists():
        print("No .env file found. Run: cp .env.example .env")
        return 1

    print("Paste your Groq API key from https://console.groq.com/keys (input is hidden).")
    print("Tip: create a NEW key and copy it with the copy button, it is shown only once.")
    key = getpass.getpass("GROQ_API_KEY: ").strip()
    if not key:
        print("Empty, nothing changed.")
        return 1
    if not key.startswith("gsk_"):
        print(f"⚠ Warning: a Groq key normally starts with 'gsk_', but yours starts "
              f"with {key[:4]!r}. Saving anyway, double-check you copied the right value.")

    lines = ENV.read_text().splitlines()
    idx = next((i for i, ln in enumerate(lines) if ln.startswith("GROQ_API_KEY=")), None)
    if idx is None:
        lines.append(f"GROQ_API_KEY={key}")
    else:
        lines[idx] = f"GROQ_API_KEY={key}"
    ENV.write_text("\n".join(lines) + "\n")
    print(f"\n✓ Updated GROQ_API_KEY in .env (length {len(key)}, hidden).")
    print("Now run:  ./.venv/bin/python scripts/verify_setup.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
