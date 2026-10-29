#!/usr/bin/env bash
# Offline-capable after the Trivy database is prepared. No Docker socket is mounted.
set -euo pipefail
cd "$(dirname "$0")/.."
scanner='aquasec/trivy@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c'
work=$(mktemp -d "$PWD/.local/image-scan.XXXXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir -p .local/trivy-cache docs/evidence
for service in api web; do
  docker image save "haven-$service:0.2.0" -o "$work/$service.tar"
  docker run --rm --read-only --cap-drop ALL --user "$(id -u):$(id -g)" \
    --tmpfs /tmp:rw,size=512m,mode=1777 \
    -v "$work:/images:ro" -v "$PWD/.local/trivy-cache:/cache" \
    -v "$PWD/docs/evidence:/reports" "$scanner" image \
    --input "/images/$service.tar" --scanners vuln --format json \
    --output "/reports/$service-container-audit-v2.json" --cache-dir /cache \
    --skip-version-check --timeout 5m ${HAVEN_TRIVY_OFFLINE:+--skip-db-update --skip-java-db-update --offline-scan}
done
python3 - <<'PY'
import json
from pathlib import Path
for service in ['api','web']:
 data=json.loads(Path(f'docs/evidence/{service}-container-audit-v2.json').read_text())
 counts={};fixed={}
 for result in data.get('Results',[]):
  for issue in result.get('Vulnerabilities',[]):
   severity=issue['Severity'];counts[severity]=counts.get(severity,0)+1
   if issue.get('FixedVersion'):fixed[severity]=fixed.get(severity,0)+1
 print(json.dumps({'service':service,'counts':counts,'with_fixed_version':fixed,'report_scope':'scanner database recorded in report; no independent security review'}))
PY
