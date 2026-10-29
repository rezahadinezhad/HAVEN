#!/usr/bin/env bash
set -euo pipefail
: "${HAVEN_IP:?Actual primary private tunnel IPv4}"
: "${HAVEN_LEAF_CSR:?Path to leaf CSR generated on server}"
: "${HAVEN_ISSUER_CERT:?Controlled intermediate certificate}"
: "${HAVEN_ISSUER_KEY:?Protected intermediate key on signing workstation}"
: "${HAVEN_LEAF_OUTPUT:?New output certificate path}"
python3 - <<'PY'
import os,ipaddress
ipaddress.IPv4Address(os.environ['HAVEN_IP'])
PY
openssl x509 -checkend 2592000 -noout -in "$HAVEN_ISSUER_CERT" || { echo "Issuer has less than 30 days remaining; renew it before issuing this leaf"; exit 1; }
[[ ! -e "$HAVEN_LEAF_OUTPUT" ]] || { echo 'Refusing overwrite'; exit 1; }
umask 077
ext=$(mktemp)
trap 'rm -f "$ext"' EXIT
cat > "$ext" <<EXT
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:$HAVEN_IP,DNS:haven-primary
authorityKeyIdentifier=keyid,issuer
subjectKeyIdentifier=hash
EXT
openssl x509 -req -in "$HAVEN_LEAF_CSR" -CA "$HAVEN_ISSUER_CERT" -CAkey "$HAVEN_ISSUER_KEY" -set_serial "0x$(openssl rand -hex 16)" -out "$HAVEN_LEAF_OUTPUT" -days 30 -sha256 -extfile "$ext"
openssl x509 -in "$HAVEN_LEAF_OUTPUT" -noout -dates -ext subjectAltName
