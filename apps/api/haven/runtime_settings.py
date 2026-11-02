"""ASGI database reuse. Management/migration commands retain base settings."""

from copy import deepcopy
import os
from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403
from .settings import DATABASES as BASE_DATABASES, LOGGING as BASE_LOGGING
from .server import runtime_limits

DATABASES = deepcopy(BASE_DATABASES)
LOGGING = deepcopy(BASE_LOGGING)
# Keep values in bind parameters, including in idle pg_stat_activity SQL text.
DATABASES["default"]["OPTIONS"]["server_side_binding"] = True
try:
    _, _pool_size = runtime_limits(os.environ)
except ValueError as error:
    raise ImproperlyConfigured(str(error)) from None
if _pool_size:
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
    DATABASES["default"]["OPTIONS"]["pool"] = {
        "min_size": 1,
        "max_size": _pool_size,
        "timeout": 3,
        "max_waiting": 64,
        "max_idle": 60,
        "max_lifetime": 600,
    }
# Pool failures must not introduce unbounded connection/DSN diagnostics.
LOGGING["loggers"]["psycopg.pool"] = {"handlers": ["null"], "propagate": False}
