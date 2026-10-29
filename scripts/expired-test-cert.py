#!/usr/bin/env python3
"""Generate a deterministic EXPIRED leaf under the disposable local test root, never production PKI."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import ipaddress
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
p=Path(__file__).resolve().parent.parent/'.local/tls'
root=x509.load_pem_x509_certificate((p/'root.crt').read_bytes())
assert 'HAVEN TEST ONLY' in root.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
assert root.not_valid_after_utc-root.not_valid_before_utc <= timedelta(days=7)
key=serialization.load_pem_private_key((p/'root.key').read_bytes(),None)
leaf=serialization.load_pem_private_key((p/'leaf.key').read_bytes(),None)
now=datetime.now(timezone.utc)
cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'EXPIRED TEST ONLY')]))
      .issuer_name(root.subject).public_key(leaf.public_key()).serial_number(x509.random_serial_number())
      .not_valid_before(now-timedelta(days=2)).not_valid_after(now-timedelta(days=1))
      .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
      .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
      .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(key,hashes.SHA256()))
(p/'expired.crt').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
