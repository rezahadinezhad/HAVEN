#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(wasm-bindgen --version) == 'wasm-bindgen 0.2.105' ]] || { echo 'Install wasm-bindgen-cli 0.2.105 --locked'; exit 1; }
cargo build --manifest-path packages/crypto-core/Cargo.toml --target wasm32-unknown-unknown --lib --release --locked -j 2
wasm-bindgen packages/crypto-core/target/wasm32-unknown-unknown/release/haven_crypto_core.wasm --target web --out-dir apps/web/public/crypto --out-name haven_crypto
node scripts/build-client.mjs
sha256sum apps/web/public/crypto/* apps/web/public/crypto-worker.js apps/web/public/vault-worker.js > docs/evidence/crypto-assets.sha256
