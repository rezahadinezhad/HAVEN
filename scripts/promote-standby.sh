#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${HAVEN_FENCE_ATTESTATION:?Protected operator fencing receipt is required; never infer fencing from a timeout}"
python3 - "$HAVEN_FENCE_ATTESTATION" <<'PY'
import json,sys,stat,hashlib
from pathlib import Path
p=Path(sys.argv[1]);r=json.loads(p.read_text())
assert stat.S_IMODE(p.stat().st_mode)&0o077==0
assert r['version']==1 and r['power_or_provider_fenced'] is True and r['database_network_fenced'] is True
assert all(isinstance(r[k],str) and r[k] for k in ['primary_instance_id','operator','incident_id','evidence_reference'])
print('Operator-attested fencing receipt SHA256: '+hashlib.sha256(p.read_bytes()).hexdigest())
print('This checks receipt structure only; the operator must verify actual provider/network fencing.')
PY
# This is intentionally manual. A receipt cannot substitute for real external fencing evidence.
docker compose --env-file .env -f infrastructure/compose/compose.yml -f infrastructure/compose/standby.yml exec -T --user postgres db pg_ctl -D /var/lib/postgresql/data promote -w
echo 'Database promoted. Keep application services stopped until ciphertext/checkpoint, TLS, release and RPO checks pass.'
echo 'Before reboot, use the reviewed promoted-primary Compose profile. The standby initializer refuses writer restart.'
