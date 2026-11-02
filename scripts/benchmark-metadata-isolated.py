#!/usr/bin/env python3
"""Own disposable PostgreSQL/Redis/Nginx, actual limits, synthetic native MLS load.

No existing container, DB, backup, or application is changed. Needs Docker and
local test CA from scripts/dev-cert.sh. Output is aggregate JSON; private logs,
fixtures and encrypted native checkpoints remain under .local (0700).
"""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parent.parent
PG = "postgres:16.14-bookworm@sha256:64154d0babcb1741988719e703419af0382b19953706149f9872fbd0f438efa8"
REDIS = "redis:7.4.6-alpine@sha256:3b73847e72874be07e6657b129a94761662b79bc0f679273757d4218573b2a98"
NGINX = "nginx:1.28.3-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236"
parser = argparse.ArgumentParser()
parser.add_argument("--revision", default="current")
parser.add_argument("--resilience", action="store_true")
parser.add_argument("--seconds", type=int, default=120)
parser.add_argument("--rate", type=float, default=20)
parser.add_argument("--rekey-every", type=int, default=100)
parser.add_argument(
    "--crypto-workers",
    type=int,
    default=10,
    help="Independent native processes, 1–50; use 1 for the serialized control",
)
args = parser.parse_args()
source_manifest_sha256 = hashlib.sha256(
    subprocess.check_output(
        [sys.executable, str(ROOT / "scripts/source-manifest.py")], cwd=ROOT
    )
).hexdigest()
if (
    not 1 <= args.seconds <= 7200
    or not 0 < args.rate <= 20
    or not 1 <= args.rekey_every <= 1000
    or not 1 <= args.crypto_workers <= 50
):
    raise SystemExit(
        "Bounded workload required (1–7200 seconds, up to 20 messages/second)"
    )
os.umask(0o077)
for port in (55434, 56381, 8115, 8452, 8454):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"Isolated port {port} unavailable") from None
folder = ROOT / ".local" / ("metadata-load-" + secrets.token_hex(6))
folder.mkdir(mode=0o700)
work = ROOT / "apps/api"
if args.revision != "current":
    archive = subprocess.check_output(
        ["git", "archive", args.revision, "apps/api"], cwd=ROOT
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(folder / "source", filter="data")
    work = folder / "source/apps/api"
secret = secrets.token_urlsafe(64)
password = secrets.token_urlsafe(48)
environment = {
    **os.environ,
    "HAVEN_SECRET_KEY": secret,
    "POSTGRES_USER": "haven_synthetic",
    "POSTGRES_DB": "haven_synthetic",
    "POSTGRES_PASSWORD": password,
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "55434",
    "REDIS_URL": "redis://127.0.0.1:56381/0",
    "HAVEN_HOSTS": "127.0.0.1",
    "HAVEN_ORIGINS": "https://127.0.0.1:8454",
    "HAVEN_OPTIONAL_HOSTNAME": "",
    "DJANGO_SETTINGS_MODULE": "haven.integration_settings",
    "MLS_PUBLIC_VERIFIER": str(
        ROOT / "packages/crypto-core/bin/haven-public-verify-x86_64-linux"
    ),
    "HAVEN_ISOLATED_LOAD": "synthetic-only",
    "HAVEN_LOAD_PRIVATE": str(folder),
    "HAVEN_LOAD_API": str(work),
    "HAVEN_LOAD_CRYPTO_WORKERS": str(args.crypto_workers),
    "HAVEN_LOAD_SECONDS": str(args.seconds),
    "HAVEN_LOAD_RATE": str(args.rate),
    "HAVEN_LOAD_REKEY_EVERY": str(args.rekey_every),
    "HAVEN_LOAD_RECONNECT": "1" if args.resilience else "0",
}
pg_env = folder / "postgres.env"
pg_env.write_text(
    f"POSTGRES_USER=haven_synthetic\nPOSTGRES_DB=haven_synthetic\nPOSTGRES_PASSWORD={password}\nPOSTGRES_INITDB_ARGS=--data-checksums\n"
)
nginx = (ROOT / "infrastructure/nginx/nginx.conf").read_text()
nginx = (
    nginx.replace("server api:8100 resolve;", "server 127.0.0.1:8115;")
    .replace("server web:3100 resolve;", "server 127.0.0.1:3100;")
    .replace("listen 443 ssl;", "listen 127.0.0.1:8452 ssl;")
)
(folder / "nginx.conf").write_text(nginx)
name = "haven-synthetic-load-" + secrets.token_hex(5)
containers, children = [], []
log = (folder / "private.log").open("w")
python = ROOT / "apps/api/.venv/bin/python"
# Private settings/ASGI adapters add synthetic instrumentation to either API
# revision. Production application/settings files are never edited or exposed.
(folder / "metadata_profile_settings.py").write_text(
    "from haven.integration_settings import *\n"
    'MIDDLEWARE = ["metadata_load_profile.RequestProfiler", *MIDDLEWARE]\n'
)
(folder / "metadata_profile_asgi.py").write_text(
    "from metadata_load_profile import ASGIProfiler\n"
    "from haven.asgi import application as original\n"
    "application = ASGIProfiler(original)\n"
)
api_environment = {
    **environment,
    "DJANGO_SETTINGS_MODULE": "metadata_profile_settings",
    "PYTHONPATH": os.pathsep.join((str(folder), str(ROOT / "scripts"), str(work))),
}
source_files = [
    *[
        (work / name)
        for name in subprocess.check_output(
            [
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "apps/api",
            ],
            cwd=ROOT,
            text=True,
        ).splitlines()
        if name.endswith(".py") and "/tests/" not in name
        for name in [name.removeprefix("apps/api/")]
    ],
    *[
        ROOT / name
        for name in (
            "scripts/benchmark-metadata-isolated.py",
            "scripts/benchmark-metadata-load.py",
            "scripts/metadata-tls-meter.mjs",
            "scripts/metadata-load-media.mjs",
            "scripts/metadata_load_instruments.py",
            "scripts/metadata_load_profile.py",
            "packages/crypto-core/src/lib.rs",
            "packages/crypto-core/examples/protocol_client.rs",
            "packages/crypto-core/Cargo.toml",
            "packages/crypto-core/Cargo.lock",
            "infrastructure/nginx/nginx.conf",
        )
    ],
]
source_fingerprints = {
    (
        str(path.relative_to(work))
        if path.is_relative_to(work)
        else str(path.relative_to(ROOT))
    ): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in source_files
    if path.is_file()
}


def docker(*arguments):
    return subprocess.run(
        ["docker", *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def owned_container(suffix, *arguments):
    instance = name + "-" + suffix
    # Never --rm: provenance label remains checkable even if the workload exits.
    identifier = docker(
        "create", "--name", instance, "--label", "haven.test-only=true", *arguments
    )
    containers.append(identifier)
    docker("start", identifier)
    return instance


def cpu(pid):
    values = Path(f"/proc/{pid}/stat").read_text().split()
    return (int(values[13]) + int(values[14])) / os.sysconf("SC_CLK_TCK")


def await_profile(name):
    for _ in range(100):
        if (folder / name).is_file():
            return json.loads((folder / name).read_text())
        time.sleep(0.1)
    raise RuntimeError("Synthetic API profile handshake timed out")


def container_usage(instance):
    pid = int(docker("inspect", "--format", "{{.State.Pid}}", instance))
    entry = next(
        line.split("::", 1)[1]
        for line in Path(f"/proc/{pid}/cgroup").read_text().splitlines()
        if line.startswith("0::")
    )
    folder = Path("/sys/fs/cgroup") / entry.lstrip("/")
    return {
        "cpu": {
            line.split()[0]: int(line.split()[1])
            for line in (folder / "cpu.stat").read_text().splitlines()
        },
        "memory_current_bytes": int((folder / "memory.current").read_text()),
        "memory_peak_bytes": int((folder / "memory.peak").read_text()),
        "scope": "Owned container cgroup v2, includes every PostgreSQL child and container page cache; peak includes setup",
    }


try:
    pg = owned_container(
        "pg",
        "--env-file",
        str(pg_env),
        "-p",
        "127.0.0.1:55434:5432",
        PG,
        "postgres",
        "-c",
        "track_io_timing=on",
        "-c",
        "track_wal_io_timing=on",
        "-c",
        "log_statement=none",
        "-c",
        "log_min_error_statement=panic",
    )
    owned_container(
        "redis",
        "-p",
        "127.0.0.1:56381:6379",
        REDIS,
        "redis-server",
        "--save",
        "",
        "--appendonly",
        "no",
        "--maxmemory",
        "128mb",
        "--maxmemory-policy",
        "noeviction",
    )
    for _ in range(120):
        result = subprocess.run(
            [
                "docker",
                "exec",
                pg,
                "pg_isready",
                "-h",
                "127.0.0.1",
                "-p",
                "5432",
                "-U",
                "haven_synthetic",
            ],
            capture_output=True,
        )
        if result.returncode == 0:
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("Disposable PostgreSQL did not start")
    subprocess.run(
        [str(python), "manage.py", "migrate", "--noinput"],
        cwd=work,
        env=environment,
        stdout=log,
        stderr=log,
        check=True,
    )
    api = subprocess.Popen(
        [
            str(ROOT / "apps/api/.venv/bin/uvicorn"),
            "metadata_profile_asgi:application",
            "--host",
            "127.0.0.1",
            "--port",
            "8115",
            "--no-access-log",
            "--proxy-headers",
            "--ws-max-size",
            "2048",
        ],
        cwd=work,
        env=api_environment,
        stdout=log,
        stderr=log,
    )
    children.append(api)
    publisher = subprocess.Popen(
        [str(python), "manage.py", "publish_outbox"],
        cwd=work,
        env=environment,
        stdout=log,
        stderr=log,
    )
    children.append(publisher)
    owned_container(
        "nginx",
        "--network",
        "host",
        "--read-only",
        "--tmpfs",
        "/var/cache/nginx",
        "--tmpfs",
        "/var/run",
        "--tmpfs",
        "/tmp",
        "-v",
        str(folder / "nginx.conf") + ":/etc/nginx/nginx.conf:ro",
        "-v",
        str(ROOT / ".local/tls/leaf.crt") + ":/etc/haven/tls/leaf.crt:ro",
        "-v",
        str(ROOT / ".local/tls/leaf.key") + ":/etc/haven/tls/leaf.key:ro",
        NGINX,
    )
    meter = subprocess.Popen(
        ["node", str(ROOT / "scripts/metadata-tls-meter.mjs")],
        cwd=ROOT,
        env={**os.environ, "HAVEN_METER_OUTPUT": str(folder / "tls.json")},
        stdout=subprocess.PIPE,
        stderr=log,
        text=True,
    )
    children.append(meter)
    if meter.stdout.readline().strip() != "READY":
        raise RuntimeError("TLS meter failed to start")
    for _ in range(80):
        with socket.socket() as check:
            if check.connect_ex(("127.0.0.1", 8115)) == 0:
                break
        time.sleep(0.25)
    worker = subprocess.Popen(
        [str(python), str(ROOT / "scripts/benchmark-metadata-load.py")],
        cwd=ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=log,
        text=True,
    )
    children.append(worker)
    if worker.stdout.readline().strip() != "READY":
        raise RuntimeError(
            f"Synthetic setup failed; private diagnostics: {folder}/private.log"
        )
    before_cpu = cpu(api.pid)
    before_publisher_cpu = cpu(publisher.pid)
    before_pg_usage = container_usage(pg)
    before_block_io = docker(
        "stats", "--no-stream", "--format", "{{json .BlockIO}}", pg
    )
    api.send_signal(signal.SIGUSR2)
    await_profile("api-profile-ready.json")
    meter.send_signal(signal.SIGUSR1)
    worker.stdin.write("GO\n")
    worker.stdin.flush()
    output = worker.stdout.readline()
    worker.wait(timeout=60)
    if worker.returncode or not output:
        raise RuntimeError(
            f"Synthetic load failed; private diagnostics: {folder}/private.log"
        )
    result = json.loads(output)
    result["api_cpu_seconds"] = cpu(api.pid) - before_cpu
    result["notification_worker_cpu_seconds"] = (
        cpu(publisher.pid) - before_publisher_cpu
    )
    result["postgres_container_usage_before"] = before_pg_usage
    result["postgres_container_usage_after"] = container_usage(pg)
    result["api_peak_rss_kib"] = int(
        next(
            line.split()[1]
            for line in Path(f"/proc/{api.pid}/status").read_text().splitlines()
            if line.startswith("VmHWM:")
        )
    )
    result["postgres_container_block_io_before"] = json.loads(before_block_io)
    api.send_signal(signal.SIGUSR1)
    result["api_profile"] = await_profile("api-profile.json")
    result["postgres_container_block_io_after"] = json.loads(
        docker("stats", "--no-stream", "--format", "{{json .BlockIO}}", pg)
    )
    meter.send_signal(signal.SIGUSR2)
    time.sleep(0.25)
    result["tls_transport"] = json.loads((folder / "tls.json").read_text())
    result["revision"] = args.revision
    result["working_source_manifest_sha256_at_start"] = source_manifest_sha256
    result["native_client_sha256"] = hashlib.sha256(
        (
            ROOT / "packages/crypto-core/target/release/examples/protocol_client"
        ).read_bytes()
    ).hexdigest()
    result["same_current_native_client_for_both_apis"] = True
    result["exercised_source_sha256_at_start"] = source_fingerprints
    result["source_diff_sha256"] = (
        __import__("hashlib")
        .sha256(subprocess.check_output(["git", "diff", "HEAD"], cwd=ROOT))
        .hexdigest()
        if args.revision == "current"
        else None
    )
    result["private_artifacts"] = str(folder.relative_to(ROOT))
    result["postgres_durability"] = (
        "fsync=on; synchronous_commit=on; full_page_writes=on; checksums=on; disk-backed disposable Docker volume; timings enabled"
    )
    result["limits"] = (
        "Unmodified ingress/DB/API rate/connection/storage limits; per-account loopback source; one API worker; co-located synthetic driver; no production or physical-device qualification"
    )
    print(json.dumps(result, indent=2))
finally:
    for child in reversed(children):
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    for instance in reversed(containers):
        info = json.loads(docker("inspect", instance))[0]
        if (info["Config"].get("Labels") or {}).get("haven.test-only") != "true":
            raise RuntimeError("Refusing removal: test provenance missing")
        docker("rm", "-f", "-v", instance)
    log.close()
