#!/usr/bin/env python3
"""Render-only checks with documentation-range IPs; does not contact or deploy those addresses."""
import os,json,subprocess
from pathlib import Path
env=os.environ.copy();env.update({'HAVEN_DB_TUNNEL_IP':'192.0.2.20','HAVEN_PRIMARY_TUNNEL_IP':'192.0.2.20','HAVEN_PRIMARY_BRIDGE_CONFIG':'/protected/primary-bridge.conf','HAVEN_BRIDGE_TLS_DIR':'/protected/bridge-leaf','HAVEN_STANDBY_PREPARATION_CONFIG':'/protected/standby-preparation.conf','HAVEN_PRIMARY_BRIDGE_ROOTS':'/protected/roots.pem','HAVEN_REPLICATION_PRIMARY_IP':'192.0.2.20','HAVEN_DB_TLS_DIR':'/protected/db-tls','HAVEN_REPLICATION_PASSWORD_FILE':'/protected/replication-pass'})
base=['docker','compose','--env-file','.env','-f','infrastructure/compose/compose.yml'];report={}
for label,overlays in [('primary',['replication-primary.yml','primary-bridge.yml']),('backup',['standby.yml','standby-preparation.yml'])]:
 args=base.copy()
 for name in overlays:args+=['-f','infrastructure/compose/'+name]
 result=subprocess.run(args+['--profile','*','config','--format','json'],env=env,capture_output=True)
 if result.returncode:raise RuntimeError(result.stderr.decode())
 cfg=json.loads(result.stdout)
 report[label]={k:{'profiles':v.get('profiles',[]),'networks':list(v.get('networks',{}))} for k,v in cfg['services'].items()}
 assert 'private' in cfg['services']['db']['networks']
 if label=='backup':
  for name in ['api','outbox','privacy','migrate','prepare-db-roles','redis']:assert cfg['services'][name]['profiles']==['promoted']
  assert 'web' in cfg['services']['ingress']['depends_on'] and 'api' not in cfg['services']['ingress']['depends_on']
  active=json.loads(subprocess.run(args+['config','--format','json'],env=env,check=True,capture_output=True).stdout)['services']
  assert set(active)=={'ingress','web'},set(active)
  report['backup_default_active']=list(active)
Path('docs/evidence/bridge-compose-v2.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: primary/backup overlays render; only web and ingress active by default; replica db explicitly targeted. No public deployment claimed.')
