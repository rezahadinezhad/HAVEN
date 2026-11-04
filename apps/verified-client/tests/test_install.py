"""Exercise the actual independent launcher, including atomic updates and execution refusal."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from test_boundary import ROOT, fingerprint, release


class InstalledLauncher(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "profile"
        self.wheels = self.root / "wheels"
        self.wheels.mkdir()
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "ed25519",
                "-out",
                str(self.root / "private.key"),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(self.root / "private.key"),
                "-pubout",
                "-out",
                str(self.root / "release.pub"),
            ],
            check=True,
            capture_output=True,
        )
        self.bootstrap = ROOT / "apps/verified-client/bootstrap.py"
        self.fingerprint = fingerprint(self.root / "release.pub")
        source = (
            self.bootstrap.read_text()
            .replace(
                "EMBEDDED_VERIFIER = None",
                "EMBEDDED_VERIFIER = "
                + repr(
                    (
                        ROOT / "apps/verified-client/runtime/haven_client/release.py"
                    ).read_text()
                ),
                1,
            )
            .encode()
        )
        runtime = io.BytesIO()
        with zipfile.ZipFile(runtime, "w") as archive:
            archive.writestr("__main__.py", 'print("AUTHENTICATED_RUNTIME")')
        self.payload = {
            "bootstrap.py": source,
            "runtime.pyz": runtime.getvalue(),
            "requirements.lock": b"# no external test dependencies\n",
            "web/index.html": b"trusted client",
        }
        self.first = release(self.root, files=self.payload)

    def tearDown(self):
        self.temp.cleanup()

    def apply(self, bundle, extra=()):
        return subprocess.run(
            [
                sys.executable,
                str(self.bootstrap),
                "--state",
                str(self.state),
                "apply",
                "--bundle",
                str(bundle),
                "--trusted-key",
                str(self.root / "release.pub"),
                "--key-fingerprint",
                self.fingerprint,
                "--wheelhouse",
                str(self.wheels),
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )

    def test_first_trust_is_required_and_launch_verifies_executable(self):
        invalid = self.apply(self.first, ["--key-fingerprint", "0" * 64])
        self.assertNotEqual(invalid.returncode, 0)
        result = self.apply(self.first)
        self.assertEqual(result.returncode, 0, result.stderr)
        run = [
            sys.executable,
            str(self.state / "launcher.py"),
            "--state",
            str(self.state),
            "run",
        ]
        executed = subprocess.run(
            run, capture_output=True, text=True, timeout=15, check=False
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertIn("AUTHENTICATED_RUNTIME", executed.stdout)
        active = json.loads((self.state / "active.json").read_text())
        folder = self.state / "releases" / active["digest"]
        (folder / "runtime.pyz").write_bytes(b"changed local executable")
        rejected = subprocess.run(
            run, capture_output=True, text=True, timeout=15, check=False
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertNotIn("AUTHENTICATED_RUNTIME", rejected.stdout)

    def test_update_floor_survives_failed_and_replayed_updates(self):
        self.assertEqual(self.apply(self.first).returncode, 0)
        newer = release(
            self.root,
            sequence=2,
            files={**self.payload, "web/index.html": b"new trusted client"},
            name="second.haven",
        )
        self.assertEqual(self.apply(newer).returncode, 0)
        before = (self.state / "active.json").read_bytes()
        active = json.loads(before)
        self.assertTrue(
            (self.state / "releases" / active["digest"] / "venv/bin/python").is_file()
        )
        self.assertNotEqual(self.apply(self.first).returncode, 0)
        self.assertEqual((self.state / "active.json").read_bytes(), before)
        tampered = self.root / "tampered.haven"
        with (
            zipfile.ZipFile(newer) as original,
            zipfile.ZipFile(tampered, "w") as output,
        ):
            for item in original.infolist():
                output.writestr(
                    item,
                    b"evil"
                    if item.filename == "web/index.html"
                    else original.read(item),
                )
        self.assertNotEqual(self.apply(tampered).returncode, 0)
        self.assertEqual((self.state / "active.json").read_bytes(), before)

    def test_live_private_browser_blocks_an_update(self):
        self.assertEqual(self.apply(self.first).returncode, 0)
        browser = self.state / "browser"
        browser.mkdir(mode=0o700)
        lock = browser / ".parentlock"
        lock.touch(mode=0o600)
        code = 'import fcntl,sys; f=open(sys.argv[1],"r+"); fcntl.lockf(f,fcntl.LOCK_EX); print("locked",flush=True); sys.stdin.read()'
        child = subprocess.Popen(
            [sys.executable, "-c", code, str(lock)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(child.stdout.readline().strip(), "locked")
            blocked = self.apply(self.first)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("Close the private browser", blocked.stderr)
        finally:
            child.communicate("", timeout=5)


if __name__ == "__main__":
    unittest.main()
