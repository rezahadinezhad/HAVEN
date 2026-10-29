#!/usr/bin/env bash
# Upstream code at the exact VCS commit embedded in the locked openmls 0.9.2 crate.
set -euo pipefail
cd "$(dirname "$0")/.."
revision=8a8f83b4b61fc45f28facec25e914992b3465de6
archive=.local/upstream-kats/openmls.tar.gz
mkdir -p .local/upstream-kats
if [[ ! -f "$archive" ]]; then
  curl --fail --location --silent --show-error "https://codeload.github.com/openmls/openmls/tar.gz/$revision" -o "$archive"
fi
echo "0d206348ff7fc1e72bf47c1b37ba39a4b176be5cb602604d44a25aab21541f33  $archive" | sha256sum --check
if [[ ! -d .local/upstream-kats/openmls-$revision ]]; then tar -xzf "$archive" -C .local/upstream-kats; fi
cd ".local/upstream-kats/openmls-$revision"
cargo test -p openmls --lib --locked --features test-utils kats -j 2
