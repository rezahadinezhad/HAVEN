#!/usr/bin/env bash
# Inspect only reviewable files; never scan or print local runtime secrets.
set -euo pipefail
cd "$(dirname "$0")/.."
repo_root="$PWD"
python3 scripts/repository-safety.py
scanner="${GITLEAKS_BIN:-gitleaks}"
command -v "$scanner" >/dev/null || { echo 'Install Gitleaks 8.30.1 or set GITLEAKS_BIN.' >&2; exit 1; }
mkdir -p .local
snapshot=$(mktemp -d "$PWD/.local/publish-scan.XXXXXXXX")
trap 'rm -rf "$snapshot"' EXIT
python3 - "$snapshot" <<'PY'
import shutil, subprocess, sys
from pathlib import Path
root=Path.cwd(); target=Path(sys.argv[1])
names=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard']).decode().split('\0')
for name in set(names)-{''}:
    source=root/name
    if source.is_symlink(): raise SystemExit('Refusing symlink')
    if source.is_file():
        destination=target/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination)
PY
(cd "$snapshot" && "$scanner" dir . --config "$repo_root/.gitleaks.toml" --redact --no-banner)
