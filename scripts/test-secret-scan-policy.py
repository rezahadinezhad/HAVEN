#!/usr/bin/env python3
"""Prove that public-checksum exceptions do not hide new credential values."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import tomllib

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--scanner", required=True, type=Path)
args = parser.parse_args()
scanner = args.scanner.resolve()
root = Path(__file__).resolve().parent.parent
config = root / ".gitleaks.toml"
policy = tomllib.loads(config.read_text())
entry = next(a for a in policy["allowlists"] if a["description"].startswith("reviewed public source checksums"))
public_hash = entry["regexes"][0].removeprefix("^(?:").removesuffix(")$").split("|")[0]
cases = [
    ("docs/evidence/metadata-realistic-workload-2026-11-02/probe.json", public_hash, 0),
    ("docs/evidence/metadata-realistic-workload-2026-11-02/probe.json", secrets.token_hex(32), 1),
    ("docs/evidence/metadata-realistic-workload-2026-11-02/probe.json", "prefix" + public_hash, 1),
    ("src/probe.json", public_hash, 1),
]
with tempfile.TemporaryDirectory(prefix="haven-scan-policy-") as folder:
    base = Path(folder)
    for index, (name, value, expected) in enumerate(cases):
        case = base / str(index)
        path = case / name
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"core/auth.py": value}) + "\n")
        result = subprocess.run(
            [str(scanner), "dir", ".", "--config", str(config), "--redact=100", "--no-banner"],
            capture_output=True,
            cwd=case,
        )
        assert result.returncode == expected, f"Scanner exception boundary failed for case {index}"
print("PASS: known public checksum accepted; new values, modified values and other paths rejected")
