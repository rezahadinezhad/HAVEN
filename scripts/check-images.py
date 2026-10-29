#!/usr/bin/env python3
"""Inspect only the explicitly built HAVEN images; do not mount secrets or a Docker socket."""
import json
import subprocess
from pathlib import Path

report = {}
for service in ['api', 'web']:
    image = f'haven-{service}:0.2.0'
    metadata = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
    assert metadata['Config']['User'] == ('10001:10001' if service == 'api' else 'node')
    command = '''set -eu
    test ! -e /app/.env
    test -z "$(find /app /usr/local -name '*.key' -o -name 'root.key' 2>/dev/null)"
    '''
    if service == 'api':
        command += '''if command -v pip >/dev/null; then exit 1; fi
        python --version
        if /usr/local/bin/haven-public-verify </dev/null >/dev/null 2>&1; then exit 1; fi
        '''
    else:
        command += '''test ! -e /app/public/pof.html
        test ! -e /app/public/pof.js
        if command -v npm >/dev/null; then exit 1; fi
        node --version
        '''
    result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--entrypoint', 'sh', image, '-c', command], capture_output=True)
    if result.returncode:
        raise RuntimeError('Artifact cleanliness/version check failed for ' + service)
    report[service] = {'image_id': metadata['Id'], 'user': metadata['Config']['User'], 'runtime': result.stdout.decode().strip(), 'no_baked_keys_env_or_package_manager': True}
Path('docs/evidence/image-cleanliness-v2.txt').write_text(json.dumps(report, indent=2) + '\n')
print('PASS nonroot API/web images; absent baked .env/key files and runtime installers; production PoF assets excluded.')
