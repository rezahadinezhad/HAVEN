#!/usr/bin/env python3
import os,sys,secrets,hashlib,subprocess,uuid
from pathlib import Path
from datetime import timedelta
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'apps/api'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','haven.settings')
import django
django.setup()
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from core import models as m
command=['docker','compose','--env-file',str(root/'.local/test.env'),'-f',str(root/'infrastructure/compose.test.yml')]
# This is a delivery-service fixture, not an E2EE product test. Roll back generated data afterwards.
with transaction.atomic(),override_settings(CRYPTO_READY=True):
    user=m.User.objects.create_user(username='drill_'+uuid.uuid4().hex[:12],password=secrets.token_urlsafe(30),display_name='Drill')
    d=m.Device.objects.create(user=user,label='drill',identity='test-only',public_key=secrets.token_bytes(32),trust_state='approved',challenge='drill',expires_at=timezone.now()+timedelta(hours=1))
    token=secrets.token_urlsafe(48)
    m.Session.objects.create(user=user,device=d,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(hours=1))
    conv=m.Conversation.objects.create(kind='direct',creator=d,group_id=uuid.uuid4().hex,last_seq=1)
    m.Membership.objects.create(conversation=conv,device=d,valid_from_epoch=0)
    m.MessageEnvelope.objects.create(conversation=conv,sender_device=d,server_seq=1,client_message_id=uuid.uuid4(),group_epoch=0,ciphertext=secrets.token_bytes(120),request_digest='test')
    client=APIClient();client.defaults['HTTP_HOST']='127.0.0.1:8443';client.cookies['__Host-haven']=token
    subprocess.run(command+['stop','redis'],check=True,stdout=subprocess.DEVNULL)
    result=client.get(f'/api/v1/conversations/{conv.pk}/messages',secure=True)
    assert result.status_code==200 and len(result.json()['messages'])==1
    print('PASS: PostgreSQL-backed existing-session HTTP delta sync survives actual test Redis stop (opaque fixture only)')
    transaction.set_rollback(True)
subprocess.run(command+['start','redis'],check=True,stdout=subprocess.DEVNULL)
