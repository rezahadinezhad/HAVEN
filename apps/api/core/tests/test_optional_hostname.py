"""Exact opt-in hostname does not relax the required literal-IP route."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("hosts", "origins", "optional", "integration", "accepted"),
    [
        ("127.0.0.1", "https://127.0.0.1:8445", "", True, True),
        ("127.0.0.1,localhost", "https://127.0.0.1:8445,https://localhost:8446", "localhost", True, True),
        ("127.0.0.1,localhost", "https://127.0.0.1:8445,https://localhost:8446", "", True, False),
        ("127.0.0.1,localhost", "https://127.0.0.1:8445", "localhost", True, False),
        ("localhost", "https://localhost:8446", "localhost", True, False),
        (
            "127.0.0.1,*.example.org",
            "https://127.0.0.1:8445,https://*.example.org",
            "*.example.org",
            False,
            False,
        ),
        ("127.0.0.1,example.org", "https://127.0.0.1:8445,http://example.org", "example.org", False, False),
        (
            "127.0.0.1,example.org",
            "https://127.0.0.1:8445,https://example.org:0",
            "example.org",
            False,
            False,
        ),
        ("127.0.0.1,example.org", "https://127.0.0.1:8445,https://example.org", "example.org", True, False),
    ],
)
def test_exact_optional_hostname(hosts, origins, optional, integration, accepted):
    env = {
        **os.environ,
        "HAVEN_SECRET_KEY": "test-only-" + "x" * 64,
        "HAVEN_HOSTS": hosts,
        "HAVEN_ORIGINS": origins,
        "HAVEN_OPTIONAL_HOSTNAME": optional,
    }
    module = "haven.integration_settings" if integration else "haven.settings"
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert (result.returncode == 0) is accepted


def test_env_validator_fails_closed_under_optimized_python(tmp_path):
    tls = tmp_path / "tls"
    tls.mkdir()
    (tls / "leaf.crt").write_text("test only")
    (tls / "leaf.key").write_text("test only")
    env_file = tmp_path / ".env"
    lines = [
        f"HAVEN_SECRET_KEY={'s' * 64}",
        f"POSTGRES_PASSWORD={'a' * 40}",
        f"HAVEN_DB_MIGRATION_PASSWORD={'b' * 40}",
        f"HAVEN_DB_RUNTIME_PASSWORD={'c' * 40}",
        "HAVEN_HOSTS=127.0.0.1,localhost",
        "HAVEN_ORIGINS=https://127.0.0.1,https://localhost",
        "HAVEN_OPTIONAL_HOSTNAME=localhost",
        f"HAVEN_TLS_DIR={tls}",
    ]
    script = Path(__file__).resolve().parents[4] / "scripts/validate-env.py"
    env_file.write_text("\n".join(lines) + "\n")
    env_file.chmod(0o600)

    def check():
        return subprocess.run(
            [sys.executable, "-O", str(script)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    assert check().returncode == 0
    env_file.write_text("\n".join(lines[:-2] + ["HAVEN_OPTIONAL_HOSTNAME=*.example.org", lines[-1]]) + "\n")
    assert check().returncode != 0
