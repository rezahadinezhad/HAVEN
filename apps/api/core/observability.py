"""Bounded local operational counters. No addresses, users, paths, content or secrets are labels."""

import time
from functools import lru_cache
import redis
from django.conf import settings

LIMITS = (10, 25, 50, 100, 250, 500, 750, 1500, 5000)


@lru_cache(maxsize=1)
def client():
    return redis.Redis.from_url(
        settings.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"][0],
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )


def request_observed(milliseconds, status):
    try:
        prefix = f"haven:metrics:{int(time.time()) // 60}:"
        bucket = next((str(n) for n in LIMITS if milliseconds <= n), "overflow")
        values = {"requests": 1, "latency_ms_sum": max(0, int(milliseconds)), "bucket:" + bucket: 1}
        if status >= 500:
            values["errors_5xx"] = 1
        with client().pipeline(transaction=False) as pipe:
            for suffix, increment in values.items():
                pipe.incrby(prefix + suffix, increment)
                pipe.expire(prefix + suffix, 180)
            pipe.execute()
    except redis.RedisError:
        pass  # Telemetry must not become a durable-delivery dependency.


def websocket_lease(channel, remove=False):
    try:
        db = client()
        if remove:
            db.zrem("haven:ws:leases", channel)
        else:
            with db.pipeline(transaction=False) as pipe:
                pipe.zremrangebyscore("haven:ws:leases", "-inf", time.time() - 70)
                pipe.zadd("haven:ws:leases", {channel: time.time()})
                pipe.expire("haven:ws:leases", 180)
                pipe.execute()
    except redis.RedisError:
        pass


def snapshot():
    try:
        db = client()
        minute = int(time.time()) // 60
        names = (
            ["requests", "errors_5xx", "latency_ms_sum"]
            + ["bucket:" + str(n) for n in LIMITS]
            + ["bucket:overflow"]
        )
        values = db.mget([f"haven:metrics:{m}:{name}" for m in [minute - 1, minute] for name in names])
        totals = {
            name: int(values[i] or 0) + int(values[len(names) + i] or 0) for i, name in enumerate(names)
        }
        db.zremrangebyscore("haven:ws:leases", "-inf", time.time() - 70)
        count = totals["requests"]
        seen, p95 = 0, None
        for bound in LIMITS:
            seen += totals["bucket:" + str(bound)]
            if count and seen >= count * 0.95:
                p95 = bound
                break
        return {
            "status": "local_counters",
            "window_seconds": "60_to_120",
            "api_requests": count,
            "api_errors_5xx": totals["errors_5xx"],
            "mean_ms": round(totals["latency_ms_sum"] / count, 2) if count else None,
            "p95_upper_bound_ms": p95,
            "above_5000ms": totals["bucket:overflow"],
            "websocket_leases": db.zcard("haven:ws:leases"),
            "lease_timeout_seconds": 70,
            "notice": "Approximate process-external counters; not a reference-host performance qualification",
        }
    except redis.RedisError:
        return {"status": "unavailable"}
