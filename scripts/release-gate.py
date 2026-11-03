#!/usr/bin/env python3
"""Check normal-product activation separately from independent qualification."""

import argparse
import ast
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--qualification",
    action="store_true",
    help="Require external release qualification",
)
options = parser.parse_args()
if options.qualification:
    print(
        "PENDING: independent security review, physical browsers and deployment qualification."
    )
    print("See " + str(root / "SECURITY_STATUS.md"))
    sys.exit(1)
assignments = {
    node.targets[0].id: node.value.value
    for node in ast.parse((root / "apps/api/haven/settings.py").read_text()).body
    if isinstance(node, ast.Assign)
    and isinstance(node.targets[0], ast.Name)
    and isinstance(node.value, ast.Constant)
}
required = ("CRYPTO_READY", "CONVERSATION_CLOSURE_READY", "GRAPH_RETIREMENT_READY")
if not all(assignments.get(name) is True for name in required):
    sys.exit("Normal-product activation is disabled")
print(
    "ACTIVE_REVIEW_PENDING: normal messaging, account-wide closure and retirement are enabled."
)
print(
    "Independent qualification is tracked separately; use --qualification to require it."
)
