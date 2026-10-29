"""Loopback-only integration environment. Does not disable authentication, TLS or cryptography."""

from .settings import *  # noqa: F403
from .settings import ALLOWED_HOSTS, ORIGINS

from urllib.parse import urlsplit

_TEST_HOSTS = {"127.0.0.1", "127.0.0.2", "localhost"}
if (
    not set(ALLOWED_HOSTS)
    or not set(ALLOWED_HOSTS) <= _TEST_HOSTS
    or any(
        urlsplit(origin).scheme != "https" or urlsplit(origin).hostname not in _TEST_HOSTS
        for origin in ORIGINS
    )
):
    raise RuntimeError("Integration settings require isolated loopback IP/localhost origins")
CRYPTO_READY = True
