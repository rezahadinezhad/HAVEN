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
from dataclasses import asdict

from metadata_load_instruments import merge_profiles
from metadata_workload import Workload, PROFILES, default_duration, default_rate

ROOT = Path(__file__).resolve().parent.parent
PG = "postgres:16.14-bookworm@sha256:64154d0babcb1741988719e703419af0382b19953706149f9872fbd0f438efa8"
REDIS = "redis:7.4.6-alpine@sha256:3b73847e72874be07e6657b129a94761662b79bc0f679273757d4218573b2a98"
NGINX = "nginx:1.28.3-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236"
parser = argparse.ArgumentParser()
parser.add_argument("--revision", default="current")
parser.add_argument("--profile", choices=PROFILES, default="realistic")
parser.add_argument("--users", type=int, default=100)
parser.add_argument("--group-size", type=int, default=10)
parser.add_argument("--files", type=int, default=None)
parser.add_argument("--warmup-seconds", type=int, default=20)
parser.add_argument("--recovery-seconds", type=int, default=30)
parser.add_argument(
    "--recipient-workers",
    type=int,
    default=100,
    choices=(0, 50, 100, 200),
    help="Bound independent recipient delivery; 0 preserves serial recipients within each group as a control",
)
parser.add_argument(
    "--no-phase-profile",
    action="store_true",
    help="Capacity control without API request/SQL timing wrappers; retain process CPU and workload checks",
)
parser.add_argument(
    "--http-mode",
    choices=("asgi", "wsgi", "gunicorn"),
    default="asgi",
    help="Disposable HTTP adapter comparison; WebSockets remain unchanged",
)
parser.add_argument("--http-threads", type=int, choices=(2, 4, 8, 16), default=8)
parser.add_argument(
    "--gil-profile",
    action="store_true",
    help="Diagnostic GIL sampling of one owned API process; no locals; not capacity qualification",
)
parser.add_argument(
    "--call-profile",
    "--cpu-profile",
    dest="cpu_profile",
    action="store_true",
    help="Diagnostic sampled call wall times including waits; not CPU attribution or capacity qualification",
)
parser.add_argument(
    "--api-workers",
    type=int,
    default=4,
    choices=(1, 2, 4, 8),
    help="Actual Uvicorn worker processes sharing the production-style listener",
)
parser.add_argument("--resilience", action="store_true")
parser.add_argument("--seconds", type=int, default=None)
parser.add_argument("--rate", type=float, default=None)
parser.add_argument("--rekey-every", type=int, default=100)
parser.add_argument(
    "--sender-workers",
    type=int,
    default=2,
    choices=(1, 2),
    help="Native authors per conversation; one preserves the sender-ACK serialization control",
)
parser.add_argument(
    "--hold-first-sender-ack",
    action="store_true",
    help="Diagnostic only: hold first author ACK until a second publication or five-second timeout",
)
parser.add_argument(
    "--db-pool-size",
    type=int,
    default=None,
    help="Override only the disposable API pool: 0 disables, 1–32 bounds reuse; unset follows selected revision",
)
parser.add_argument(
    "--crypto-workers",
    type=int,
    default=10,
    help="Independent native processes, 1–50; use 1 for the serialized control",
)
args = parser.parse_args()
args.seconds = (
    args.seconds if args.seconds is not None else default_duration(args.profile)
)
args.rate = args.rate if args.rate is not None else default_rate(args.profile)
args.files = (
    args.files
    if args.files is not None
    else (5 if args.profile in ("legacy-stress", "combined", "combined-natural") else 0)
)
try:
    workload = Workload(
        args.profile,
        args.users,
        args.seconds,
        args.rate,
        args.group_size,
        args.files,
        args.rekey_every,
        args.warmup_seconds,
        args.recovery_seconds,
        args.sender_workers,
        args.hold_first_sender_ack,
    )
    workload.population()
    if args.profile == "legacy-stress" and (args.users != 100 or args.files != 5):
        raise ValueError("Legacy stress preserves exactly 100 accounts and five files")
except ValueError as error:
    parser.error(str(error))
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
    or (args.db_pool_size is not None and not 0 <= args.db_pool_size <= 32)
    or (
        args.db_pool_size is not None
        and (args.api_workers + (1 if args.http_mode == "gunicorn" else 0))
        * args.db_pool_size
        > 64
    )
):
    raise SystemExit(
        "Bounded workload required (1–7200 seconds, up to 20 messages/second)"
    )
diagnostic_package = {
    "wsgi": ("a2wsgi", "1.10.10"),
    "gunicorn": ("gunicorn", "26.2.0"),
}.get(args.http_mode)
if diagnostic_package:
    package, version = diagnostic_package
    check = subprocess.run(
        [
            str(ROOT / "apps/api/.venv/bin/python"),
            "-c",
            "import importlib.metadata,sys;sys.exit(importlib.metadata.version(sys.argv[1]) != sys.argv[2])",
            package,
            version,
        ],
        capture_output=True,
    )
    if check.returncode:
        raise SystemExit(
            f"Diagnostic HTTP comparison requires temporary {package}=={version}; not a runtime dependency"
        )
os.umask(0o077)
for port in (55434, 56381, 8115, 8116, 8452, 8454):
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
    "HAVEN_LOAD_RECIPIENT_WORKERS": str(args.recipient_workers),
    "HAVEN_LOAD_CPU_PROFILE": "1" if args.cpu_profile else "0",
    "HAVEN_LOAD_PHASE_PROFILE": "0" if args.no_phase_profile else "1",
    "HAVEN_LOAD_DEBUGGER_PARENT": str(os.getpid()) if args.gil_profile else "",
    "HAVEN_LOAD_SECONDS": str(args.seconds),
    "HAVEN_LOAD_RATE": str(args.rate),
    "HAVEN_LOAD_REKEY_EVERY": str(args.rekey_every),
    "HAVEN_LOAD_RECONNECT": "1" if args.resilience else "0",
    "HAVEN_WORKLOAD_DEFINITION": json.dumps(asdict(workload)),
}
# Select the disposable API budget through the explicit CLI, never through
# unrelated workstation runtime settings inherited by the fixture processes.
environment.pop("HAVEN_API_WORKERS", None)
environment.pop("HAVEN_DB_POOL_SIZE", None)
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
if args.http_mode == "gunicorn":
    nginx = nginx.replace("server 127.0.0.1:8115;", "server 127.0.0.1:8116;")
    nginx = nginx.replace(
        "upstream haven_web",
        "upstream haven_ws { server 127.0.0.1:8115; }\n  upstream haven_web",
    )
    start = nginx.index("location /ws/")
    nginx = nginx[:start] + nginx[start:].replace(
        "proxy_pass http://haven_api;", "proxy_pass http://haven_ws;", 1
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
    + (
        ""
        if args.db_pool_size is None
        else (
            "from copy import deepcopy\nDATABASES = deepcopy(DATABASES)\n"
            'DATABASES["default"]["OPTIONS"].pop("pool", None)\n'
            'DATABASES["default"]["CONN_HEALTH_CHECKS"] = '
            + str(bool(args.db_pool_size))
            + "\n"
            + (
                ""
                if not args.db_pool_size
                else 'DATABASES["default"]["OPTIONS"]["pool"] = '
                + repr(
                    {
                        "min_size": 1,
                        "max_size": args.db_pool_size,
                        "timeout": 3,
                        "max_waiting": 64,
                        "max_idle": 60,
                        "max_lifetime": 600,
                    }
                )
                + "\n"
            )
        )
    )
)
(folder / "metadata_profile_asgi.py").write_text(
    "from metadata_load_profile import ASGIProfiler\n"
    "from haven.asgi import application as original\n"
    + (
        ""
        if args.http_mode != "wsgi"
        else 'from a2wsgi import WSGIMiddleware\nfrom django.core.wsgi import get_wsgi_application\noriginal.application_mapping["http"] = WSGIMiddleware(get_wsgi_application(), workers='
        + str(args.http_threads)
        + ", send_queue_size=10)\n"
    )
    + "application = ASGIProfiler(original)\n"
)
(folder / "metadata_profile_wsgi.py").write_text(
    "from django.core.wsgi import get_wsgi_application\napplication = get_wsgi_application()\n"
)
api_environment = {
    **environment,
    "DJANGO_SETTINGS_MODULE": "metadata_profile_settings",
    "HAVEN_API_WORKERS": str(args.api_workers),
    "PYTHONPATH": os.pathsep.join((str(folder), str(ROOT / "scripts"), str(work))),
}
if args.db_pool_size is not None:
    api_environment["HAVEN_DB_POOL_SIZE"] = str(args.db_pool_size)
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
            "scripts/benchmark-metadata-realistic.py",
            "scripts/metadata_workload.py",
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


def await_profile(name, pid):
    path = folder / (str(pid) + "-" + name)
    for _ in range(100):
        if path.is_file():
            return json.loads(path.read_text())
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
    websocket_environment = api_environment
    if args.http_mode == "gunicorn":
        websocket_environment = {
            **api_environment,
            "HAVEN_API_WORKERS": "1",
            "HAVEN_DB_POOL_SIZE": "8",
        }
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
            "--workers",
            str(1 if args.http_mode == "gunicorn" else args.api_workers),
        ],
        cwd=work,
        env=websocket_environment,
        stdout=log,
        stderr=log,
    )
    children.append(api)
    http = None
    if args.http_mode == "gunicorn":
        http = subprocess.Popen(
            [
                str(python),
                "-m",
                "gunicorn",
                "metadata_profile_wsgi:application",
                "--bind",
                "127.0.0.1:8116",
                "--worker-class",
                "gthread",
                "--workers",
                str(args.api_workers),
                "--threads",
                str(args.http_threads),
                "--access-logfile",
                "/dev/null",
                "--error-logfile",
                "/dev/null",
                "--forwarded-allow-ips",
                "127.0.0.1",
            ],
            cwd=work,
            env={
                **api_environment,
                "HAVEN_DB_POOL_SIZE": str(
                    args.db_pool_size
                    if args.db_pool_size is not None
                    else min(12, 56 // args.api_workers)
                ),
            },
            stdout=log,
            stderr=log,
        )
        children.append(http)
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
        [
            str(python),
            str(
                ROOT
                / "scripts"
                / (
                    "benchmark-metadata-load.py"
                    if args.profile == "legacy-stress"
                    else "benchmark-metadata-realistic.py"
                )
            ),
        ],
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
    api_pids = []
    for _ in range(100):
        api_pids = sorted(
            json.loads(path.read_text())["pid"]
            for path in folder.glob("*-api-process.json")
        )
        if len(api_pids) == args.api_workers + (1 if http else 0):
            break
        time.sleep(0.1)
    if len(api_pids) != args.api_workers + (1 if http else 0):
        raise RuntimeError("API worker profile registration incomplete")
    for pid in api_pids:
        parent = int(
            next(
                line.split()[1]
                for line in Path(f"/proc/{pid}/status").read_text().splitlines()
                if line.startswith("PPid:")
            )
        )
        if pid != api.pid and parent not in {api.pid, http.pid if http else api.pid}:
            raise RuntimeError("Refusing unowned API worker")
    before_cpu = {pid: cpu(pid) for pid in api_pids}
    before_publisher_cpu = cpu(publisher.pid)
    before_pg_usage = container_usage(pg)
    before_block_io = docker(
        "stats", "--no-stream", "--format", "{{json .BlockIO}}", pg
    )
    for pid in api_pids:
        os.kill(pid, signal.SIGUSR2)
    for pid in api_pids:
        await_profile("api-profile-ready.json", pid)
    spy = None
    if args.gil_profile:
        spy = subprocess.Popen(
            [
                str(ROOT / ".local/throughput-tools/bin/py-spy"),
                "record",
                "--pid",
                str(api_pids[0]),
                "--gil",
                "--rate",
                "100",
                "--duration",
                "30",
                "--format",
                "raw",
                "--output",
                str(folder / "gil.folded"),
            ],
            stdout=log,
            stderr=log,
        )
        children.append(spy)
    meter.send_signal(signal.SIGUSR1)
    worker.stdin.write("GO\n")
    worker.stdin.flush()
    output = worker.stdout.readline()
    worker.wait(timeout=60)
    if worker.returncode or not output:
        for pid in api_pids:
            os.kill(pid, signal.SIGUSR1)
        print(
            json.dumps(
                {
                    "status": "FAILED_DIAGNOSTIC_OR_WORKLOAD",
                    "workload_definition": asdict(workload),
                    "api_workers": args.api_workers,
                    "revision": args.revision,
                    "working_source_manifest_sha256_at_start": source_manifest_sha256,
                    "source_fingerprints": source_fingerprints,
                    "driver_failure_summary": json.loads(
                        (folder / "failure-summary.json").read_text()
                    )
                    if (folder / "failure-summary.json").exists()
                    else None,
                    "api_profiles_by_worker": [
                        await_profile("api-profile.json", pid) for pid in api_pids
                    ],
                    "exception_shapes": [
                        json.loads(path.read_text())
                        for path in folder.glob("*-api-exception-shape.json")
                    ],
                    "handled_failure_types": [
                        json.loads(path.read_text())
                        for path in folder.glob("*-api-handled-failure.json")
                    ],
                    "scope": "Partial failed run, no capacity qualification or invented completion count",
                },
                indent=2,
            ),
            flush=True,
        )
        raise RuntimeError(
            f"Synthetic load failed; private diagnostics: {folder}/private.log"
        )
    result = json.loads(output)
    if spy:
        spy.wait(timeout=40)
        if spy.returncode:
            raise RuntimeError("Owned GIL sampler failed; private diagnostics retained")
        leaves = {}
        for line in (folder / "gil.folded").read_text().splitlines():
            stack, count = line.rsplit(" ", 1)
            leaf = stack.split(";")[-1]
            leaves[leaf] = leaves.get(leaf, 0) + int(count)
        result["gil_profile"] = {
            "leaf_samples": sorted(
                [{"frame": frame, "samples": count} for frame, count in leaves.items()],
                key=lambda row: row["samples"],
                reverse=True,
            )[:40],
            "total_samples": sum(leaves.values()),
            "scope": "One owned API process, GIL-holding Python samples; no locals; diagnostic only, not exact CPU percentages or capacity qualification; raw stacks remain private",
        }
    result["api_worker_cpu_seconds"] = [cpu(pid) - before_cpu[pid] for pid in api_pids]
    result["api_cpu_seconds"] = sum(result["api_worker_cpu_seconds"])
    result["api_workers"] = args.api_workers
    result["http_mode"] = args.http_mode
    result["diagnostic_http_package"] = (
        dict([diagnostic_package]) if diagnostic_package else None
    )
    result["http_threads"] = args.http_threads if args.http_mode != "asgi" else None
    result["websocket_worker_count"] = 1 if http else args.api_workers
    result["api_phase_profile_enabled"] = not args.no_phase_profile
    result["notification_worker_cpu_seconds"] = (
        cpu(publisher.pid) - before_publisher_cpu
    )
    result["postgres_container_usage_before"] = before_pg_usage
    result["postgres_container_usage_after"] = container_usage(pg)
    result["api_worker_peak_rss_kib"] = [
        int(
            next(
                line.split()[1]
                for line in Path(f"/proc/{pid}/status").read_text().splitlines()
                if line.startswith("VmHWM:")
            )
        )
        for pid in api_pids
    ]
    result["api_peak_rss_kib"] = sum(result["api_worker_peak_rss_kib"])
    result["api_memory_scope"] = (
        "Sum of per-worker lifetime HWM including setup; not simultaneous total RSS peak"
    )
    result["postgres_container_block_io_before"] = json.loads(before_block_io)
    for pid in api_pids:
        os.kill(pid, signal.SIGUSR1)
    result["api_profiles_by_worker"] = [
        await_profile("api-profile.json", pid) for pid in api_pids
    ]
    result["api_profile"] = merge_profiles(result["api_profiles_by_worker"])
    result["postgres_container_block_io_after"] = json.loads(
        docker("stats", "--no-stream", "--format", "{{json .BlockIO}}", pg)
    )
    meter.send_signal(signal.SIGUSR2)
    time.sleep(0.25)
    result["tls_transport"] = json.loads((folder / "tls.json").read_text())
    result["revision"] = args.revision
    result["api_db_pool_override"] = args.db_pool_size
    result["cpu_profile_diagnostic"] = args.cpu_profile
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
        "Unmodified ingress/DB/API rate/connection/storage limits; per-account loopback source; recorded HTTP/WebSocket worker counts; co-located synthetic driver; no production or physical-device qualification"
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
