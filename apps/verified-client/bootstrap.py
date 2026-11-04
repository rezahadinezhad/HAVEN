#!/usr/bin/env python3
"""Trusted installed launcher. Never downloads or runs code from the messaging origin."""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

# Initial checkout invocation and the independently installed single-file launcher
# share the same bounded verifier; the latter embeds it at build time.
EMBEDDED_VERIFIER = None
if EMBEDDED_VERIFIER is None:
    source = Path(__file__).parent / "runtime/haven_client/release.py"
    spec = importlib.util.spec_from_file_location("release", source)
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
else:
    import types

    release = types.ModuleType("release")
    exec(EMBEDDED_VERIFIER, release.__dict__)  # noqa: S102 — publisher embeds this trusted verifier, never API data


def atomic(path, data):
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        Path(name).unlink(missing_ok=True)


def protected_state(path):
    if path.is_symlink():
        raise ValueError("Client state cannot be a symlink")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.stat().st_mode & 0o077:
        raise ValueError("Client state must be mode 0700")


def install(state, bundle, key, expected, wheelhouse):
    protected_state(state)
    trusted = state / "release.pub"
    if trusted.exists():
        if key and release.fingerprint(key) != release.fingerprint(trusted):
            raise ValueError("Installed release key cannot change through an update")
        key = trusted
    elif not key or not expected or release.fingerprint(key) != expected:
        raise ValueError(
            "Initial installation requires an independently verified public-key fingerprint"
        )
    prior = (
        json.loads((state / "active.json").read_text())
        if (state / "active.json").exists()
        else None
    )
    manifest, digest, payload = release.verify(
        bundle,
        key,
        prior["sequence"] if prior else 1,
        prior["digest"] if prior else None,
    )
    destination = state / "releases" / digest
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    if not destination.exists():
        stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=destination.parent))
        try:
            for name, body in payload.items():
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic(target, body)
            atomic(stage / "release.haven", Path(bundle).read_bytes())
            release.verify(
                stage / "release.haven",
                key,
                prior["sequence"] if prior else 1,
                prior["digest"] if prior else None,
            )
            os.replace(stage, destination)
            descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    if not trusted.exists():
        atomic(trusted, Path(key).read_bytes())
    environment = destination / "venv"
    if not environment.exists():
        venv.EnvBuilder(with_pip=True).create(environment)
    # Dependencies are hash-locked and installed exclusively from operator-supplied wheels.
    subprocess.run(
        [
            str(environment / "bin/python"),
            "-I",
            "-m",
            "pip",
            "--isolated",
            "install",
            "--no-index",
            "--find-links",
            str(Path(wheelhouse).resolve()),
            "--require-hashes",
            "-r",
            str(destination / "requirements.lock"),
        ],
        check=True,
        timeout=180,
        stdout=subprocess.DEVNULL,
    )
    # The existing verifier authenticates the replacement launcher under the
    # pinned root; launcher fixes must be deliverable without changing that root.
    atomic(state / "launcher.py", payload["bootstrap.py"])
    if not (state / "haven-client").exists():
        command = (
            "#!/bin/sh\nexec "
            + shlex.quote(sys._base_executable)
            + " -I "
            + shlex.quote(str(state / "launcher.py"))
            + " --state "
            + shlex.quote(str(state))
            + ' "$@"\n'
        )
        atomic(state / "haven-client", command.encode())
        (state / "haven-client").chmod(0o700)
    atomic(
        state / "active.json",
        release.canonical({"sequence": manifest["sequence"], "digest": digest}),
    )
    print("Verified client release installed:", manifest["sequence"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    commands = parser.add_subparsers(dest="action", required=True)
    apply = commands.add_parser("apply")
    apply.add_argument("--bundle", type=Path, required=True)
    apply.add_argument("--trusted-key", type=Path)
    apply.add_argument("--key-fingerprint")
    apply.add_argument("--wheelhouse", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    state = options.state.expanduser()
    if state.is_symlink():
        raise ValueError("Client state cannot be a symlink")
    state = state.resolve()
    protected_state(state)
    with (state / "client.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error(
                "Stop the installed client before applying an update or starting another instance"
            )
        if options.action == "apply":
            # Hold Firefox's profile locks throughout the version switch. A
            # running old renderer must never acquire a newer worker mid-session.
            browser_locks = []
            try:
                for name in (".parentlock", "parent.lock"):
                    path = state / "browser" / name
                    if path.exists():
                        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
                        try:
                            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except OSError:
                            os.close(fd)
                            raise ValueError(
                                "Close the private browser before updating"
                            ) from None
                        browser_locks.append(fd)
                install(
                    state,
                    options.bundle,
                    options.trusted_key,
                    options.key_fingerprint,
                    options.wheelhouse,
                )
            finally:
                for fd in browser_locks:
                    os.close(fd)
            return
        active = json.loads((state / "active.json").read_text())
        folder = state / "releases" / active["digest"]
        if (
            not isinstance(active["digest"], str)
            or len(active["digest"]) != 64
            or any(c not in "0123456789abcdef" for c in active["digest"])
        ):
            raise ValueError("Invalid active client state")
        # Verify the executable on disk too; the archive is the immutable authority.
        _, _, payload = release.verify(
            folder / "release.haven",
            state / "release.pub",
            active["sequence"],
            active["digest"],
        )
        if (
            hashlib.sha256((folder / "runtime.pyz").read_bytes()).digest()
            != hashlib.sha256(payload["runtime.pyz"]).digest()
        ):
            raise ValueError("Installed runtime changed")
        args = options.arguments
        if args and args[0] == "--":
            args = args[1:]
        process = subprocess.Popen(
            [
                str(folder / "venv/bin/python"),
                "-I",
                str(folder / "runtime.pyz"),
                "--state",
                str(state),
                "--bundle",
                str(folder / "release.haven"),
                "--trusted-key",
                str(state / "release.pub"),
                *args,
            ],
            # Retain the same kernel lock if the parent is terminated abruptly.
            pass_fds=(lock.fileno(),),
        )

        def relay(number, _frame):
            process.send_signal(number)

        previous = {
            number: signal.signal(number, relay)
            for number in (signal.SIGTERM, signal.SIGINT)
        }
        try:
            status = process.wait()
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        if status:
            raise subprocess.CalledProcessError(status, process.args)


if __name__ == "__main__":
    os.umask(0o077)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print("Client operation rejected:", str(error), file=sys.stderr)
        sys.exit(1)
