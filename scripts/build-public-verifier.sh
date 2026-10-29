#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
rustup target add x86_64-unknown-linux-musl
RUSTFLAGS='-C linker=rust-lld' cargo build --manifest-path packages/crypto-core/Cargo.toml --target x86_64-unknown-linux-musl --release --bin haven-public-verify --locked -j 2
mkdir -p packages/crypto-core/bin
cp packages/crypto-core/target/x86_64-unknown-linux-musl/release/haven-public-verify packages/crypto-core/bin/haven-public-verify-x86_64-linux
sha256sum packages/crypto-core/bin/haven-public-verify-x86_64-linux > docs/evidence/public-verifier.sha256
