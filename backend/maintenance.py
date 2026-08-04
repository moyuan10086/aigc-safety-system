"""Run operator-only maintenance without exposing it through the public API.

Examples:
  uv run python maintenance.py backup --label before-release
  uv run python maintenance.py verify --archive 20260803T120000Z_before-release_ab12cd34
  uv run python maintenance.py restore-verify --archive 20260803T120000Z_before-release_ab12cd34
  uv run python maintenance.py rotate-evidence
"""

from __future__ import annotations

import argparse
import json

from services import maintenance_service


def main() -> None:
    parser = argparse.ArgumentParser(description="AIGC security audit maintenance")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup = subparsers.add_parser("backup", help="create an online SQLite backup")
    backup.add_argument("--label", default="manual")
    verify = subparsers.add_parser("verify", help="verify checksums and audit chain")
    verify.add_argument("--archive", required=True)
    restore_verify = subparsers.add_parser(
        "restore-verify", help="restore an archive to an isolated temp directory and verify it"
    )
    restore_verify.add_argument("--archive", required=True)
    subparsers.add_parser("rotate-evidence", help="backup and re-encrypt evidence with current key")
    args = parser.parse_args()
    if args.command == "backup":
        result = maintenance_service.create_backup(label=args.label)
    elif args.command == "verify":
        result = maintenance_service.verify_backup(args.archive)
    elif args.command == "restore-verify":
        result = maintenance_service.verify_restore(args.archive)
    else:
        result = maintenance_service.rotate_evidence_keys()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
