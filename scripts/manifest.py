#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
entries={}
for p in sorted(root.rglob('*')):
    if p.is_symlink():
        raise SystemExit('Symlink rejected')
    if not p.is_file() or str(p.relative_to(root)) in ('MANIFEST.json','MANIFEST.sig'):
        continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    entries[str(p.relative_to(root))]=h.hexdigest()
print(json.dumps({'v':1,'files':entries},sort_keys=True,separators=(',',':')))
