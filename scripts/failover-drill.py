#!/usr/bin/env python3
"""Disposable local primary/streaming-standby drill. Never promotes an existing operator database."""
import hashlib,json,os,re,secrets,subprocess,time,sys,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
IMAGE='postgres:16.14-bookworm@sha256:64154d0babcb1741988719e703419af0382b19953706149f9872fbd0f438efa8'
nonce=secrets.token_hex(6);network='haven-drill-'+nonce;primary=network+'-primary';standby=network+'-standby'
interactive=os.environ.get('HAVEN_DRILL_INTERACTIVE')=='1'
password=os.environ.get('HAVEN_DRILL_PASSWORD') if interactive else secrets.token_hex(32)
if not password or not re.fullmatch(r'[0-9a-f]{64}',password):raise RuntimeError('A random test-only hexadecimal password is required')
replication=secrets.token_hex(32)
created=[]
def interrupted(signum,frame):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,interrupted)
signal.signal(signal.SIGINT,interrupted)

def call(args,input=None,check=True):
    result=subprocess.run(args,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if check and result.returncode:
        failure=ROOT/'.local/last-failover-error.log'
        failure.write_text((result.stdout+result.stderr).decode(errors='replace').replace(password,'[REDACTED]').replace(replication,'[REDACTED]'))
        failure.chmod(0o600)
        raise RuntimeError('Drill command failed (diagnostics in protected .local/last-failover-error.log)')
    return result

def docker(*args,**kw):return call(['docker',*args],**kw)
def query(name,sql):return docker('exec','-i',name,'psql','-U','haven','-d','haven','-qAt','-v','ON_ERROR_STOP=1',input=sql.encode()).stdout.decode().strip()
def wait(name):
    for _ in range(80):
        if docker('exec',name,'psql','-U','haven','-d','haven','-qAt','-c','SELECT 1',check=False).returncode==0:return
        time.sleep(.25)
    result=docker('logs',name,check=False)
    failure=ROOT/'.local/last-failover-container.log'
    failure.write_text((result.stdout+result.stderr).decode(errors='replace').replace(password,'[REDACTED]').replace(replication,'[REDACTED]'))
    failure.chmod(0o600)
    raise RuntimeError('Disposable database did not become ready; protected container diagnostics saved')
def snapshot(name):
    rows=query(name,"SELECT id::text||':'||server_seq::text||':'||encode(ciphertext,'hex')||':'||chain_hash FROM core_messageenvelope ORDER BY id;")
    return {'envelopes':int(query(name,'SELECT count(*) FROM core_messageenvelope;')),'ciphertext_and_order_sha256':hashlib.sha256(rows.encode()).hexdigest()}
try:
    source=os.environ.get('HAVEN_DRILL_SOURCE','haven-test-db-1')
    # Project names may vary for isolated regression runs. Require explicit
    # test-only provenance instead of accepting an arbitrary production source.
    info=json.loads(docker('inspect',source).stdout)[0]
    labels=info['Config'].get('Labels') or {}
    if labels.get('haven.test-only')!='true' or labels.get('com.docker.compose.service')!='db':
        raise RuntimeError('Only a compose database explicitly labelled haven.test-only may be copied')
    dump=docker('exec',source,'pg_dump','-U','haven','-d','haven','--format=custom','--no-owner').stdout
    docker('network','create',* ([] if interactive else ['--internal']),'--label','haven.drill='+nonce,network)
    subnet=json.loads(docker('network','inspect',network).stdout)[0]['IPAM']['Config'][0]['Subnet']
    if not re.fullmatch(r'[0-9./]+',subnet):raise RuntimeError('Invalid isolated network')
    created.append(primary)
    docker('run','-d','--name',primary,'--label','haven.drill='+nonce,'--network',network,'--network-alias','primary',
           *(['-p','127.0.0.1::5432'] if interactive else []),'--tmpfs','/var/lib/postgresql/data:rw,size=512m','-e','POSTGRES_USER=haven','-e','POSTGRES_DB=haven','-e','POSTGRES_PASSWORD='+password,IMAGE)
    wait(primary)
    docker('exec','-i',primary,'pg_restore','--exit-on-error','--clean','--if-exists','--no-owner','-U','haven','-d','haven',input=dump)
    query(primary,f"CREATE ROLE haven_repl WITH REPLICATION LOGIN PASSWORD '{replication}';")
    docker('exec',primary,'sh','-c',f"printf '\nhost replication haven_repl {subnet} scram-sha-256\n' >> /var/lib/postgresql/data/pg_hba.conf")
    query(primary,'SELECT pg_reload_conf();')
    created.append(standby)
    docker('run','-d','--name',standby,'--label','haven.drill='+nonce,'--network',network,'--user','postgres',
           *(['-p','127.0.0.1::5432'] if interactive else []),'--tmpfs','/var/lib/postgresql/data:rw,size=512m,uid=999,gid=999,mode=0700','-e','PGPASSWORD='+replication,
           IMAGE,'bash','-ec','pg_basebackup --checkpoint=fast -h primary -U haven_repl -D /var/lib/postgresql/data -R -X stream -C -S haven_standby; exec postgres -D /var/lib/postgresql/data')
    wait(standby)
    if interactive:
        ports=[int(docker('port',name,'5432/tcp').stdout.decode().strip().split(':')[-1]) for name in [primary,standby]]
        print(json.dumps({'phase':'ready','primary_port':ports[0],'standby_port':ports[1]}),flush=True)
        if sys.stdin.readline().strip()!='PROMOTE':raise RuntimeError('Explicit test promotion command required')
    query(primary,'CREATE TABLE haven_failover_probe (id integer PRIMARY KEY, value text); INSERT INTO haven_failover_probe VALUES (1,\'before_fencing\');')
    lsn=query(primary,'SELECT pg_current_wal_flush_lsn();')
    if not re.fullmatch(r'[0-9A-F]+/[0-9A-F]+',lsn):raise RuntimeError('Invalid WAL checkpoint')
    caught=False
    for _ in range(80):
        if query(standby,f"SELECT pg_last_wal_replay_lsn() >= '{lsn}'::pg_lsn;")=='t':caught=True;break
        time.sleep(.25)
    if not caught:raise RuntimeError('Standby failed to replay committed checkpoint; promotion refused')
    before=snapshot(primary)
    if before['envelopes']==0:raise RuntimeError('No real ciphertext dataset: drill not qualified')
    started=time.monotonic();docker('stop','--time','15',primary)
    if docker('inspect','--format','{{.State.Running}}',primary).stdout.strip()!=b'false':raise RuntimeError('Primary not fenced: promotion refused')
    docker('exec','--user','postgres',standby,'pg_ctl','-D','/var/lib/postgresql/data','promote','-w')
    if query(standby,'SELECT pg_is_in_recovery();')!='f':raise RuntimeError('Promotion failed')
    after=snapshot(standby)
    if before!=after:raise RuntimeError('Ciphertext/order changed across controlled promotion')
    query(standby,"INSERT INTO haven_failover_probe VALUES (2,'after_promotion');")
    if query(standby,'SELECT count(*) FROM haven_failover_probe;')!='2':raise RuntimeError('Post-promotion write failed')
    result={'status':'PASS_LOCAL_DATABASE_DRILL','postgres_image':IMAGE,'primary_fenced_before_promotion':True,
            'replayed_checkpoint':lsn,'before':before,'after':after,'measured_stop_promote_write_seconds':round(time.monotonic()-started,3),
            'controlled_rpo_rows':0,'production_rpo_rto':'UNQUALIFIED','limitations':['single physical host','container-stop fencing only','no provider/tunnel failure proof','no cross-origin browser state transfer claim']}
    target='failover-origin-db.json' if interactive else 'failover-local.json'
    (ROOT/'docs/evidence'/target).write_text(json.dumps(result,indent=2)+'\n')
    if interactive:
        print(json.dumps({'phase':'promoted','result':result}),flush=True)
        if sys.stdin.readline().strip()!='FINISH':raise RuntimeError('Explicit test completion required')
    else:print(json.dumps(result,indent=2))
finally:
    for name in reversed(created):
        label=docker('inspect','--format','{{index .Config.Labels "haven.drill"}}',name,check=False).stdout.decode().strip()
        if label==nonce:docker('rm','-f',name,check=False)
    docker('network','rm',network,check=False)
