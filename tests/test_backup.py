import os, sys, tarfile
from datetime import datetime, timedelta
from pathlib import Path
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import backup


@pytest.fixture
def src(tmp_path):
    s = tmp_path / "data"
    (s / "sub").mkdir(parents=True)
    (s / "a.txt").write_text("alpha")
    (s / "sub" / "b.txt").write_text("beta")
    (s / "junk.tmp").write_text("x")
    return s


def test_backup_and_verify(src, tmp_path):
    r = backup.create_backup([src], tmp_path / "out", exclude=["*.tmp"])
    assert sorted(r["files"]) == ["data/a.txt", "data/sub/b.txt"]
    assert backup.verify_backup(r["archive"]) == []


def test_dry_run_writes_nothing(src, tmp_path):
    out = tmp_path / "out"
    r = backup.create_backup([src], out, dry_run=True)
    assert r["dry_run"] and not out.exists()


def test_verify_detects_corruption(src, tmp_path):
    r = backup.create_backup([src], tmp_path / "out")
    # rebuild archive with a modified file but the old manifest
    bad = tmp_path / "tamper"
    bad.mkdir()
    (bad / "a.txt").write_text("CHANGED")
    with tarfile.open(r["archive"], "w:gz") as t:
        t.add(bad / "a.txt", arcname="data/a.txt")
    problems = backup.verify_backup(r["archive"])
    assert any("mismatch" in p for p in problems) and any("missing" in p for p in problems)


def test_rotation_keeps_newest(src, tmp_path):
    out = tmp_path / "out"
    base = datetime(2026, 1, 1)
    for i in range(5):
        backup.create_backup([src], out, now=base + timedelta(days=i))
    removed = backup.rotate(out, keep=2)
    left = sorted(p.name for p in out.glob("backup-*.tar.gz"))
    assert len(removed) == 3 and left == ["backup-20260104-000000.tar.gz", "backup-20260105-000000.tar.gz"]
    assert len(list(out.glob("*.manifest.json"))) == 2


def test_run_from_config(src, tmp_path):
    cfg = {"sources": [str(src)], "destination": str(tmp_path / "o"), "keep": 1, "exclude": []}
    r = backup.run(cfg)
    assert r["problems"] == []


def test_config_validation(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{}")
    with pytest.raises(ValueError):
        backup.load_config(p)
