#!/usr/bin/env python3
import os
import secrets
from pathlib import Path
p=Path(__file__).resolve().parent.parent/'.env'
text=(p.parent/'.env.example').read_text().replace('HAVEN_SECRET_KEY=\n','HAVEN_SECRET_KEY='+secrets.token_urlsafe(64)+'\n').replace('POSTGRES_PASSWORD=\n','POSTGRES_PASSWORD='+secrets.token_urlsafe(32)+'\n')
text=text.replace('HAVEN_DB_MIGRATION_PASSWORD=REPLACE_WITH_48_RANDOM_CHARACTERS','HAVEN_DB_MIGRATION_PASSWORD='+secrets.token_urlsafe(48)).replace('HAVEN_DB_RUNTIME_PASSWORD=REPLACE_WITH_DIFFERENT_48_RANDOM_CHARACTERS','HAVEN_DB_RUNTIME_PASSWORD='+secrets.token_urlsafe(48))
fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:
    f.write(text)
print('Created mode-0600 .env. Configure exact IP origins and certificate directory before deployment.')
