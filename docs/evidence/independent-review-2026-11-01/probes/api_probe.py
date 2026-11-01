import os, sys, json, secrets, uuid
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path('apps/api').resolve()))
os.environ['HAVEN_SECRET_KEY'] = secrets.token_hex(32)
os.environ['DJANGO_SETTINGS_MODULE'] = 'haven.settings'
from django.conf import settings
settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}
settings.CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache'}}
settings.MIGRATION_MODULES={k:None for k in ('core','auth','contenttypes','sessions')}
settings.CRYPTO_READY=True
import django
django.setup()
from django.core.management import call_command
call_command('migrate',run_syncdb=True,verbosity=0)
from core import models as m
from core.middleware import digest
from django.utils import timezone
from rest_framework.test import APIClient
from django.db import connection
from django.test.utils import CaptureQueriesContext
u=m.User.objects.create_user(username='review-user',password=secrets.token_urlsafe(30),display_name='Review')
d=m.Device.objects.create(user=u,label='review',identity='review',public_key=b'x'*32,trust_state='approved',challenge='x',expires_at=timezone.now()+timedelta(days=1))
token=secrets.token_urlsafe(48)
m.Session.objects.create(user=u,device=d,token_hash=digest(token),expires_at=timezone.now()+timedelta(hours=1))
c=APIClient(enforce_csrf_checks=True)
c.defaults.update(HTTP_HOST='127.0.0.1:8443',HTTP_ORIGIN='https://127.0.0.1:8443')
c.cookies[settings.SESSION_COOKIE_NAME]=token
for n in range(101):
 cv=m.Conversation.objects.create(kind='group',creator=d,group_id=str(uuid.uuid4()))
 m.Membership.objects.create(conversation=cv,device=d,valid_from_epoch=0)
listed=c.get('/api/v1/conversations',secure=True).json()
synced=c.get('/api/v1/sync',secure=True).json()['conversations']
print(json.dumps({'check':'conversation_pagination','actual':101,'list_count':len(listed),'sync_count':len(synced),'list_sync_overlap':len({x['id'] for x in listed}&{x['id'] for x in synced})}))
for n in range(100):
 m.MessageEnvelope.objects.create(conversation=cv,sender_device=d,server_seq=n+1,client_message_id=uuid.uuid4(),group_epoch=0,ciphertext=b'x'*150000,request_digest='x')
with CaptureQueriesContext(connection) as q:
 r=c.get(f'/api/v1/conversations/{cv.pk}/proofs',secure=True)
selects=[x['sql'] for x in q if 'core_messageenvelope' in x['sql']]
print(json.dumps({'check':'proof_fetch','status':r.status_code,'proof_count':len(r.json()['proofs']),'ciphertext_selected':any('"ciphertext"' in x for x in selects),'unneeded_ciphertext_bytes':15000000}))
# Reproduce the real rate helper deterministically without running password hashing 300 times.
from core.views import rate
from django.core.cache import cache
from types import SimpleNamespace
cache.clear()
req=SimpleNamespace(user=None,META={'REMOTE_ADDR':'test'})
for _ in range(300): rate(req,'login.total',300,identity='service')
csrf=c.get('/api/v1/auth/csrf',secure=True).json()['csrf']
r=c.post('/api/v1/auth/login',{'username':'unrelated-user','password':'synthetic'},format='json',secure=True,HTTP_X_CSRFTOKEN=csrf)
print(json.dumps({'check':'global_login_exhaustion','unrelated_login_status':r.status_code}))
