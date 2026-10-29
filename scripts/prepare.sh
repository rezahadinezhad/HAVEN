#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .local
python3 - <<'PY'
import secrets,os
p='.local/test.env'
if not os.path.exists(p):
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:
        f.write('HAVEN_SECRET_KEY='+secrets.token_urlsafe(64)+'\nPOSTGRES_PASSWORD='+secrets.token_urlsafe(32)+'\n')
PY
uv sync --project apps/api --frozen --python 3.12
npm ci --prefix apps/web --ignore-scripts
scripts/build-crypto.sh
scripts/build-public-verifier.sh
NEXT_TELEMETRY_DISABLED=1 npm run build --prefix apps/web
scripts/dev-cert.sh
