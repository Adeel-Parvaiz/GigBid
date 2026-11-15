"""Create and restore verified snapshots of GigBid's shared Docker appdata volume."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

SQLITE_HEADER = b"SQLite format 3\x00"
MANIFEST_NAME = "manifest.json"


def _relative_path(value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError(f"Unsafe backup path: {value!r}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"Unsafe backup path: {value!r}")
    return Path(*path.parts)


def _is_sqlite(path: Path) -> bool:
    with path.open("rb") as source:
        return source.read(len(SQLITE_HEADER)) == SQLITE_HEADER


def _integrity_check(path: Path) -> None:
    database = sqlite3.connect(path)
    try:
        result = database.execute("PRAGMA integrity_check").fetchone()
    finally:
        database.close()
    if not result or result[0] != "ok":
        raise ValueError(f"SQLite integrity check failed for {path}")


def _snapshot_sqlite(source: Path, destination: Path) -> None:
    source_db = sqlite3.connect(source, timeout=30)
    destination_db = sqlite3.connect(destination)
    try:
        source_db.backup(destination_db)
        destination_db.commit()
    finally:
        destination_db.close()
        source_db.close()
    _integrity_check(destination)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup(source: Path, backup_dir: Path) -> Path:
    source, backup_dir = source.resolve(), backup_dir.resolve()
    if not source.is_dir():
        raise ValueError(f"Appdata source directory does not exist: {source}")
    if backup_dir == source or source in backup_dir.parents:
        raise ValueError("Backup destination must be outside the appdata volume")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_path = backup_dir / f"gigbid-appdata-{timestamp}-{uuid.uuid4().hex[:8]}.tar.gz"
    with tempfile.TemporaryDirectory(prefix=".gigbid-backup-", dir=backup_dir) as temporary:
        staged = Path(temporary)
        records = []
        for original in sorted(source.rglob("*")):
            relative = original.relative_to(source)
            if original.is_symlink():
                raise ValueError(f"Refusing to back up symlink in appdata: {relative}")
            if not original.is_file():
                continue
            if original.name.endswith(("-wal", "-shm")):
                continue
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if _is_sqlite(original):
                _snapshot_sqlite(original, target)
                kind = "sqlite"
            else:
                shutil.copy2(original, target)
                kind = "file"
            records.append({"path": relative.as_posix(), "type": kind, "sha256": _hash(target)})

        manifest = {
            "format": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "files": records,
        }
        (staged / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        with tempfile.NamedTemporaryFile(dir=backup_dir, suffix=".tmp", delete=False) as temporary_archive:
            temporary_archive_path = Path(temporary_archive.name)
        try:
            with tarfile.open(temporary_archive_path, "w:gz") as archive:
                for path in sorted(staged.rglob("*")):
                    if path.is_file():
                        archive.add(path, arcname=path.relative_to(staged).as_posix(), recursive=False)
            os.replace(temporary_archive_path, archive_path)
        finally:
            if temporary_archive_path.exists():
                temporary_archive_path.unlink()
    return archive_path


def _stage_archive(archive_path: Path, staging: Path) -> list[Path]:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names = set()
        for member in members:
            relative = _relative_path(member.name)
            if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsupported member in backup archive: {member.name!r}")
            if relative.as_posix() in names:
                raise ValueError(f"Duplicate path in backup archive: {member.name!r}")
            names.add(relative.as_posix())
        manifest_member = next((member for member in members if member.name == MANIFEST_NAME), None)
        if manifest_member is None or not manifest_member.isfile():
            raise ValueError("Backup archive is missing its manifest")
        manifest_file = archive.extractfile(manifest_member)
        if manifest_file is None:
            raise ValueError("Backup manifest is unreadable")
        manifest = json.loads(manifest_file.read())
        if not isinstance(manifest, dict) or manifest.get("format") != 1 or not isinstance(manifest.get("files"), list):
            raise ValueError("Unsupported backup manifest")

        expected = {}
        for record in manifest["files"]:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                raise ValueError("Invalid backup manifest file record")
            relative = _relative_path(record["path"])
            if relative.as_posix() == MANIFEST_NAME or relative.as_posix() in expected:
                raise ValueError("Invalid or duplicate path in backup manifest")
            if record.get("type") not in {"sqlite", "file"}:
                raise ValueError(f"Unsupported backup file type for {relative}")
            expected[relative.as_posix()] = record

        if names != set(expected) | {MANIFEST_NAME}:
            raise ValueError("Backup archive contents do not match its manifest")
        staged_files = []
        for name, record in expected.items():
            member = next(member for member in members if member.name == name)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"Backup file is unreadable: {name}")
            target = staging / _relative_path(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            if _hash(target) != record.get("sha256"):
                raise ValueError(f"Backup checksum mismatch: {name}")
            if record["type"] == "sqlite":
                if not _is_sqlite(target):
                    raise ValueError(f"Expected a SQLite database: {name}")
                _integrity_check(target)
            staged_files.append(target)
        return staged_files


def restore(archive_path: Path, destination: Path, replace_existing: bool = False) -> None:
    archive_path, destination = archive_path.resolve(), destination.resolve()
    if not archive_path.is_file():
        raise ValueError(f"Backup archive does not exist: {archive_path}")
    destination.mkdir(parents=True, exist_ok=True)
    existing = list(destination.iterdir())
    if existing and not replace_existing:
        raise ValueError("Restore destination is not empty; pass --replace-existing after stopping all writers")

    with tempfile.TemporaryDirectory(prefix=".gigbid-restore-", dir=destination) as temporary:
        staging = Path(temporary) / "new"
        staging.mkdir()
        staged_files = _stage_archive(archive_path, staging)
        old_data = Path(temporary) / "old"
        old_data.mkdir()
        moved_old: list[tuple[Path, Path]] = []
        installed: list[Path] = []
        try:
            if replace_existing:
                for path in existing:
                    saved = old_data / path.name
                    os.replace(path, saved)
                    moved_old.append((saved, path))
            for staged in staged_files:
                relative = staged.relative_to(staging)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, target)
                installed.append(target)
        except BaseException:
            for path in reversed(installed):
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
            for saved, original in reversed(moved_old):
                if saved.exists():
                    os.replace(saved, original)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make_backup = commands.add_parser("backup")
    make_backup.add_argument("--source", type=Path, default=Path("/data"))
    make_backup.add_argument("--backup-dir", type=Path, required=True)
    restore_backup = commands.add_parser("restore")
    restore_backup.add_argument("--archive", type=Path, required=True)
    restore_backup.add_argument("--destination", type=Path, default=Path("/data"))
    restore_backup.add_argument("--replace-existing", action="store_true")
    args = parser.parse_args()

    if args.command == "backup":
        print(backup(args.source, args.backup_dir))
    else:
        restore(args.archive, args.destination, args.replace_existing)
        print(f"Restored verified appdata archive into {args.destination}")


if __name__ == "__main__":
    main()
