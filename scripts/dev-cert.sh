#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .local/tls
umask 077
if [[ -e .local/tls/root.key ]]; then
  echo 'Existing development PKI preserved; remove deliberately to regenerate.'
  exit 0
fi
openssl req -x509 -newkey rsa:3072 -nodes -keyout .local/tls/root.key -out .local/tls/root.crt -days 7 -sha256 -subj '/CN=HAVEN TEST ONLY root' -addext 'basicConstraints=critical,CA:TRUE,pathlen:0' -addext 'keyUsage=critical,keyCertSign,cRLSign'
openssl req -newkey rsa:2048 -nodes -keyout .local/tls/leaf.key -out .local/tls/leaf.csr -subj '/CN=HAVEN DEVELOPMENT ONLY'
cat > .local/tls/extensions <<'EXT'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:127.0.0.1
EXT
openssl x509 -req -in .local/tls/leaf.csr -CA .local/tls/root.crt -CAkey .local/tls/root.key -CAcreateserial -out .local/tls/leaf.crt -days 3 -sha256 -extfile .local/tls/extensions
openssl verify -CAfile .local/tls/root.crt -verify_ip 127.0.0.1 .local/tls/leaf.crt
openssl x509 -in .local/tls/root.crt -noout -fingerprint -sha256
echo 'TEST ONLY. Root key remains local for disposable tests; never deploy this CA.'
