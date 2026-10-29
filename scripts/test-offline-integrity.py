#!/usr/bin/env python3
"""Tamper only a disposable copy; assert verification fails before any Docker command."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
source = Path(os.environ['HAVEN_BUNDLE_DIR']).resolve()
public_key = Path(os.environ['HAVEN_RELEASE_PUBLIC_KEY']).resolve()
results = {}
with tempfile.TemporaryDirectory(prefix='bundle-tamper-', dir=root / '.local') as directory:
    work = Path(directory)
    copied = work / 'bundle'
    shutil.copytree(source, copied)
    marker = work / 'docker-invoked'
    shim = work / 'bin'
    shim.mkdir()
    command = shim / 'docker'
    command.write_text('#!/usr/bin/env python3\nfrom pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\nraise SystemExit(97)\n')
    command.chmod(0o700)
    environment = {**os.environ, 'PATH': str(shim) + os.pathsep + os.environ['PATH'], 'HAVEN_BUNDLE_DIR': str(copied), 'HAVEN_RELEASE_PUBLIC_KEY': str(public_key)}
    def rejected(name):
        result = subprocess.run(['bash', str(root / 'scripts/deploy-offline-bundle.sh')], env=environment, capture_output=True)
        if result.returncode == 0 or marker.exists():
            raise RuntimeError('Tamper verification failed before-image-load requirement: ' + name)
        results[name] = 'REJECTED_BEFORE_DOCKER'
    extra = copied / 'unsigned-extra'
    extra.write_text('This file was not in the signed manifest.\n')
    rejected('added_unsigned_artifact')
    extra.unlink()
    with (copied / 'source.tar.gz').open('ab') as stream:
        stream.write(b'Changed artifact bytes')
    rejected('changed_signed_artifact')
print(json.dumps(results, indent=2))
