# Security policy

## Scope and safety
writes only inside the configured destination; deletes only rotated archives that match the strict backup filename pattern; `--dry-run` and `--no-rotate` available; archives are `0600`; the destination cannot be inside a source.

## What was and was not tested
**Tested (automated, in CI and locally):** archive creation, verification, exclusion, rotation, validation and CLI errors in temporary directories on Linux.

**Not tested:** large backups, network or removable destinations, symlink-heavy trees, Windows/macOS, and restoring from a backup (restore is not implemented).

## Reporting a problem
This is a small personal portfolio project, not a supported product. If you find a security issue, please open a GitHub issue **without** secrets, credentials or real system details, or use GitHub's "Report a vulnerability" button on the Security tab if it is enabled.
