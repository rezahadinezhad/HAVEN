#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .local/tls/root.crt ]] || { echo 'Run make prepare first'; exit 1; }
# Certutil imports ONLY into private test profiles, never the OS or personal browser.
for profile in .local/browser-home/.pki/nssdb .local/browser-home/.local/share/pki/nssdb .local/firefox-profile; do
 mkdir -m 700 -p "$profile"
 [[ -f "$profile/cert9.db" ]] || certutil -N -d "sql:$profile" --empty-password
 certutil -D -d "sql:$profile" -n 'HAVEN TEST ONLY' 2>/dev/null || true
 certutil -A -d "sql:$profile" -n 'HAVEN TEST ONLY' -t 'C,,' -i .local/tls/root.crt
done
set -a
source .local/test.env
set +a
apps/api/.venv/bin/python - <<'PY'
import os,sys,secrets,json
from pathlib import Path
sys.path.insert(0,'apps/api');os.environ.setdefault('DJANGO_SETTINGS_MODULE','haven.settings')
import django
django.setup()
from core.models import User
p=Path('.local/ui-credentials.json')
if p.exists():
 d=json.loads(p.read_text())
 u=User.objects.get(username=d['username'])
 assert u.check_password(d['password']) and u.role=='superadmin'
else:
 d={'username':'qa_'+secrets.token_hex(6),'password':secrets.token_urlsafe(48)}
 User.objects.create_user(**d,display_name='Disposable test operator',role='superadmin')
 fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as f:json.dump(d,f)
print('Disposable QA account ready; credentials retained in protected local file only.')
PY

bash scripts/prepare-bridge-test.sh
