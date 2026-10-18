# backup-automation

A small Python backup tool that creates timestamped `.tar.gz` archives, writes a SHA-256 manifest, **verifies** each backup by re-reading it, and **rotates** old backups. Supports a JSON config file and a `--dry-run` mode.

## Problem
Backups are only useful if they run consistently, are checked, and do not fill the disk. This automates all three for local directories.

## How it works
```mermaid
flowchart LR
    A[config.json] --> B[collect files, apply excludes]
    B --> C[tar.gz archive + SHA-256 manifest]
    C --> D[verify: re-hash archive contents]
    D --> E[rotate: keep newest N]
```

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pytest
pytest          # tests run entirely in temporary directories
```
Standard library only; no rsync is required (the tool uses Python's `tarfile`).

## Usage
Edit `config.example.json` (or copy it):
```json
{ "sources": ["./sample_source"], "destination": "./backups", "keep": 3, "exclude": ["*.tmp", "__pycache__"] }
```
```bash
python backup.py --config config.example.json --dry-run   # preview only
python backup.py --config config.example.json             # real run
```

## Sample output
```
Created backups/backup-20261018-150000.tar.gz
  + sample_source/notes.txt
Verification: OK
```
Dry run prints `[DRY RUN] would create ...` and changes nothing.

## Limitations
- Full backups only (no incremental/differential), local destinations only (no remote sync or encryption).
- Rotation deletes files in the destination folder matching `backup-*.tar.gz`, so point it at a dedicated folder. Try `--dry-run` first.

## What it demonstrates
Automation scripting, data-integrity checks with hashing, retention policies, safe dry-run design, and tests using temporary directories.

## License
MIT
