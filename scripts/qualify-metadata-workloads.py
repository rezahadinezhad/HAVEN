#!/usr/bin/env python3
"""Serial owned synthetic qualification; publish only completed, parsed aggregate JSON."""

import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--cases",
    nargs="*",
    help="Select named cases; default runs the complete matrix including two-hour endurance",
)
parser.add_argument(
    "--label",
    default="revised",
    help="New evidence subdirectory; refuses existing case results",
)
args = parser.parse_args()
if not args.label or any(
    c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in args.label
):
    parser.error("Use a lowercase alphanumeric/hyphen evidence label")
cases = {
    "smoke": [
        "--profile",
        "realistic",
        "--users",
        "20",
        "--seconds",
        "12",
        "--rekey-every",
        "2",
    ],
    "author-lane-serial": [
        "--profile",
        "group",
        "--users",
        "10",
        "--group-size",
        "10",
        "--seconds",
        "4",
        "--rate",
        "1",
        "--warmup-seconds",
        "0",
        "--recovery-seconds",
        "0",
        "--sender-workers",
        "1",
        "--hold-first-sender-ack",
    ],
    "author-lane-pipelined": [
        "--profile",
        "group",
        "--users",
        "10",
        "--group-size",
        "10",
        "--seconds",
        "4",
        "--rate",
        "1",
        "--warmup-seconds",
        "0",
        "--recovery-seconds",
        "0",
        "--sender-workers",
        "2",
        "--hold-first-sender-ack",
    ],
    "legacy-smoke": ["--profile", "legacy-stress", "--seconds", "5", "--rate", "1"],
    "baseline-burst": ["--profile", "burst", "--revision", "b988879"],
    "current-burst": ["--profile", "burst"],
    "combined": ["--profile", "combined"],
    "combined-natural": ["--profile", "combined-natural"],
    "media-burst": ["--profile", "burst", "--files", "5"],
    "handoff": ["--profile", "handoff", "--seconds", "300", "--rekey-every", "5"],
    "intermittent": [
        "--profile",
        "intermittent",
        "--seconds",
        "300",
        "--rekey-every",
        "5",
    ],
    "connections": ["--profile", "connections", "--seconds", "120"],
    "group-5": ["--profile", "group", "--group-size", "5", "--rekey-every", "50"],
    "group-10": ["--profile", "group", "--group-size", "10", "--rekey-every", "50"],
    "group-25": ["--profile", "group", "--group-size", "25", "--rekey-every", "50"],
    "endurance": ["--profile", "realistic", "--seconds", "7200", "--rate", "2"],
}
chosen = args.cases if args.cases is not None else list(cases)
if not chosen or set(chosen) - cases.keys():
    parser.error("Choose one or more known case names: " + ", ".join(cases))
os.umask(0o077)
private = ROOT / ".local" / ("workload-qualification-" + secrets.token_hex(6))
private.mkdir(mode=0o700)
public = ROOT / "docs/evidence/metadata-realistic-workload-2026-11-02" / args.label
public.mkdir(exist_ok=True)
if (public / "matrix-summary.json").exists() or any(
    (public / (name + ".json")).exists() for name in chosen
):
    parser.error("Evidence label already contains results; choose a new label")
summary = {
    "status": "RUNNING",
    "cases": [],
    "private_artifacts": str(private.relative_to(ROOT)),
    "scope": "Serial synthetic native tests on a shared workstation; no production capacity qualification",
}


def publish(name, value):
    temporary = private / (name + ".publish")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(public / name)


def interrupted(*_):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, interrupted)
child = None
try:
    for name in chosen:
        summary["active_case"] = name
        publish("matrix-summary.json", summary)
        start = time.monotonic()
        with (
            (private / (name + ".json")).open("w") as output,
            (private / (name + ".stderr")).open("w") as errors,
        ):
            child = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "scripts/benchmark-metadata-isolated.py"),
                    "--no-phase-profile",
                    *cases[name],
                ],
                cwd=ROOT,
                stdout=output,
                stderr=errors,
            )
            result = child.wait()
        try:
            data = json.loads((private / (name + ".json")).read_text())
        except ValueError:
            data = {
                "status": "FAILED_OR_INTERRUPTED",
                "scope": "No fabricated completion counts; protected diagnostics retained",
            }
        publish(name + ".json", data)
        integrity = data.get("integrity_status")
        if name == "legacy-smoke":
            integrity = (
                "PASS"
                if data.get("target_status") == "COMPLETED"
                and data.get("zero_socket_error_gate") == "PASS"
                else "FAIL"
            )
        summary["cases"].append(
            {
                "name": name,
                "exit_code": result,
                "integrity_status": integrity,
                "sender_pipeline_probe_status": data.get(
                    "sender_pipeline_probe_status", "NOT_REQUESTED"
                ),
                "performance_status": data.get(
                    "performance_status", data.get("target_status")
                ),
                "wall_seconds_including_setup": time.monotonic() - start,
            }
        )
        publish("matrix-summary.json", summary)
        if (
            result
            or integrity != "PASS"
            or data.get("sender_pipeline_probe_status") == "FAIL"
        ):
            raise RuntimeError(
                "Qualification stopped for failed workload integrity; inspect protected diagnostics"
            )
    summary["status"] = "COMPLETED"
    summary.pop("active_case", None)
    publish("matrix-summary.json", summary)
except BaseException:
    if child is not None and child.poll() is None:
        child.send_signal(signal.SIGINT)
        try:
            child.wait(timeout=60)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    summary["status"] = "INTERRUPTED_OR_FAILED"
    publish("matrix-summary.json", summary)
    raise
