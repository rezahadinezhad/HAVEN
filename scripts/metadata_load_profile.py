"""Synthetic-only API profiler. No request/SQL text, identifiers or parameters saved."""

import json
import os
from pathlib import Path
import signal
import threading
import time

from metadata_load_instruments import Timings

if (
    os.environ.get("HAVEN_ISOLATED_LOAD") != "synthetic-only"
    or os.environ.get("POSTGRES_PORT") != "55434"
):
    raise RuntimeError("Profiler requires disposable load environment")
FOLDER = Path(os.environ["HAVEN_LOAD_PRIVATE"])
if FOLDER.stat().st_mode & 0o077:
    raise RuntimeError("Private profile folder required")
TIMINGS = Timings()
RESET, SNAPSHOT = threading.Event(), threading.Event()


def write(name, value):
    temporary = FOLDER / (name + ".tmp")
    temporary.write_text(json.dumps(value))
    temporary.replace(FOLDER / name)


def control():
    while True:
        if RESET.wait(0.05):
            RESET.clear()
            TIMINGS.reset()
            write("api-profile-ready.json", {"reset": True})
        if SNAPSHOT.is_set():
            SNAPSHOT.clear()
            TIMINGS.enabled.clear()
            write(
                "api-profile.json",
                {
                    "timings": TIMINGS.snapshot(),
                    "scope": "HTTP middleware SQL plus ASGI arrival/response; process-wide DB connection/commit/rollback timing includes WebSockets; no WebSocket cursor SQL, SQL text, parameters, paths, headers or identifiers; timings overlap, do not sum phases",
                },
            )


signal.signal(signal.SIGUSR2, lambda *_: RESET.set())
signal.signal(signal.SIGUSR1, lambda *_: SNAPSHOT.set())
threading.Thread(target=control, daemon=True).start()


class RequestProfiler:
    def __init__(self, get_response):
        self.get_response = get_response
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

    def __call__(self, request):
        from django.db import connection

        arrived = request.scope.get("haven_load_arrived")
        started = time.monotonic()
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
            TIMINGS.record("sync_middleware_total", time.monotonic() - started)


class ASGIProfiler:
    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.application(scope, receive, send)
        scope["haven_load_arrived"] = started = time.monotonic()

        async def response(message):
            await send(message)
            if message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                TIMINGS.record("asgi_arrival_to_final_body", time.monotonic() - started)

        await self.application(scope, receive, response)
