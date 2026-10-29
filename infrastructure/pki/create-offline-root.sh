#!/usr/bin/env bash
set -euo pipefail
: "${HAVEN_OFFLINE_PKI_DIR:?Absolute protected directory on the isolated signing workstation}"
[[ "$HAVEN_OFFLINE_PKI_DIR" == /* ]] || exit 1
read -r -p 'Confirm this workstation is isolated and never a VPS or CI. Type OFFLINE ROOT: ' answer
[[ "$answer" == 'OFFLINE ROOT' ]] || exit 1
mkdir -p "$HAVEN_OFFLINE_PKI_DIR"
chmod 700 "$HAVEN_OFFLINE_PKI_DIR"
[[ ! -e "$HAVEN_OFFLINE_PKI_DIR/root.key" ]] || { echo 'Root exists; refusing overwrite'; exit 1; }
umask 077
# OpenSSL prompts for a strong encryption passphrase. Never pass it as a command-line argument.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -aes-256-cbc -out "$HAVEN_OFFLINE_PKI_DIR/root.key"
openssl req -new -x509 -sha256 -key "$HAVEN_OFFLINE_PKI_DIR/root.key" -out "$HAVEN_OFFLINE_PKI_DIR/root.crt" -days 730 -subj '/CN=HAVEN controlled private root' -addext 'basicConstraints=critical,CA:TRUE,pathlen:1' -addext 'keyUsage=critical,keyCertSign,cRLSign'
openssl x509 -in "$HAVEN_OFFLINE_PKI_DIR/root.crt" -noout -fingerprint -sha256
echo 'Record root fingerprint and ceremony. Keep root key offline; issue a protected intermediate separately.'
