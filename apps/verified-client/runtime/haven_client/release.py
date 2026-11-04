"""Bounded Ed25519 release verification. This module uses only the standard library and OpenSSL."""

import hashlib
import json
import re
import stat
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

MAX_RELEASE = 80 * 1024 * 1024
MAX_CONTENT = 64 * 1024 * 1024
MAX_MANIFEST = 128 * 1024
DOMAIN = "haven/verified-client-release/v1"


class InvalidRelease(ValueError):
    pass


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidRelease("Duplicate manifest field")
        result[key] = value
    return result


def fingerprint(public_key):
    if not Path(public_key).is_file() or Path(public_key).stat().st_size > 4096:
        raise InvalidRelease("Invalid trusted release public key")
    result = subprocess.run(
        ["openssl", "pkey", "-pubin", "-in", str(public_key), "-outform", "DER"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    if (
        result.returncode
        or len(result.stdout) != 44
        or not result.stdout.startswith(bytes.fromhex("302a300506032b6570032100"))
    ):
        raise InvalidRelease("Invalid trusted release public key")
    return hashlib.sha256(result.stdout).hexdigest()


def safe_path(name):
    if (
        not isinstance(name, str)
        or len(name) > 240
        or "\\" in name
        or "%" in name
        or not re.fullmatch(r"[A-Za-z0-9_./-]+", name)
    ):
        return False
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and name == str(path)
        and all(p not in ("", ".", "..") for p in path.parts)
    )


def verify(bundle, public_key, minimum=1, previous_digest=None):
    bundle, public_key = Path(bundle), Path(public_key)
    if (
        bundle.is_symlink()
        or not bundle.is_file()
        or bundle.stat().st_size > MAX_RELEASE
    ):
        raise InvalidRelease("Missing, unsafe or oversized client release")
    fingerprint(public_key)
    # Bound central-directory parsing before ZipFile allocates entry objects.
    with bundle.open("rb") as stream:
        if bundle.stat().st_size < 22:
            raise InvalidRelease("Truncated client release")
        stream.seek(-22, 2)
        (
            marker,
            disk,
            central_disk,
            count_disk,
            count,
            central_bytes,
            central_offset,
            comment,
        ) = struct.unpack("<4s4H2LH", stream.read(22))
    if (
        marker != b"PK\x05\x06"
        or disk
        or central_disk
        or count_disk != count
        or count > 256
        or comment
        or central_bytes > MAX_MANIFEST
        or central_offset + central_bytes + 22 != bundle.stat().st_size
    ):
        raise InvalidRelease("Unsupported or oversized release directory")
    try:
        with zipfile.ZipFile(bundle) as archive:
            entries = archive.infolist()
            names = [x.filename for x in entries]
            if len(names) > 256 or len(names) != len(set(names)):
                raise InvalidRelease("Duplicate or excessive release entries")
            if any(
                not safe_path(x.filename)
                or x.is_dir()
                or stat.S_ISLNK(x.external_attr >> 16)
                or x.flag_bits & 1
                or x.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                for x in entries
            ):
                raise InvalidRelease("Unsafe release entry")
            sizes = {x.filename: x.file_size for x in entries}
            if (
                sum(sizes.values()) > MAX_CONTENT
                or sizes.get("manifest.json", MAX_MANIFEST + 1) > MAX_MANIFEST
                or sizes.get("signature.ed25519") != 64
            ):
                raise InvalidRelease("Release size limit exceeded")
            wire, signature = (
                archive.read("manifest.json"),
                archive.read("signature.ed25519"),
            )
            with tempfile.TemporaryDirectory(prefix="haven-release-") as temp:
                root = Path(temp)
                (root / "manifest").write_bytes(wire)
                (root / "signature").write_bytes(signature)
                checked = subprocess.run(
                    [
                        "openssl",
                        "pkeyutl",
                        "-verify",
                        "-rawin",
                        "-pubin",
                        "-inkey",
                        str(public_key),
                        "-in",
                        str(root / "manifest"),
                        "-sigfile",
                        str(root / "signature"),
                    ],
                    capture_output=True,
                    check=False,
                    timeout=10,
                )
            if checked.returncode:
                raise InvalidRelease("Client release signature rejected")
            manifest = json.loads(wire, object_pairs_hook=unique_object)
            if (
                not isinstance(manifest, dict)
                or set(manifest) != {"domain", "sequence", "source", "files"}
                or manifest["domain"] != DOMAIN
            ):
                raise InvalidRelease("Unsupported client release")
            sequence = manifest["sequence"]
            if (
                type(sequence) is not int
                or not minimum <= sequence <= 2147483647
                or not re.fullmatch(r"[0-9a-f]{40}", manifest["source"])
            ):
                raise InvalidRelease("Release rollback or invalid version")
            digest = hashlib.sha256(wire).hexdigest()
            if (
                sequence == minimum
                and previous_digest is not None
                and previous_digest != digest
            ):
                raise InvalidRelease("Conflicting release at the same sequence")
            files = manifest["files"]
            if (
                not isinstance(files, dict)
                or not {
                    "runtime.pyz",
                    "bootstrap.py",
                    "requirements.lock",
                    "web/index.html",
                }
                <= files.keys()
                or set(names) != set(files) | {"manifest.json", "signature.ed25519"}
            ):
                raise InvalidRelease("Incomplete or unexpected client payload")
            payload = {}
            for name, record in files.items():
                if (
                    not safe_path(name)
                    or not (
                        name in {"runtime.pyz", "bootstrap.py", "requirements.lock"}
                        or name.startswith("web/")
                    )
                    or not isinstance(record, dict)
                    or set(record) != {"bytes", "sha256"}
                    or type(record["bytes"]) is not int
                    or record["bytes"] != sizes[name]
                    or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
                ):
                    raise InvalidRelease("Invalid release manifest entry")
                body = archive.read(name)
                if hashlib.sha256(body).hexdigest() != record["sha256"]:
                    raise InvalidRelease("Client asset digest rejected")
                payload[name] = body
            return manifest, digest, payload
    except (
        KeyError,
        TypeError,
        zipfile.BadZipFile,
        UnicodeError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise InvalidRelease("Malformed client release") from error
