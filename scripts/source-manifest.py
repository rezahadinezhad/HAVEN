#!/usr/bin/env python3
"""Hash tracked and reviewable untracked source, excluding volatile evidence and this output file."""
import hashlib
import subprocess
from pathlib import Path
root = Path(__file__).resolve().parent.parent
paths = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root).decode().split("\0")
for name in sorted(set(paths)):
    if not name or name == "SOURCE_MANIFEST.sha256" or name.startswith("docs/evidence/"):
        continue
    path = root / name
    if path.is_symlink():
        raise SystemExit("Refusing a source symlink")
    if path.is_file():
        print(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + name)
