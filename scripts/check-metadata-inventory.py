#!/usr/bin/env python3
"""Offline schema coverage check; opens no database connection and emits no record values."""

import csv
import os
import sys
from pathlib import Path

import django
from django.apps import apps
from django.db.migrations.recorder import MigrationRecorder

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "apps/api"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "haven.settings")

django.setup()

rows = list(
    csv.DictReader((root / "docs/security/metadata-privacy/inventory.csv").open())
)
keys = [(row["model"], row["field"]) for row in rows]
assert len(keys) == len(set(keys)), "Duplicate inventory field"
current = {
    (model._meta.label, field.name)
    for model in [
        *apps.get_models(include_auto_created=True),
        MigrationRecorder.Migration,
    ]
    for field in [*model._meta.local_fields, *model._meta.local_many_to_many]
}
listed = {(row["model"], row["field"]) for row in rows if row["column"] != "REMOVED"}
assert current == listed, (
    f"Inventory drift: missing={current - listed}; stale={listed - current}"
)
for row in rows:
    assert row["classification"] in {
        "REQUIRED",
        "REDUCIBLE",
        "REPLACEABLE",
        "REMOVABLE",
    }
    assert all(
        row[key]
        for key in ["purpose", "sensitivity", "api_exposure", "retention", "source"]
    )
print(
    f"PASS: {len(current)} current and {len(rows) - len(current)} retired fields classified; no record data read"
)
