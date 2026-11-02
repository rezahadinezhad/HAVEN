#!/usr/bin/env python3
"""Real native-worker isolation, signature, lifecycle and timing regressions."""

import base64
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from metadata_load_instruments import CryptoPool, Timings, merge_profiles

ROOT = Path(__file__).resolve().parent.parent


class InstrumentTests(unittest.TestCase):
    def test_worker_histograms_merge_counts_not_averaged_percentiles(self):
        fast, slow = Timings(), Timings()
        fast.reset()
        slow.reset()
        for _ in range(19):
            fast.record("phase", 0.001)
        slow.record("phase", 1)
        merged = merge_profiles(
            [{"timings": fast.snapshot()}, {"timings": slow.snapshot()}]
        )
        row = merged["timings"]["phase"]
        self.assertEqual(row["samples"], 20)
        self.assertAlmostEqual(row["total_seconds"], 1.019)
        self.assertEqual(row["p95_bounds"]["upper_ms"], 1)
        self.assertEqual(row["max_ms"], 1000)

    def test_histogram_reset_disabled_collection_and_bounds(self):
        timings = Timings()
        timings.record("phase", 1)
        self.assertFalse(timings.snapshot())
        timings.reset()
        for value in [0.001, 0.002, 0.004, 0.008]:
            timings.record("phase", value)
        row = timings.snapshot()["phase"]
        self.assertEqual(row["samples"], 4)
        self.assertAlmostEqual(row["total_seconds"], 0.015)
        self.assertEqual(row["p95_bounds"], {"lower_ms": 5, "upper_ms": 10})
        timings.reset()
        self.assertFalse(timings.snapshot())

    def test_real_workers_keep_same_client_slot_independent_and_reap(self):
        timings = Timings()
        pool = CryptoPool(
            ROOT / "packages/crypto-core/target/release/examples/protocol_client",
            2,
            timings,
        )
        try:
            keys = []
            for shard in range(2):
                value = pool.exchange(
                    shard,
                    {
                        "client": "same-slot",
                        "command": {
                            "op": "init",
                            "identity": f"synthetic-worker-{shard}",
                        },
                    },
                )
                keys.append(base64.b64decode(value["result"]["public_key"]))
            self.assertTrue(
                keys[0] != keys[1], "Workers must have independent identity state"
            )
            timings.reset()

            def sign(index):
                shard = index % 2
                payload = f"synthetic-worker-check-{index}".encode()
                result = pool.exchange(
                    shard,
                    {
                        "client": "same-slot",
                        "command": {
                            "op": "sign",
                            "payload": base64.b64encode(payload).decode(),
                        },
                    },
                )
                signature = base64.b64decode(result["result"]["signature"])
                Ed25519PublicKey.from_public_bytes(keys[shard]).verify(
                    signature, payload
                )

            with ThreadPoolExecutor(max_workers=8) as threads:
                list(threads.map(sign, range(64)))
            self.assertEqual(
                timings.snapshot()["crypto_worker_roundtrip"]["samples"], 64
            )
            self.assertEqual(len(pool.usage()), 2)
            with self.assertRaises(RuntimeError):
                pool.exchange(0, {"client": "same-slot", "command": {"op": "unknown"}})
        finally:
            pool.close()
        self.assertTrue(all(process.poll() is not None for process, _ in pool.workers))

    def test_profiler_refuses_non_disposable_environment(self):
        env = {k: v for k, v in os.environ.items() if k != "HAVEN_ISOLATED_LOAD"}
        result = subprocess.run(
            [sys.executable, "-c", "import metadata_load_profile"],
            cwd=ROOT / "scripts",
            env=env,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"Profiler requires disposable load environment", result.stderr)


if __name__ == "__main__":
    unittest.main()
