#!/usr/bin/env python3
"""Sign a complete executable client release with an independently held Ed25519 key."""

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--development",
    action="store_true",
    help="Allow an uncommitted development build; never publish it as a reviewed release",
)
parser.add_argument("--web", type=Path, required=True)
parser.add_argument("--signing-key", type=Path, required=True)
parser.add_argument("--sequence", type=int, required=True)
parser.add_argument("--output", type=Path, required=True)
options = parser.parse_args()
if options.signing_key.stat().st_mode & 0o077:
    parser.error("Release signing key must be protected mode 0600")
if options.output.exists():
    parser.error("Never overwrite a published release")
if not 1 <= options.sequence <= 2147483647:
    parser.error("Invalid release sequence")
if (
    not options.development
    and subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip()
):
    parser.error("Commit the reviewed source before signing a production release")
if not options.development:
    marker = json.loads((options.web / ".haven-client-build").read_text())
    inputs = []
    for base in ("apps/web/src", "apps/web/public", "apps/verified-client/web"):
        inputs.extend(
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / base).rglob("*")
            if p.is_file()
        )
    inputs.extend(
        (
            "apps/web/package.json",
            "apps/web/package-lock.json",
            "apps/web/tsconfig.json",
            "scripts/build-verified-client.mjs",
        )
    )
    source_hash = hashlib.sha256()
    for name in sorted(inputs):
        source_hash.update((name + "\0").encode())
        source_hash.update((ROOT / name).read_bytes())
    if marker != {
        "domain": "haven/client-build-inputs/v1",
        "sha256": source_hash.hexdigest(),
    }:
        parser.error("Client build is stale relative to reviewed source")
    if any(
        "qa-client" in p.name or "pof" in p.name.lower() or p.suffix == ".map"
        for p in options.web.rglob("*")
    ):
        parser.error("Production releases cannot contain test harnesses or source maps")
# Validate key type before recording a publisher sequence.
public = subprocess.check_output(
    ["openssl", "pkey", "-in", str(options.signing_key), "-pubout", "-outform", "DER"]
)
if len(public) != 44 or not public.startswith(
    bytes.fromhex("302a300506032b6570032100")
):
    parser.error("Publisher key must be Ed25519")
source = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
).strip()
verifier = (ROOT / "apps/verified-client/runtime/haven_client/release.py").read_text()
bootstrap = (
    (ROOT / "apps/verified-client/bootstrap.py")
    .read_text()
    .replace("EMBEDDED_VERIFIER = None", "EMBEDDED_VERIFIER = " + repr(verifier), 1)
)
with tempfile.TemporaryDirectory(prefix="haven-client-build-") as tmp:
    runtime = Path(tmp) / "runtime.pyz"
    with zipfile.ZipFile(runtime, "w", compression=zipfile.ZIP_DEFLATED) as executable:
        for p in sorted((ROOT / "apps/verified-client/runtime").rglob("*.py")):
            item = zipfile.ZipInfo(
                p.relative_to(ROOT / "apps/verified-client/runtime").as_posix(),
                date_time=(2020, 1, 1, 0, 0, 0),
            )
            item.external_attr = 0o100600 << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            executable.writestr(item, p.read_bytes())
    files = {
        "bootstrap.py": bootstrap.encode(),
        "runtime.pyz": runtime.read_bytes(),
        "requirements.lock": (
            ROOT / "apps/verified-client/requirements.lock"
        ).read_bytes(),
    }
    for p in options.web.rglob("*"):
        if p.is_symlink():
            parser.error("Client source cannot contain symlinks")
        if p.is_file() and p.name != ".haven-client-build":
            files["web/" + p.relative_to(options.web).as_posix()] = p.read_bytes()
    manifest = {
        "domain": "haven/verified-client-release/v1",
        "sequence": options.sequence,
        "source": source,
        "files": {
            name: {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            for name, body in sorted(files.items())
        },
    }
    wire = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ledger_path = options.signing_key.with_name(
        options.signing_key.name + ".releases.json"
    )
    ledger_lock = ledger_path.with_suffix(".lock")
    lock = ledger_lock.open("a")
    ledger_lock.chmod(0o600)
    fcntl.flock(lock, fcntl.LOCK_EX)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    digest = hashlib.sha256(wire).hexdigest()
    prior = ledger.get(str(options.sequence))
    if (prior and prior != digest) or (
        ledger and options.sequence < max(map(int, ledger))
    ):
        parser.error(
            "Publisher sequence rollback or conflicting signed release refused"
        )
    ledger[str(options.sequence)] = digest
    descriptor, name = tempfile.mkstemp(
        dir=ledger_path.parent, prefix=".release-index-"
    )
    with os.fdopen(descriptor, "w") as stream:
        json.dump(ledger, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(name, ledger_path)
    descriptor = os.open(ledger_path.parent, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(descriptor)
    os.close(descriptor)
    (Path(tmp) / "manifest").write_bytes(wire)
    subprocess.run(
        [
            "openssl",
            "pkeyutl",
            "-sign",
            "-rawin",
            "-inkey",
            str(options.signing_key),
            "-in",
            str(Path(tmp) / "manifest"),
            "-out",
            str(Path(tmp) / "signature"),
        ],
        check=True,
    )
    options.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        options.output, "x", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr("manifest.json", wire)
        archive.writestr("signature.ed25519", (Path(tmp) / "signature").read_bytes())
        for name, body in sorted(files.items()):
            archive.writestr(name, body)
    print(
        "Signed client sequence",
        options.sequence,
        "manifest",
        hashlib.sha256(wire).hexdigest(),
    )
