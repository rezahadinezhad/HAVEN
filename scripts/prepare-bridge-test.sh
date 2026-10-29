#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
openssl x509 -in .local/tls/root.crt -noout -subject | grep -q 'HAVEN TEST ONLY root' || { echo 'Disposable TEST CA required'; exit 1; }
[[ ! -e .local/bridge-test-tls ]] || { [[ -f .local/bridge-test-tls/backup/leaf.crt ]] && { echo 'Existing bridge TEST certificates preserved'; exit 0; }; echo 'Incomplete test PKI preserved; create backup leaf deliberately'; exit 1; }
umask 077
mkdir -m 700 .local/bridge-test-tls
openssl req -new -newkey rsa:2048 -nodes -keyout .local/bridge-test-tls/leaf.key -out .local/bridge-test-tls/valid.csr -subj '/CN=haven-primary' > /dev/null 2>&1
openssl req -new -key .local/bridge-test-tls/leaf.key -out .local/bridge-test-tls/wrong.csr -subj '/CN=wrong-primary' > /dev/null 2>&1
for kind in valid wrong; do
  identity=haven-primary
  [[ "$kind" == valid ]] || identity=wrong-primary
  cat > ".local/bridge-test-tls/$kind.ext" <<EXT
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:$identity,IP:127.0.0.1
EXT
  openssl x509 -req -in ".local/bridge-test-tls/$kind.csr" -CA .local/tls/root.crt -CAkey .local/tls/root.key -set_serial "0x$(openssl rand -hex 16)" -days 1 -sha256 -extfile ".local/bridge-test-tls/$kind.ext" -out ".local/bridge-test-tls/$kind.crt" > /dev/null 2>&1
done
cp .local/bridge-test-tls/valid.crt .local/bridge-test-tls/leaf.crt
openssl verify -CAfile .local/tls/root.crt -verify_hostname haven-primary .local/bridge-test-tls/leaf.crt
openssl verify -CAfile .local/tls/root.crt -verify_ip 127.0.0.1 .local/bridge-test-tls/leaf.crt
echo 'TEST ONLY private bridge leaves prepared. No CA signing key will be mounted in containers.'

# A distinct backup IP gives browsers genuinely separate origins/cookie scopes.
mkdir -p .local/bridge-test-tls/backup
openssl req -new -newkey rsa:2048 -nodes -keyout .local/bridge-test-tls/backup/leaf.key -out .local/bridge-test-tls/backup/leaf.csr -subj '/CN=HAVEN BACKUP TEST ONLY' > /dev/null 2>&1
cat > .local/bridge-test-tls/backup/leaf.ext <<'EXT'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:127.0.0.2
EXT
openssl x509 -req -in .local/bridge-test-tls/backup/leaf.csr -CA .local/tls/root.crt -CAkey .local/tls/root.key -set_serial "0x$(openssl rand -hex 16)" -days 1 -sha256 -extfile .local/bridge-test-tls/backup/leaf.ext -out .local/bridge-test-tls/backup/leaf.crt > /dev/null 2>&1
openssl verify -CAfile .local/tls/root.crt -verify_ip 127.0.0.2 .local/bridge-test-tls/backup/leaf.crt
