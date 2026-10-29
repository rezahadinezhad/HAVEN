#!/usr/bin/env bash
set -euo pipefail
: "${HAVEN_IP:?Actual IP}"
: "${HAVEN_CERT:?Leaf certificate file}"
: "${HAVEN_TRUST_ROOTS:?Verified trust roots file}"
: "${HAVEN_INTERMEDIATE_CHAIN:?Intermediate chain file}"
openssl verify -purpose sslserver -verify_ip "$HAVEN_IP" -CAfile "$HAVEN_TRUST_ROOTS" -untrusted "$HAVEN_INTERMEDIATE_CHAIN" "$HAVEN_CERT"
openssl x509 -checkend "${HAVEN_CERT_GRACE_SECONDS:-172800}" -noout -in "$HAVEN_CERT"
openssl s_client -connect "$HAVEN_IP:${HAVEN_TLS_PORT:-443}" -verify_ip "$HAVEN_IP" -verify_return_error -CAfile "$HAVEN_TRUST_ROOTS" < /dev/null
