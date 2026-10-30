"""Installer security boundaries; stdlib only, no Docker daemon or network required."""

import hashlib
import importlib.util
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "haven_setup", Path(__file__).parents[1] / "setup.py"
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def plan(**changes):
    value = dict(
        mode="local",
        slug="setup-test",
        name="HAVEN",
        admin="owner",
        ip="127.0.0.1",
        port=18447,
        hostname="localhost",
        api_image="haven-test-api:reviewed",
        web_image="haven-test-web:reviewed",
    )
    value.update(changes)
    return value


class SetupTests(unittest.TestCase):
    def test_exact_hosts_and_no_server_compatibility(self):
        with patch.object(os, "geteuid", return_value=1000):
            setup.validate_plan(plan())
            for changes in [
                dict(ip="0.0.0.0"),
                dict(hostname="*.test"),
                dict(hostname="external.test"),
                dict(slug="../other"),
                dict(port=True),
                dict(port=80),
                dict(admin="a\nother"),
            ]:
                with self.subTest(changes=changes), self.assertRaises(setup.SetupError):
                    setup.validate_plan(plan(**changes))
            server = plan(
                mode="server",
                ip="192.0.2.10",
                hostname="",
                certificate="leaf.crt",
                private_key="leaf.key",
                port=443,
            )
            setup.validate_plan(server)
            with self.assertRaises(setup.SetupError):
                setup.validate_plan(dict(server, local_compatibility=True))
        with (
            patch.object(os, "geteuid", return_value=0),
            self.assertRaises(setup.SetupError),
        ):
            setup.validate_plan(plan())

    def test_dotenv_injection_rejected(self):
        for value in ["value\nOTHER=1", "${HOME}", 'x"', "x\\y", "x#comment", "\x00"]:
            with self.subTest(value=repr(value)), self.assertRaises(setup.SetupError):
                setup.safe_value(value)
        self.assertEqual(setup.safe_value("A private community"), "A private community")

    def test_overlay_never_enables_nonloopback_messaging(self):
        local = setup.render_overlay(plan())
        self.assertIn("127.0.0.1:18447:443", local)
        self.assertEqual(local.count("haven.integration_settings"), 3)
        self.assertNotIn("security_opt", local)
        compatible = setup.render_overlay(plan(local_compatibility=True))
        self.assertEqual(compatible.count("security_opt: !override []"), 7)
        server = setup.render_overlay(plan(mode="server", port=443))
        self.assertIn("0.0.0.0:443:443", server)
        self.assertNotIn("integration_settings", server)
        self.assertNotIn("security_opt", server)

    def test_private_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "secret"
            setup.write_new(target, "protected")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertEqual(setup.read_private(target), "protected")
            with self.assertRaises(FileExistsError):
                setup.write_new(target, "replacement")
            alias = root / "alias"
            alias.symlink_to(target)
            with self.assertRaises(setup.SetupError):
                setup.read_private(alias)
            target.chmod(0o644)
            with self.assertRaises(setup.SetupError):
                setup.read_private(target)

    def test_manifest_tampering_and_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            names = [
                "setup.sh",
                "scripts/setup.py",
                "infrastructure/compose/compose.yml",
                "apps/api/Dockerfile",
                "apps/web/Dockerfile",
            ]
            records = []
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
                records.append(
                    hashlib.sha256(path.read_bytes()).hexdigest() + "  " + name
                )
            manifest = root / "SOURCE_MANIFEST.sha256"
            manifest.write_text("\n".join(records))
            setup.verify_manifest(root)
            (root / names[0]).write_text("tampered")
            with self.assertRaises(setup.SetupError):
                setup.verify_manifest(root)
            manifest.write_text("")
            with self.assertRaises(setup.SetupError):
                setup.verify_manifest(root)

    def test_collision_rejected_before_recording_ownership(self):
        class Collision:
            def run(self, command):
                return subprocess.CompletedProcess(command, 0, "existing-object\n")

        with self.assertRaises(setup.SetupError):
            setup.check_namespace(plan(), Collision())
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(setup, "ROOT", Path(temp)),
            patch.object(setup, "verify_manifest", return_value="a" * 64),
            patch.object(setup, "preflight"),
            patch.object(
                setup, "check_namespace", side_effect=setup.SetupError("collision")
            ),
        ):
            with self.assertRaises(setup.SetupError):
                setup.install(plan(), interactive=False)
            directory = Path(temp) / ".local/setup/setup-test"
            for name in ("state.json", "config.env", "admin-credentials.json"):
                self.assertFalse((directory / name).exists())

    def test_occupied_port_rejected(self):
        with socket.socket() as listener, tempfile.TemporaryDirectory() as temp:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with self.assertRaises(setup.SetupError):
                setup.check_port(
                    plan(port=listener.getsockname()[1]), Path(temp), None, resume=False
                )

    def test_stale_or_unowned_resume_preserves_secrets(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(setup, "ROOT", Path(temp)),
            patch.object(setup, "verify_manifest", return_value="a" * 64),
            patch.object(os, "geteuid", return_value=1000),
        ):
            directory = Path(temp) / ".local/setup/setup-test"
            setup.secure_dir(directory)
            setup.write_new(directory / "config.env", "original secret")
            for source, owned in [("b" * 64, True), ("a" * 64, False)]:
                setup.save_state(
                    directory,
                    dict(source_hash=source, plan=plan(), namespace_checked=owned),
                )
                with self.assertRaises(setup.SetupError):
                    setup.install(
                        {"slug": "setup-test"}, resume=True, interactive=False
                    )
                self.assertEqual(
                    (directory / "config.env").read_text(), "original secret"
                )

    def test_log_redacts_credentials_and_stdin_not_command(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = setup.Runner(Path(temp), ["synthetic-private-value"])
            runner.run(
                ["python3", "-c", "import sys; print(sys.stdin.read())"],
                input_text="synthetic-private-value",
            )
            log = runner.log.read_text()
            self.assertNotIn("synthetic-private-value", log)
            self.assertIn("[redacted]", log)


@unittest.skipUnless(setup.shutil.which("openssl"), "OpenSSL required")
class TLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.runner = setup.Runner(cls.directory)
        cls.roots = setup.prepare_tls(plan(), cls.directory, cls.runner)
        cls.bundle = cls.directory / "tls-bundle"

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_chain_ip_hostname_key_and_resume(self):
        setup.validate_tls(plan(), self.bundle, self.runner, self.roots)
        original = (self.bundle / "tls/leaf.key").read_bytes()
        self.assertEqual(
            setup.prepare_tls(plan(), self.directory, self.runner), self.roots
        )
        self.assertEqual((self.bundle / "tls/leaf.key").read_bytes(), original)
        self.assertFalse((self.bundle / "tls/root.key").exists())
        self.assertTrue((self.bundle / "issuer/root.key").exists())

    def test_reject_wrong_ip_hostname_untrusted_and_near_expiry(self):
        for changes, roots, minimum in [
            (dict(ip="127.0.0.2"), self.roots, 172800),
            (dict(hostname="other.test"), self.roots, 172800),
            ({}, None, 172800),
            ({}, self.roots, 4 * 86400),
        ]:
            with (
                self.subTest(changes=changes, minimum=minimum),
                self.assertRaises(setup.SetupError),
            ):
                setup.validate_tls(
                    plan(**changes),
                    self.bundle,
                    self.runner,
                    roots,
                    minimum_seconds=minimum,
                )

    def test_reject_ca_leaf_and_mismatched_key(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            setup.secure_dir(target / "tls")
            for name in ("leaf.key", "leaf.crt"):
                setup.shutil.copyfile(self.bundle / "tls" / name, target / "tls" / name)
            (target / "tls/leaf.key").chmod(0o600)
            setup.shutil.copyfile(
                self.bundle / "issuer/root.key", target / "tls/leaf.key"
            )
            with self.assertRaises(setup.SetupError):
                setup.validate_tls(plan(), target, self.runner, self.roots)
            setup.shutil.copyfile(
                self.bundle / "issuer/root.crt", target / "tls/leaf.crt"
            )
            with self.assertRaises(setup.SetupError):
                setup.validate_tls(plan(), target, self.runner, self.roots)

    def test_interrupted_tls_generation_never_publishes_partial_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with patch.object(
                setup, "create_tls", side_effect=setup.SetupError("interrupted")
            ):
                with self.assertRaises(setup.SetupError):
                    setup.prepare_tls(plan(), directory, self.runner)
            self.assertFalse((directory / "tls-bundle").exists())
            self.assertFalse(list(directory.glob(".tls-preparing-*")))


if __name__ == "__main__":
    unittest.main()
