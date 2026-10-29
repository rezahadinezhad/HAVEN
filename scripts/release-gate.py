#!/usr/bin/env python3
"""Fail closed: a runtime environment variable cannot qualify a release."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parent.parent
print('BLOCKED: complete acceptance, independent review, physical browsers, public-IP TLS, provider failover and field qualification outstanding.')
print('Local integrated MLS tests do not authorize high-risk onboarding. See '+str(root/'SECURITY_STATUS.md'))
sys.exit(1)
