"""Trusted immutable image launcher: verify the signed runtime before executing it."""

import hashlib
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path("/app")
spec = importlib.util.spec_from_file_location("release", ROOT / "release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
manifest, digest, payload = release.verify(
    ROOT / "release.haven",
    ROOT / "release.pub",
    int((ROOT / "minimum-sequence").read_text()),
)
if payload["requirements.lock"] != (ROOT / "requirements.lock").read_bytes():
    raise ValueError("Image dependencies differ from the signed release")
executable = ROOT / "runtime.pyz"
if sys.argv[1:] == ["--prepare-image"]:
    executable.write_bytes(payload["runtime.pyz"])
    print(
        "Authenticated image client sequence", manifest["sequence"], "manifest", digest
    )
else:
    if (
        hashlib.sha256(executable.read_bytes()).digest()
        != hashlib.sha256(payload["runtime.pyz"]).digest()
    ):
        raise ValueError("Image executable differs from signed release")
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-I",
            str(executable),
            "--bundle",
            str(ROOT / "release.haven"),
            "--trusted-key",
            str(ROOT / "release.pub"),
            "serve",
            "--minimum-sequence",
            str(manifest["sequence"]),
            *sys.argv[1:],
        ],
    )
