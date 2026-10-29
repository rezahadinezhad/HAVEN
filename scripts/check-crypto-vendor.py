#!/usr/bin/env python3
"""Verify the checked-in upstream provider source and minimal compatibility patch."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "packages/crypto-core/vendor"
manifest = json.loads((root / "UPSTREAM.json").read_text())
expected = set(manifest["files"])
actual = {
    str(p.relative_to(root))
    for name in ("openmls_rust_crypto", "basic_credential")
    for p in (root / name).rglob("*") if p.is_file()
}
if actual != expected:
    raise SystemExit("Unexpected or missing provider source file")
for name, hashes in manifest["files"].items():
    path = root / name
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != hashes["local_sha256"]:
        raise SystemExit("Provider source integrity mismatch: " + name)
    if name.endswith(".rs") and name != "basic_credential/src/lib.rs":
        if hashes["local_sha256"] != hashes["upstream_sha256"]:
            raise SystemExit("Cryptographic provider source differs from upstream")
print("PASS: pinned upstream provider source hashes; only recorded credential storage compatibility changes")
