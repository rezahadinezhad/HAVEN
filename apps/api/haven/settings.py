import os
import ipaddress
import re
from urllib.parse import urlsplit
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("HAVEN_SECRET_KEY", "")
if len(SECRET_KEY) < 48:
    raise ImproperlyConfigured("HAVEN_SECRET_KEY must contain at least 48 random characters")
DEBUG = False
ALLOWED_HOSTS = os.environ.get("HAVEN_HOSTS", "127.0.0.1").split(",")
ORIGINS = os.environ.get("HAVEN_ORIGINS", "https://127.0.0.1:8443").split(",")
OPTIONAL_HOSTNAME = os.environ.get("HAVEN_OPTIONAL_HOSTNAME", "")
# Preserve literal IPv4 as the default and required route. One exact hostname
# can be opted in for WebAuthn PRF; it is never a wildcard or TLS bypass.


def exact_hostname(value):
    if not value or len(value) > 253 or value != value.lower():
        return False
    labels = value.split(".")
    return all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)


try:
    if OPTIONAL_HOSTNAME and not exact_hostname(OPTIONAL_HOSTNAME):
        raise ValueError("invalid optional hostname")
    ip_hosts = []
    for host in ALLOWED_HOSTS:
        if host == OPTIONAL_HOSTNAME and OPTIONAL_HOSTNAME:
            continue
        ip_hosts.append(str(ipaddress.IPv4Address(host)))
        if ip_hosts[-1] != host:
            raise ValueError("non-canonical IPv4 host")
    if not ip_hosts or len(set(ALLOWED_HOSTS)) != len(ALLOWED_HOSTS):
        raise ValueError("IPv4 host required or duplicate host")
    if OPTIONAL_HOSTNAME and OPTIONAL_HOSTNAME not in ALLOWED_HOSTS:
        raise ValueError("optional hostname missing from hosts")
    origin_hosts = set()
    for origin in ORIGINS:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in ALLOWED_HOSTS
            or parsed.netloc not in (parsed.hostname, f"{parsed.hostname}:{parsed.port}")
            or parsed.port == 0
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError("invalid origin")
        origin_hosts.add(parsed.hostname)
    if not (set(ip_hosts) & origin_hosts) or (OPTIONAL_HOSTNAME and OPTIONAL_HOSTNAME not in origin_hosts):
        raise ValueError("required exact origin missing")
except ValueError:
    raise ImproperlyConfigured(
        "Configure exact HTTPS IPv4 origins and, only if opted in, one exact HTTPS hostname origin"
    ) from None

CSRF_TRUSTED_ORIGINS = ORIGINS
ROOT_URLCONF = "haven.urls"
ASGI_APPLICATION = "haven.asgi.application"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "channels",
    "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "core.middleware.SessionMiddleware",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "haven"),
        "USER": os.environ.get("POSTGRES_USER", "haven"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "55432"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"options": "-c synchronous_commit=on"},
    }
}
AUTH_USER_MODEL = "core.User"
PASSWORD_HASHERS = ["core.hashers.HavenArgon2Hasher"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 14}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "KEY_PREFIX": "haven-json-v1",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:56379/1"),
        "OPTIONS": {
            "serializer": "core.cache_serializer.JSONCacheSerializer",
            "socket_connect_timeout": 1,
            "socket_timeout": 1,
        },
    }
}
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://127.0.0.1:56379/0")],
            "capacity": 100,
            "expiry": 30,
            # Bound stale account-to-channel links after a crashed connection.
            # Authenticated heartbeats refresh this; HTTP remains authoritative.
            "group_expiry": 120,
        },
    }
}
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.auth.CookieAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "core.errors.handler",
    "UNAUTHENTICATED_USER": None,
}
SESSION_COOKIE_NAME = "__Host-haven"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_NAME = "__Host-haven-csrf"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_FAILURE_VIEW = "core.errors.csrf_failure"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1500000
FILE_UPLOAD_MAX_MEMORY_SIZE = 1100000
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
APP_NAME = os.environ.get("HAVEN_NAME", "HAVEN")
CRYPTO_READY = False  # Release gate: integration is never enabled by an environment switch.
MAINTENANCE = os.environ.get("HAVEN_MAINTENANCE", "")
# Avoid tracebacks/queries/payloads in application logs. Security audit events use a bounded schema.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {
        "django.request": {"handlers": ["null"], "propagate": False},
        "django.db.backends": {"handlers": ["null"], "propagate": False},
        "django.security": {"handlers": ["null"], "propagate": False},
        "uvicorn.error": {"handlers": ["null"], "propagate": False},
        "uvicorn.access": {"handlers": ["null"], "propagate": False},
    },
}

# Fixed conservative defaults; publishing policy avoids invisible retention changes.
DELIVERED_CIPHERTEXT_GRACE_HOURS = 24
ATTACHMENT_RETENTION_DAYS = 7
AUDIT_RETENTION_DAYS = 7

MLS_PUBLIC_VERIFIER = os.environ.get(
    "MLS_PUBLIC_VERIFIER",
    str(BASE_DIR.parent.parent / "packages/crypto-core/bin/haven-public-verify-x86_64-linux"),
)

# Logical budgets include conservative per-row/index overhead. Physical disk/WAL
# capacity must exceed the logical service limit (see storage runbook).
MESSAGE_ACCOUNT_BYTES = 256 * 1024 * 1024
MESSAGE_ACCOUNT_PENDING_BYTES = 64 * 1024 * 1024
MESSAGE_SERVICE_BYTES = 5 * 1024 * 1024 * 1024
MESSAGE_ACCOUNT_ENVELOPES = 100000
MESSAGE_SERVICE_ENVELOPES = 2000000
MAX_OWNED_CONVERSATIONS = 500
