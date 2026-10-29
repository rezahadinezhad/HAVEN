#!/usr/bin/env python3
"""Check publishable files without printing their potentially secret contents."""
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
names = subprocess.check_output(
    ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
).decode().split("\0")
errors = []
for name in sorted(set(names) - {""}):
    path = root / name
    parts = Path(name).parts
    if (
        any(part in {".local", ".git", "node_modules", ".venv", ".next", "__pycache__"} for part in parts)
        or (path.name.startswith(".env") and path.name != ".env.example")
        or path.suffix.lower() in {".key", ".p12", ".pfx", ".sqlite3", ".sqlite", ".db", ".pem", ".jks", ".sql", ".dump", ".backup", ".log"}
        or path.name in {"id_rsa", "id_ed25519", "credentials.json"}
        or path.is_symlink()
    ):
        errors.append(name + ": private/generated path or symlink")
    if not path.is_file():
        continue
    if name.startswith("docs/evidence/") and path.suffix == ".json":
        try:
            value = json.loads(path.read_text())
        except (ValueError, UnicodeError):
            errors.append(name + ": invalid JSON evidence")
            continue

        def check(item):
            if isinstance(item, dict):
                for key, val in item.items():
                    if key == "env" and isinstance(val, dict) and set(val) - {"PATH", "HOME", "LANG", "LD_LIBRARY_PATH"}:
                        errors.append(name + ": unfiltered process environment")
                    check(val)
            elif isinstance(item, list):
                for val in item:
                    check(val)

        check(value)
if errors:
    raise SystemExit("\n".join(errors))
print("PASS: publishable file paths and evidence environment policy")
