"""Tar-based backup with rotation and verification (standard library only)."""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
import tarfile
from datetime import datetime
from pathlib import Path

PREFIX = "backup-"
ARCHIVE_RE = re.compile(r"^backup-\d{8}-\d{6}\.tar\.gz$")  # rotation only ever deletes names like this


def load_config(path):
    with open(path) as f:
        cfg = json.load(f)
    for key in ("sources", "destination"):
        if key not in cfg:
            raise ValueError(f"config missing '{key}'")
    cfg.setdefault("keep", 5)
    cfg.setdefault("exclude", [])
    if not isinstance(cfg["sources"], list) or not cfg["sources"]:
        raise ValueError("'sources' must be a non-empty list of paths")
    if not isinstance(cfg["destination"], str) or not cfg["destination"]:
        raise ValueError("'destination' must be a path string")
    if not isinstance(cfg["keep"], int) or isinstance(cfg["keep"], bool) or cfg["keep"] < 1:
        raise ValueError("keep must be an integer >= 1")
    if not isinstance(cfg["exclude"], list):
        raise ValueError("'exclude' must be a list of glob patterns")
    for s in cfg["sources"]:
        if not Path(s).exists():
            raise ValueError(f"source does not exist: {s}")
        d, sp = Path(cfg["destination"]).resolve(), Path(s).resolve()
        if d == sp or sp in d.parents:
            raise ValueError(f"destination {cfg['destination']} must not be inside source {s}")
    return cfg


def _excluded(name, patterns):
    return any(fnmatch.fnmatch(part, p) for p in patterns for part in Path(name).parts)


def list_files(sources, exclude):
    """Yield (absolute path, archive name) for every file to back up."""
    for src in sources:
        src = Path(src)
        if src.is_file():
            if not _excluded(src.name, exclude):
                yield src, src.name
            continue
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if not _excluded(d, exclude)]
            for fn in files:
                full = Path(root) / fn
                if not _excluded(fn, exclude):
                    yield full, str(Path(src.name) / full.relative_to(src))


def sha256(path_or_fileobj):
    h = hashlib.sha256()
    if hasattr(path_or_fileobj, "read"):
        f, close = path_or_fileobj, False
    else:
        f, close = open(path_or_fileobj, "rb"), True
    try:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    finally:
        if close:
            f.close()
    return h.hexdigest()


def create_backup(sources, dest, exclude=(), dry_run=False, now=None):
    now = now or datetime.now()
    files = list(list_files(sources, exclude))
    name = f"{PREFIX}{now:%Y%m%d-%H%M%S}.tar.gz"
    target = Path(dest) / name
    if dry_run:
        return {"archive": str(target), "files": [a for _, a in files], "dry_run": True}
    Path(dest).mkdir(parents=True, exist_ok=True)
    manifest = {}
    with tarfile.open(target, "w:gz") as tar:
        for full, arc in files:
            manifest[arc] = sha256(full)
            tar.add(full, arcname=arc)
    os.chmod(target, 0o600)  # backups may contain private data: owner-only
    Path(str(target) + ".manifest.json").write_text(json.dumps(manifest, indent=2))
    return {"archive": str(target), "files": list(manifest), "dry_run": False}


def verify_backup(archive):
    """Re-hash every file inside the archive and compare with the manifest."""
    manifest = json.loads(Path(str(archive) + ".manifest.json").read_text())
    problems = []
    with tarfile.open(archive, "r:gz") as tar:
        seen = set()
        for m in tar.getmembers():
            if not m.isfile():
                continue
            seen.add(m.name)
            if manifest.get(m.name) != sha256(tar.extractfile(m)):
                problems.append(f"checksum mismatch: {m.name}")
        problems += [f"missing from archive: {n}" for n in manifest if n not in seen]
    return problems


def rotate(dest, keep, dry_run=False):
    """Keep the newest `keep` backups; delete older archives and manifests."""
    archives = sorted(a for a in Path(dest).glob(f"{PREFIX}*.tar.gz") if ARCHIVE_RE.match(a.name))
    old = archives[:-keep] if len(archives) > keep else []
    if not dry_run:
        for a in old:
            a.unlink()
            Path(str(a) + ".manifest.json").unlink(missing_ok=True)
    return [str(a) for a in old]


def run(cfg, dry_run=False, now=None):
    result = create_backup(cfg["sources"], cfg["destination"], cfg["exclude"], dry_run, now)
    result["problems"] = [] if dry_run else verify_backup(result["archive"])
    result["rotated"] = rotate(cfg["destination"], cfg["keep"], dry_run) if not dry_run else \
        rotate(cfg["destination"], cfg["keep"], True)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tar backup with rotation and verification")
    ap.add_argument("--config", default="config.example.json")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    ap.add_argument("--no-rotate", action="store_true", help="never delete old backups")
    a = ap.parse_args(argv)
    try:
        cfg = load_config(a.config)
        if a.no_rotate:
            cfg["keep"] = 10 ** 9
        r = run(cfg, a.dry_run)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(("[DRY RUN] would create " if r["dry_run"] else "Created ") + r["archive"])
    for f in r["files"]:
        print("  +", f)
    print("Verification:", "skipped (dry run)" if r["dry_run"] else ("OK" if not r["problems"] else r["problems"]))
    for o in r["rotated"]:
        print(("  would remove old backup " if r["dry_run"] else "  removed old backup ") + o)
    return 1 if r["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
