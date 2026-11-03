"""Bound the API's process and database budgets before starting Uvicorn."""

import argparse
import os


def runtime_limits(environ):
    try:
        workers = int(environ.get("HAVEN_API_WORKERS", "4"))
        if not 1 <= workers <= 8:
            raise ValueError
        pool_size = int(environ.get("HAVEN_DB_POOL_SIZE", str(min(16, 64 // workers))))
        if not 0 <= pool_size <= 32 or workers * pool_size > 64:
            raise ValueError
    except ValueError:
        raise ValueError(
            "Use 1–8 HAVEN_API_WORKERS and 0–32 HAVEN_DB_POOL_SIZE; "
            "their product must not exceed 64 connections"
        ) from None
    return workers, pool_size


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--forwarded-allow-ips", default="127.0.0.1")
    args = parser.parse_args()
    try:
        workers, pool_size = runtime_limits(os.environ)
    except ValueError as error:
        parser.error(str(error))
    os.environ["HAVEN_API_WORKERS"] = str(workers)
    os.environ["HAVEN_DB_POOL_SIZE"] = str(pool_size)
    if os.environ.get("HAVEN_RETIREMENT_JOURNAL_DIR"):
        import django

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "haven.runtime_settings")
        django.setup()
        from core.retirement_journal import reconcile

        reconcile()  # Fail closed before accepting traffic after SQL restoration.
        from django.db import connection

        connection.close()
        connection.close_pool()
    import uvicorn

    uvicorn.run(
        "haven.asgi:application",
        host=args.host,
        port=args.port,
        workers=workers,
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips=args.forwarded_allow_ips,
        ws_max_size=2048,
    )


if __name__ == "__main__":
    main()
