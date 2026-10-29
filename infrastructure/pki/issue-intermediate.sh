#!/usr/bin/env bash
set -euo pipefail
: "${HAVEN_OFFLINE_PKI_DIR:?Offline root directory required}"
: "${HAVEN_INTERMEDIATE_DIR:?Protected intermediate output directory required}"
[[ "$HAVEN_OFFLINE_PKI_DIR" == /* && "$HAVEN_INTERMEDIATE_DIR" == /* ]] || exit 1
[[ -f "$HAVEN_OFFLINE_PKI_DIR/root.crt" && -f "$HAVEN_OFFLINE_PKI_DIR/root.key" ]] || exit 1
[[ ! -e "$HAVEN_INTERMEDIATE_DIR" ]] || { echo 'Refusing overwrite of intermediate directory'; exit 1; }
openssl x509 -checkend 15552000 -noout -in "$HAVEN_OFFLINE_PKI_DIR/root.crt" || { echo "Renew root before issuing a 180-day intermediate"; exit 1; }
umask 077
mkdir -p "$HAVEN_INTERMEDIATE_DIR"
chmod 700 "$HAVEN_INTERMEDIATE_DIR"
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -aes-256-cbc -out "$HAVEN_INTERMEDIATE_DIR/intermediate.key"
openssl req -new -sha256 -key "$HAVEN_INTERMEDIATE_DIR/intermediate.key" -out "$HAVEN_INTERMEDIATE_DIR/intermediate.csr" -subj '/CN=HAVEN controlled issuing intermediate'
ext=$(mktemp)
trap 'rm -f "$ext"' EXIT
cat > "$ext" <<'EXT'
basicConstraints=critical,CA:TRUE,pathlen:0
keyUsage=critical,keyCertSign,cRLSign
authorityKeyIdentifier=keyid,issuer
subjectKeyIdentifier=hash
EXT
openssl x509 -req -in "$HAVEN_INTERMEDIATE_DIR/intermediate.csr" -CA "$HAVEN_OFFLINE_PKI_DIR/root.crt" -CAkey "$HAVEN_OFFLINE_PKI_DIR/root.key" -set_serial "0x$(openssl rand -hex 16)" -sha256 -days 180 -extfile "$ext" -out "$HAVEN_INTERMEDIATE_DIR/intermediate.crt"
openssl verify -CAfile "$HAVEN_OFFLINE_PKI_DIR/root.crt" "$HAVEN_INTERMEDIATE_DIR/intermediate.crt"
echo 'Keep root and intermediate signing keys off every server. Leaf validity must end before the issuer expires.'
