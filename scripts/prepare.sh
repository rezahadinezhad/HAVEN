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
# Upgrade disposable test configuration without replacing existing secrets.
with open(p) as f:
    configured = f.read()
if 'HAVEN_ROUTING_SECRET=' not in configured:
    with open(p, 'a') as f:
        f.write('\nHAVEN_ROUTING_SECRET='+secrets.token_urlsafe(48)+'\n')
if 'HAVEN_RETIREMENT_REPLAY_SECRET=' not in configured:
    with open(p, 'a') as f:
        f.write('\nHAVEN_RETIREMENT_REPLAY_SECRET='+secrets.token_urlsafe(48)+'\n')
PY
uv sync --project apps/api --frozen --python 3.12
npm ci --prefix apps/web --ignore-scripts
scripts/build-crypto.sh
scripts/build-public-verifier.sh
cargo build --manifest-path packages/crypto-core/Cargo.toml --release --example protocol_client --locked -j 2
NEXT_TELEMETRY_DISABLED=1 npm run build --prefix apps/web
scripts/dev-cert.sh
