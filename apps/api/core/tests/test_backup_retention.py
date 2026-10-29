import hashlib
import importlib.util
import os
import time
import subprocess
import sys
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location(
    "prune_backups", Path(__file__).resolve().parents[4] / "scripts/prune-backups.py"
)
rotation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rotation)


def archive(directory, index):
    path = directory / f"haven-202601{index:02}T000000Z.sql.gpg"
    value = b"synthetic encrypted backup fixture" + bytes([index])
    path.write_bytes(value)
    path.with_name(path.name + ".sha256").write_text(hashlib.sha256(value).hexdigest() + "  " + path.name)
    os.utime(path, (time.time() - 10 * 86400,) * 2)
    return path


def test_rotation_keeps_three_and_does_not_touch_unrelated_files(tmp_path):
    tmp_path.chmod(0o700)
    paths = [archive(tmp_path, index) for index in range(1, 6)]
    unrelated = tmp_path / "other-secret.gpg"
    unrelated.write_bytes(b"not a HAVEN backup")
    assert set(rotation.plan(tmp_path)) == set(paths[:2])
    assert all(path.exists() for path in paths)  # Planning never mutates data.
    assert unrelated.exists()
    # Recently copied files are retained even when the embedded date is old.
    os.utime(paths[0], None)
    assert rotation.plan(tmp_path) == [paths[1]]


def test_rotation_fails_closed_on_corrupt_pair_symlink_or_permissions(tmp_path):
    tmp_path.chmod(0o700)
    paths = [archive(tmp_path, index) for index in range(1, 6)]
    paths[4].write_bytes(b"corrupted newest archive")
    with pytest.raises(ValueError):
        rotation.plan(tmp_path)
    archive(tmp_path, 5)
    paths[0].unlink()
    paths[0].symlink_to(paths[1])
    with pytest.raises(ValueError):
        rotation.plan(tmp_path)
    paths[0].unlink()
    archive(tmp_path, 1)
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError):
        rotation.plan(tmp_path)


def test_rotation_apply_only_removes_obsolete_pairs(tmp_path):
    tmp_path.chmod(0o700)
    paths = [archive(tmp_path, index) for index in range(1, 6)]
    command = [sys.executable, spec.origin, "--directory", str(tmp_path)]
    preview = json.loads(subprocess.check_output(command, text=True))
    assert preview["mode"] == "dry_run" and len(preview["archives"]) == 2
    assert all(path.exists() for path in paths)
    applied = json.loads(subprocess.check_output(command + ["--apply"], text=True))
    assert applied["mode"] == "applied"
    assert not any(path.exists() for path in paths[:2])
    assert all(path.exists() and path.with_name(path.name + ".sha256").exists() for path in paths[2:])
