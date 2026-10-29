#!/usr/bin/env bash
# Run the unchanged OpenMLS 0.9.2 protocol KATs against the backported provider.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/check-crypto-vendor.py
revision=8a8f83b4b61fc45f28facec25e914992b3465de6
archive=.local/upstream-kats/openmls.tar.gz
mkdir -p .local/upstream-kats
if [[ ! -f "$archive" ]]; then
  curl --fail --location --silent --show-error "https://codeload.github.com/openmls/openmls/tar.gz/$revision" -o "$archive"
fi
echo "0d206348ff7fc1e72bf47c1b37ba39a4b176be5cb602604d44a25aab21541f33  $archive" | sha256sum --check
python3 - <<'PY'
from pathlib import Path
import shutil, tarfile
root=Path.cwd(); workspace=root/'.local/provider-vectors/openmls-8a8f83b4b61fc45f28facec25e914992b3465de6'
if not workspace.exists():
    with tarfile.open(root/'.local/upstream-kats/openmls.tar.gz') as source:
        source.extractall(workspace.parent,filter='data')
for name in ('openmls_rust_crypto','basic_credential'):
    src=root/'packages/crypto-core/vendor'/name; dst=workspace/name
    shutil.rmtree(dst/'src')
    shutil.copytree(src/'src',dst/'src')
    manifest=(src/'Cargo.toml').read_text()
    replacements={
        'openmls_traits = { version = "=0.6.0" }':'openmls_traits = { workspace = true }',
        'openmls_memory_storage = { version = "=0.6.0" }':'openmls_memory_storage = { workspace = true }',
    }
    for a,b in replacements.items():manifest=manifest.replace(a,b)
    (dst/'Cargo.toml').write_text(manifest)
PY
cd ".local/provider-vectors/openmls-$revision"
# Resolve this disposable upstream test workspace separately from HAVEN's lockfile.
cargo generate-lockfile > resolve.log 2>&1
cargo test -p openmls --lib --locked --features test-utils kats -j 2
