"""Synthetic-only API profiler. No request/SQL text, identifiers or parameters saved."""

import json
import importlib.util
import cProfile
import pstats
import sys
import ctypes
import os
from pathlib import Path
import signal
import threading
import time

from metadata_load_instruments import Timings
from django.core.signals import got_request_exception

if (
    os.environ.get("HAVEN_ISOLATED_LOAD") != "synthetic-only"
    or os.environ.get("POSTGRES_PORT") != "55434"
):
    raise RuntimeError("Profiler requires disposable load environment")
FOLDER = Path(os.environ["HAVEN_LOAD_PRIVATE"])
if FOLDER.stat().st_mode & 0o077:
    raise RuntimeError("Private profile folder required")
if os.environ.get("HAVEN_LOAD_DEBUGGER_PARENT"):
    # Permit only the owning synthetic orchestrator and its debugger children,
    # without changing system ptrace policy or any deployed process.
    owner = int(os.environ["HAVEN_LOAD_DEBUGGER_PARENT"])
    ancestor = os.getppid()
    for _ in range(8):
        if ancestor == owner:
            break
        ancestor = int(
            next(
                line.split()[1]
                for line in Path(f"/proc/{ancestor}/status").read_text().splitlines()
                if line.startswith("PPid:")
            )
        )
    else:
        raise RuntimeError("Debugger is not owned by this synthetic run")
    if ctypes.CDLL(None).prctl(0x59616D61, owner, 0, 0, 0) != 0:
        raise RuntimeError("Cannot authorize the owned synthetic debugger")
TIMINGS = Timings()
PHASE_PROFILE = os.environ.get("HAVEN_LOAD_PHASE_PROFILE", "1") == "1"
RESET, SNAPSHOT = threading.Event(), threading.Event()
POOL_BEFORE = {}
CPU_ROWS = {}
CPU_COUNT = 0
CPU_LOCK = threading.Lock()


def pool_stats():
    from django.db.backends.postgresql.base import DatabaseWrapper

    return {
        alias: pool.get_stats()
        for alias, pool in DatabaseWrapper._connection_pools.items()
    }


def write(name, value):
    name = str(os.getpid()) + "-" + name
    temporary = FOLDER / (name + ".tmp")
    temporary.write_text(json.dumps(value))
    temporary.replace(FOLDER / name)


def control():
    global POOL_BEFORE
    while True:
        if RESET.wait(0.05):
            RESET.clear()
            POOL_BEFORE = pool_stats()
            TIMINGS.reset()
            write("api-profile-ready.json", {"reset": True})
        if SNAPSHOT.is_set():
            SNAPSHOT.clear()
            TIMINGS.enabled.clear()
            write(
                "api-profile.json",
                {
                    "timings": TIMINGS.snapshot(),
                    "pool_before": POOL_BEFORE,
                    "pool_after": pool_stats(),
                    "sampled_call_wall": sorted(
                        CPU_ROWS.values(),
                        key=lambda row: row["self_seconds"],
                        reverse=True,
                    )[:40],
                    "scope": "HTTP middleware SQL plus ASGI arrival/response; process-wide DB connection/commit/rollback timing includes WebSockets; no WebSocket cursor SQL, SQL text, parameters, paths, headers or identifiers; timings overlap, do not sum phases",
                },
            )


write("api-process.json", {"pid": os.getpid()})
signal.signal(signal.SIGUSR2, lambda *_: RESET.set())
signal.signal(signal.SIGUSR1, lambda *_: SNAPSHOT.set())
threading.Thread(target=control, daemon=True).start()


def exception_shape(sender, request, **kwargs):
    error = sys.exception()
    sites = []
    tb = error.__traceback__ if error else None
    while tb:
        code = tb.tb_frame.f_code
        sites.append(
            {
                "source": "/".join(Path(code.co_filename).parts[-3:]),
                "line": tb.tb_lineno,
                "function": code.co_name,
            }
        )
        tb = tb.tb_next
    write("api-exception-shape.json", {"type": type(error).__name__, "sites": sites})


got_request_exception.connect(exception_shape, weak=False)


class RequestProfiler:
    def __init__(self, get_response):
        self.get_response = get_response
        if not getattr(RequestProfiler, "_error_wrapped", False):
            RequestProfiler._error_wrapped = True
            from core import errors

            original_handler = errors.handler

            def handled_failure(exc, context):
                response = original_handler(exc, context)
                if response.status_code >= 500:
                    write(
                        "api-handled-failure.json",
                        {
                            "type": type(exc).__name__,
                            "cause": type(exc.__cause__).__name__,
                        },
                    )
                return response

            errors.handler = handled_failure
        if not PHASE_PROFILE:
            return
        if getattr(RequestProfiler, "_wrapped", False):
            return
        RequestProfiler._wrapped = True
        # These operations bypass cursor.execute_wrapper. Instrument only this
        # disposable process, never the repository's production middleware.
        from django.db.backends.postgresql.base import DatabaseWrapper

        if not getattr(DatabaseWrapper, "_haven_load_profile", False):

            def timed(method, phase):
                def call(instance, *args, **kwargs):
                    begin = time.monotonic()
                    try:
                        return method(instance, *args, **kwargs)
                    finally:
                        TIMINGS.record(phase, time.monotonic() - begin)

                return call

            for method in ("get_new_connection", "commit", "rollback"):
                setattr(
                    DatabaseWrapper,
                    method,
                    timed(getattr(DatabaseWrapper, method), "db_" + method),
                )
            DatabaseWrapper._haven_load_profile = True
        # Static function names only. These wrappers keep the actual verdicts
        # and execute every original call; nested phase timings overlap.
        from core import middleware, views, protocol

        def wrapped(function, phase):
            def call(*args, **kwargs):
                begin = time.monotonic()
                try:
                    return function(*args, **kwargs)
                finally:
                    TIMINGS.record(phase, time.monotonic() - begin)

            return call

        middleware.resolve_session = wrapped(
            middleware.resolve_session, "session_resolve"
        )
        if importlib.util.find_spec("core.authorization"):
            from core import authorization

            authorization.resolve_session = middleware.resolve_session
        middleware.request_observed = wrapped(
            middleware.request_observed, "operational_counters"
        )
        if hasattr(views, "authorize_current_session"):
            views.authorize_current_session = wrapped(
                views.authorize_current_session, "authority_fence"
            )
        protocol.public_validate = wrapped(
            protocol.public_validate, "native_public_verify"
        )

    def __call__(self, request):
        if not PHASE_PROFILE:
            return self.get_response(request)
        from django.db import connection

        scope = getattr(request, "scope", None) or request.META.get("asgi.scope", {})
        arrived = scope.get("haven_load_arrived")
        started = time.monotonic()
        global CPU_COUNT
        profile = None
        if os.environ.get("HAVEN_LOAD_CPU_PROFILE") == "1" and TIMINGS.enabled.is_set():
            with CPU_LOCK:
                CPU_COUNT += 1
                sample = CPU_COUNT % 25 == 0
            if sample:
                profile = cProfile.Profile()
                profile.enable()
        if arrived is not None:
            TIMINGS.record("asgi_arrival_to_sync_middleware", started - arrived)

        def sql(execute, statement, params, many, context):
            begin = time.monotonic()
            upper = statement.upper()
            category = "locking" if "FOR UPDATE" in upper else "other"
            try:
                return execute(statement, params, many, context)
            finally:
                TIMINGS.record("sql_" + category, time.monotonic() - begin)

        try:
            with connection.execute_wrapper(sql):
                return self.get_response(request)
        finally:
            if profile:
                profile.disable()
                stats = pstats.Stats(profile)
                with CPU_LOCK:
                    for (filename, lineno, function), (
                        primitive,
                        calls,
                        self_time,
                        cumulative,
                        _,
                    ) in stats.stats.items():
                        # Source function names/wall times only, no arguments, locals,
                        # SQL, call graphs, runtime values or full home paths.
                        source = "/".join(Path(filename).parts[-3:])
                        key = (source, lineno, function)
                        row = CPU_ROWS.setdefault(
                            key,
                            {
                                "source": source,
                                "line": lineno,
                                "function": function,
                                "calls": 0,
                                "self_seconds": 0.0,
                                "cumulative_seconds": 0.0,
                            },
                        )
                        row["calls"] += calls
                        row["self_seconds"] += self_time
                        row["cumulative_seconds"] += cumulative
            TIMINGS.record("sync_middleware_total", time.monotonic() - started)


class ASGIProfiler:
    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if not PHASE_PROFILE or scope["type"] != "http":
            return await self.application(scope, receive, send)
        scope["haven_load_arrived"] = started = time.monotonic()

        async def response(message):
            await send(message)
            if message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                TIMINGS.record("asgi_arrival_to_final_body", time.monotonic() - started)

        await self.application(scope, receive, response)
