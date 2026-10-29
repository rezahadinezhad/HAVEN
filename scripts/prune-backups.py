#!/usr/bin/env python3
"""Review/apply encrypted backup rotation; never deletes the minimum recovery copies."""

import argparse
import hashlib
import json
import re
import stat
import time
from pathlib import Path


def plan(directory, days=7, keep=3):
    if directory.is_symlink() or not directory.is_dir() or not directory.is_absolute():
        raise ValueError("Use an absolute, nonsymlink backup directory")
    if stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise ValueError("Backup directory must have mode 0700")
    candidates = []
    for path in directory.iterdir():
        if not re.fullmatch(r"haven-\d{8}T\d{6}Z\.sql\.gpg", path.name):
            continue
        checksum = path.with_name(path.name + ".sha256")
        if path.is_symlink() or checksum.is_symlink() or not path.is_file() or not checksum.is_file():
            raise ValueError("Backup pair must contain regular nonsymlink files")
        expected = checksum.read_text().split()[0]
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or expected != actual or path.stat().st_size == 0:
            raise ValueError("Checksum/empty backup failure: rotation stopped")
        candidates.append(path)
    candidates.sort(key=lambda path: path.name, reverse=True)
    cutoff = time.time() - days * 86400
    # An mtime in the future or a recently copied old archive is conservatively kept.
    return [path for path in candidates[keep:] if path.stat().st_mtime < cutoff]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--days", type=int, default=7, choices=range(1, 31))
    parser.add_argument("--keep", type=int, default=3, choices=range(3, 101))
    parser.add_argument("--apply", action="store_true", help="Delete only the reviewed obsolete archive/checksum pairs")
    args = parser.parse_args()
    try:
        paths = plan(args.directory, args.days, args.keep)
    except (ValueError, OSError, IndexError):
        raise SystemExit("Backup rotation failed closed: check directory permissions, pairs and checksums") from None
    if args.apply:
        for path in paths:
            path.unlink()
            path.with_name(path.name + ".sha256").unlink()
    print(json.dumps({"mode": "applied" if args.apply else "dry_run", "archives": [p.name for p in paths],
                      "minimum_kept": args.keep, "retention_days": args.days,
                      "notice": "Checksums do not prove decryptability or successful restore. Keep a separately protected verified recovery copy."}))


if __name__ == "__main__":
    main()
