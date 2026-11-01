import os,sys,secrets
from pathlib import Path
sys.path.insert(0,str(Path('apps/api').resolve()))
os.environ['HAVEN_SECRET_KEY']=secrets.token_hex(32)
os.environ['DJANGO_SETTINGS_MODULE']='haven.settings'
from django.conf import settings
settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}
settings.CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache'}}
settings.MIGRATION_MODULES={k:None for k in ('core','auth','contenttypes','sessions')}
import django
django.setup()
import pytest
sys.exit(pytest.main(['apps/api/core/tests/test_credential_sessions.py','apps/api/core/tests/test_friend_invitations.py','-q','-k','not concurrent and not migration']))
