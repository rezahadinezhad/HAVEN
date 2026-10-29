#!/usr/bin/env python3
"""Create a fresh, committed snapshot without publishing local historical metadata."""
import io
import subprocess
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if subprocess.check_output(["git", "status", "--porcelain"], cwd=root).strip():
    raise SystemExit("Commit and review changes before exporting")
subprocess.run(["python3", str(root / "scripts/repository-safety.py")], check=True, cwd=root)
target = root / ".local/github-ready"
if target.exists():
    raise SystemExit("Export already exists; refusing to overwrite it")
archive = subprocess.check_output(["git", "archive", "HEAD"], cwd=root)
target.mkdir(parents=True)
with tarfile.open(fileobj=io.BytesIO(archive)) as source:
    source.extractall(target, filter="data")
subprocess.run(["git", "init", "-b", "main"], cwd=target, check=True, stdout=subprocess.DEVNULL)
subprocess.run(["git", "add", "."], cwd=target, check=True)
subprocess.run(["git", "-c", "user.name=HAVEN", "-c", "user.email=haven@localhost", "commit", "-m", "Publish reviewed HAVEN source snapshot; release remains BLOCKED"], cwd=target, check=True, stdout=subprocess.DEVNULL)
print("Created fresh GitHub snapshot at " + str(target))
print("Original repository history preserved. No remote configured and nothing pushed.")
