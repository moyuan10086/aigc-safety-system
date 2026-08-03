"""Operator maintenance primitives for backup, archive verification and rotation."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from services import api_access_service, audit_log_service, tenant_artifact_service

_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _archive_root() -> Path:
    path = Path(config.AUDIT_ARCHIVE_PATH)
    if not path.is_absolute():
        path = Path(__file__).parents[1] / path
    return path.resolve()


def _safe_archive_dir(name: str) -> Path:
    if not name or Path(name).name != name:
        raise ValueError("archive name must be a single relative directory name")
    path = (_archive_root() / name).resolve()
    if path.parent != _archive_root():
        raise ValueError("archive path escapes configured archive directory")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _online_backup(source: Path, destination: Path) -> None:
    source.parent.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source, timeout=10)) as source_db, closing(
        sqlite3.connect(destination, timeout=10)
    ) as destination_db:
        source_db.backup(destination_db)


def _counts(path: Path) -> dict[str, int]:
    with closing(sqlite3.connect(path, timeout=10)) as connection:
        result: dict[str, int] = {}
        for table in (
            "audit_events",
            "audit_evidence",
            "guardrail_shadow_reviews",
            "api_keys",
            "api_usage",
            "tenant_scan_jobs",
            "tenant_reports",
        ):
            try:
                result[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.OperationalError:
                result[table] = 0
    return result


def create_backup(*, label: str | None = None) -> dict[str, Any]:
    """Create a consistent online backup and an integrity manifest."""
    # Ensure empty installations still produce valid, restorable databases.
    with closing(api_access_service._connect()):
        pass
    with closing(audit_log_service._connect()):
        pass
    with closing(tenant_artifact_service._connect()):
        pass
    root = _archive_root()
    root.mkdir(parents=True, exist_ok=True)
    suffix = label or "manual"
    if not _LABEL_RE.fullmatch(suffix):
        raise ValueError("archive label must use letters, digits, '_' or '-'")
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{suffix}_{uuid.uuid4().hex[:8]}"
    archive_dir = _safe_archive_dir(name)
    archive_dir.mkdir()
    sources = {
        "audit.db": audit_log_service._db_path(),
        "api_keys.db": api_access_service._db_path(),
    }
    files: list[dict[str, Any]] = []
    for filename, source in sources.items():
        destination = archive_dir / filename
        _online_backup(source, destination)
        files.append({"name": filename, "size": destination.stat().st_size, "sha256": _sha256(destination)})
    audit_db = archive_dir / "audit.db"
    counts = _counts(audit_db)
    counts.update({
        key: value
        for key, value in _counts(archive_dir / "api_keys.db").items()
        if key in {"api_keys", "api_usage", "tenant_scan_jobs", "tenant_reports"}
    })
    manifest = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "archive": name,
        "files": files,
        "counts": counts,
        "audit_chain_valid": audit_log_service.verify_chain(audit_db),
        "raw_evidence_policy": "audit_evidence remains encrypted; this archive contains ciphertext and nonce, not plaintext.",
        "retention_policy": "archive-before-prune; this command does not delete production evidence",
    }
    if not manifest["audit_chain_valid"]:
        raise RuntimeError("audit hash chain is invalid; backup was created but must not be accepted")
    (archive_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {**manifest, "path": str(archive_dir)}


def verify_backup(name: str) -> dict[str, Any]:
    archive_dir = _safe_archive_dir(name)
    manifest_path = archive_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("archive manifest not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    for entry in manifest.get("files", []):
        filename = str(entry.get("name", ""))
        if Path(filename).name != filename:
            raise ValueError("manifest contains an unsafe file name")
        path = archive_dir / filename
        actual = _sha256(path)
        checks.append({"name": filename, "sha256": actual, "matches": actual == entry.get("sha256")})
    chain_valid = audit_log_service.verify_chain(archive_dir / "audit.db")
    return {
        "archive": name,
        "files": checks,
        "files_valid": all(item["matches"] for item in checks),
        "audit_chain_valid": chain_valid,
        "valid": all(item["matches"] for item in checks) and chain_valid,
        "counts": manifest.get("counts", {}),
    }


def rotate_evidence_keys() -> dict[str, Any]:
    """Backup first, then migrate encrypted evidence to the current key."""
    if not config.AUDIT_CONTENT_KEY or not config.AUDIT_CONTENT_PREVIOUS_KEY:
        raise RuntimeError("AUDIT_CONTENT_KEY and AUDIT_CONTENT_PREVIOUS_KEY are both required")
    backup = create_backup(label="pre-evidence-rotation")
    migrated = audit_log_service.reencrypt_evidence()
    return {"backup": backup, "migrated_evidence": migrated}
