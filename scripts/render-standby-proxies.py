#!/usr/bin/env python3
"""Render literal-IP routing. Local mode changes listeners/upstreams only; TLS verification remains mandatory."""
import argparse
import ipaddress
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--primary-connect-ip', required=True)
parser.add_argument('--backup-peer-ip', required=True)
parser.add_argument('--local-test', action='store_true')
a = parser.parse_args()
for value in [a.primary_connect_ip, a.backup_peer_ip]:
    address = ipaddress.IPv4Address(value)
    if address.is_unspecified or address.is_multicast:
        raise SystemExit('An exact reachable private tunnel IP is required')
if a.output.exists():
    raise SystemExit('Refusing to overwrite an existing configuration directory')
a.output.mkdir(parents=True, mode=0o700)
root = Path(__file__).resolve().parent.parent / 'infrastructure/nginx'
values = {'PRIMARY_CONNECT_IP': a.primary_connect_ip, 'BACKUP_PEER_IP': a.backup_peer_ip, 'BRIDGE_LISTEN': '127.0.0.1:9443' if a.local_test else '9443', 'PUBLIC_LISTEN': '127.0.0.2:8447' if a.local_test else '443', 'API_UPSTREAM': '127.0.0.1:8103' if a.local_test else 'api:8100', 'WEB_UPSTREAM': '127.0.0.1:3100' if a.local_test else 'web:3100', 'LOCAL_HARNESS': 'location /__integration__/ { alias /etc/haven/integration/; index index.html; }' if a.local_test else ''}
for name in ['primary-bridge', 'standby-preparation']:
    content = (root / (name + '.conf.template')).read_text()
    for key, value in values.items():
        content = content.replace('@' + key + '@', value)
    if '@' in content:
        raise SystemExit('Unresolved template field')
    target = a.output / (name + '.conf')
    target.write_text(content)
    target.chmod(0o600)
print('Rendered verified-TLS primary bridge and standby preparation routing. Configure firewall and independently trusted certificates before starting.')
