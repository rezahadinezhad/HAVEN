#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
[[ -f .local/tls/root.crt && -f .local/tls/root.key ]] || {
  echo 'Disposable test root missing. Run scripts/dev-cert.sh and explicitly trust that root in an isolated test browser.' >&2
  exit 1
}
if [[ -f .local/tls/localhost-test.crt && -f .local/tls/localhost-test.key ]] \
  && openssl x509 -in .local/tls/localhost-test.crt -checkend 3600 -noout >/dev/null 2>&1 \
  && openssl verify -CAfile .local/tls/root.crt -verify_hostname localhost .local/tls/localhost-test.crt >/dev/null 2>&1 \
  && openssl verify -CAfile .local/tls/root.crt -verify_ip 127.0.0.1 .local/tls/localhost-test.crt >/dev/null 2>&1; then
  exit 0
fi
openssl req -newkey rsa:2048 -nodes -keyout .local/tls/localhost-test.key \
  -out .local/tls/localhost-test.csr -subj '/CN=localhost' -batch >/dev/null 2>&1
cat > .local/tls/localhost-test.ext <<'EXT'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,IP:127.0.0.1
EXT
openssl x509 -req -in .local/tls/localhost-test.csr \
  -CA .local/tls/root.crt -CAkey .local/tls/root.key -CAcreateserial \
  -out .local/tls/localhost-test.crt -days 1 -sha256 \
  -extfile .local/tls/localhost-test.ext >/dev/null 2>&1
openssl verify -CAfile .local/tls/root.crt -verify_hostname localhost .local/tls/localhost-test.crt
openssl verify -CAfile .local/tls/root.crt -verify_ip 127.0.0.1 .local/tls/localhost-test.crt
echo 'Disposable localhost/IP test leaf prepared; it is not a public deployment certificate.'
