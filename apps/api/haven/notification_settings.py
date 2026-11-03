"""Worker has its own DB login and routing secret, never the application signing key."""

import os
import secrets

# Only satisfies Django's global framework configuration. Not a shared signer;
# no request/session functionality is used by the notification worker.
os.environ.setdefault("HAVEN_SECRET_KEY", secrets.token_urlsafe(48))
from .settings import *  # noqa: E402,F403
