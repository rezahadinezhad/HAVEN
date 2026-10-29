#!/usr/bin/env python3
"""Prepare disposable local QA credentials, never a fixed-password seed or production account."""
import os,secrets,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
p=root/'.local/ui-credentials.json';p.parent.mkdir(exist_ok=True)
if not p.exists():
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:json.dump({'username':'qa_operator','password':secrets.token_urlsafe(32)},f)
v=json.loads(p.read_text())
subprocess.run([str(root/'apps/api/.venv/bin/python'),'manage.py','bootstrap_admin','--username',v['username']],input=v['password']+'\n',text=True,check=True,cwd=root/'apps/api')
print('Disposable QA account prepared; credentials remain in 0600 .local file.')
