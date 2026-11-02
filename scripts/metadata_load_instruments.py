"""Bounded aggregate timings and independent native workers for synthetic load."""

from bisect import bisect_left
import json
import os
from pathlib import Path
import subprocess
import threading
import time

BOUNDS_MS = (
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1,
    2.5,
    5,
    10,
    25,
    50,
    100,
    250,
    500,
    1000,
    2500,
    5000,
    10000,
    25000,
    60000,
    120000,
)


class Timings:
    """Constant space per static phase. Percentiles are histogram bounds, not exact."""

    def __init__(self):
        self.enabled = threading.Event()
        self.lock = threading.Lock()
        self.rows = {}

    def record(self, phase, seconds):
        if not self.enabled.is_set():
            return
        milliseconds = max(0, seconds * 1000)
        with self.lock:
            row = self.rows.setdefault(phase, [0, 0.0, 0.0, [0] * (len(BOUNDS_MS) + 1)])
            row[0] += 1
            row[1] += milliseconds
            row[2] = max(row[2], milliseconds)
            row[3][bisect_left(BOUNDS_MS, milliseconds)] += 1

    def reset(self):
        with self.lock:
            self.rows.clear()
        self.enabled.set()

    def snapshot(self):
        with self.lock:
            output = {}
            for phase, (count, total, maximum, buckets) in self.rows.items():

                def quantile(fraction):
                    target, seen = max(1, int(count * fraction + 0.999999)), 0
                    for index, amount in enumerate(buckets):
                        seen += amount
                        if seen >= target:
                            return {
                                "lower_ms": 0 if index == 0 else BOUNDS_MS[index - 1],
                                "upper_ms": BOUNDS_MS[index]
                                if index < len(BOUNDS_MS)
                                else None,
                            }

                output[phase] = {
                    "samples": count,
                    "total_seconds": total / 1000,
                    "mean_ms": total / count,
                    "max_ms": maximum,
                    "histogram_counts": buckets.copy(),
                    "p50_bounds": quantile(0.5),
                    "p95_bounds": quantile(0.95),
                }
            return output


def process_usage(pid):
    values = Path(f"/proc/{pid}/stat").read_text().split()
    rss = next(
        line.split()[1]
        for line in Path(f"/proc/{pid}/status").read_text().splitlines()
        if line.startswith("VmHWM:")
    )
    return {
        "cpu_seconds": (int(values[13]) + int(values[14])) / os.sysconf("SC_CLK_TCK"),
        "peak_rss_kib": int(rss),
    }


class CryptoPool:
    """Each client is pinned to a worker; only that worker's private pipe is locked."""

    def __init__(self, binary, count, timings):
        if not 1 <= count <= 50:
            raise ValueError("One to fifty independent workers required")
        self.timings, self.workers = timings, []
        try:
            for _ in range(count):
                process = subprocess.Popen(
                    [str(binary)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                self.workers.append((process, threading.Lock()))
        except BaseException:
            self.close()
            raise

    def exchange(self, shard, message):
        process, lock = self.workers[shard]
        started = time.monotonic()
        with lock:
            acquired = time.monotonic()
            self.timings.record("crypto_worker_lock_wait", acquired - started)
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            line = process.stdout.readline()
            try:
                value = json.loads(line)
            except (ValueError, TypeError):
                raise RuntimeError("Native worker response invalid") from None
            self.timings.record("crypto_worker_roundtrip", time.monotonic() - acquired)
        if value.get("ok") is not True:
            raise RuntimeError("Native worker rejected command")
        return value

    def usage(self):
        return [process_usage(process.pid) for process, _ in self.workers]

    def close(self):
        for process, _ in self.workers:
            if process.poll() is None:
                process.terminate()
        for process, _ in self.workers:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdin.close()
            process.stdout.close()


class WaitSampler:
    """Sample only aggregate PG wait classes; never retrieve SQL or identity data."""

    def __init__(self, config):
        self.config = config
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.samples, self.errors, self.classes, self.intervals = 0, 0, {}, []
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        import psycopg

        try:
            with psycopg.connect(
                host=self.config["HOST"],
                port=self.config["PORT"],
                dbname=self.config["NAME"],
                user=self.config["USER"],
                password=self.config["PASSWORD"],
                application_name="haven-load-wait-sampler",
                connect_timeout=10,
                autocommit=True,
            ) as conn:
                self.ready.set()
                previous = time.monotonic()
                while not self.stop.is_set():
                    rows = conn.execute(
                        "SELECT state,coalesce(wait_event_type,'CPU_or_runnable'),coalesce(wait_event,'none'),count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() GROUP BY 1,2,3"
                    ).fetchall()
                    now = time.monotonic()
                    self.intervals.append(now - previous)
                    previous = now
                    self.samples += 1
                    for state, kind, event, count in rows:
                        key = ":".join((state or "unknown", kind, event))
                        item = self.classes.setdefault(
                            key, {"backend_observations": 0, "peak_backends": 0}
                        )
                        item["backend_observations"] += count
                        item["peak_backends"] = max(item["peak_backends"], count)
                    self.stop.wait(0.1)
        except Exception:
            self.errors += 1  # No potentially sensitive exception text.
            self.ready.set()

    def start(self):
        self.thread.start()
        if not self.ready.wait(12) or self.errors:
            raise RuntimeError("PostgreSQL wait sampler startup failed")

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=15)
        if self.thread.is_alive() or self.errors:
            raise RuntimeError("PostgreSQL wait sampler incomplete")
        return {
            "samples": self.samples,
            "errors": self.errors,
            "interval_mean_ms": sum(self.intervals)
            * 1000
            / max(1, len(self.intervals)),
            "interval_max_ms": max(self.intervals, default=0) * 1000,
            "classes": self.classes,
            "scope": "Sample counts of backends, not exact query wait durations; idle ClientRead is not blocking work; CPU_or_runnable is not measured CPU; sampler connection excluded",
        }


def merge_profiles(profiles):
    """Merge actual bucket counts, never average worker percentiles."""
    timings = Timings()
    pools = {"pool_before": {}, "pool_after": {}}
    for profile in profiles:
        for phase, row in profile["timings"].items():
            target = timings.rows.setdefault(
                phase, [0, 0.0, 0.0, [0] * (len(BOUNDS_MS) + 1)]
            )
            target[0] += row["samples"]
            target[1] += row["total_seconds"] * 1000
            target[2] = max(target[2], row["max_ms"])
            assert len(row["histogram_counts"]) == len(target[3])
            target[3] = [a + b for a, b in zip(target[3], row["histogram_counts"])]
        for when in pools:
            for alias, stats in profile.get(when, {}).items():
                combined = pools[when].setdefault(alias, {})
                for name, value in stats.items():
                    combined[name] = combined.get(name, 0) + value
    return {
        "timings": timings.snapshot(),
        **pools,
        "scope": "Merged histogram counts across independent API processes; SQL cursor timing HTTP-only; connection/commit and pool statistics include WebSockets; windows include handshakes/teardown; phases overlap",
    }
