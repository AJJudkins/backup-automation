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


def test_config_validation(tmp_path, src):
    import json
    def cfg(**kw):
        c = {"sources": [str(src)], "destination": str(tmp_path / "out"), "keep": 2}
        c.update(kw)
        p = tmp_path / "c.json"
        p.write_text(json.dumps(c))
        return str(p)
    assert backup.load_config(cfg())["keep"] == 2
    for bad in (dict(keep=0), dict(keep="3"), dict(sources=[]), dict(sources=[str(tmp_path / "nope")]),
                dict(destination=str(src / "inside"))):
        with pytest.raises(ValueError):
            backup.load_config(cfg(**bad))


def test_cli_errors_are_clean(tmp_path, capsys):
    assert backup.main(["--config", str(tmp_path / "missing.json")]) == 2
    assert "error:" in capsys.readouterr().err


def test_rotation_only_touches_backup_named_files(tmp_path):
    for n in ("backup-20260101-000000.tar.gz", "backup-20260102-000000.tar.gz", "backup-notes.tar.gz", "keep.txt"):
        (tmp_path / n).write_text("x")
    removed = backup.rotate(tmp_path, 1)
    assert [Path(r).name for r in removed] == ["backup-20260101-000000.tar.gz"]
    assert (tmp_path / "backup-notes.tar.gz").exists() and (tmp_path / "keep.txt").exists()


def test_archive_is_owner_only(src, tmp_path):
    r = backup.create_backup([src], tmp_path / "out")
    assert oct(os.stat(r["archive"]).st_mode & 0o777) == "0o600"
