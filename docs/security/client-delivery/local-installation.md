# Maintained local client installation

The existing HAVEN service at `https://127.0.0.1:8444` and its account/vault state are preserved. No database migration or personal device enrollment is needed for this delivery change.

The source includes a deployable independent frontend and installed-client runtime. A production release is signed only after the implementation source is committed. The operator deployment record below is completed after that signature, installation and live checks; source-level test results are in [verification](verification.md).

The local frontend demonstration uses a distinct loopback IP/origin, TLS leaf and container without backend database credentials or the database network. It shares the development Docker host and therefore does not establish resilience to host-root compromise. The installed client uses an independent local CA and dedicated browser profile; it makes no system trust changes.

The existing backend TEST CA expires November 8, 2026. The existing backend leaf expires November 6, 2026. These are local evaluation certificates; neither new client delivery mode turns them into publicly trusted production TLS. Renew backend/local demonstration leaves before expiry without replacing the trusted roots or changing browser origins. Public deployment needs the independently administered host/signer and trusted TLS described in [operations](operations.md).
