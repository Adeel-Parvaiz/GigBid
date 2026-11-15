import io
import sqlite3
import tarfile

import pytest

from scripts.backup_appdata import backup, restore


def _database(path, value):
    with sqlite3.connect(path) as database:
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("CREATE TABLE IF NOT EXISTS records (value TEXT)")
        database.execute("INSERT INTO records VALUES (?)", (value,))


def test_backup_and_restore_preserve_sqlite_and_regular_files(tmp_path):
    source = tmp_path / "appdata"
    source.mkdir()
    _database(source / "users.sqlite", "before")
    (source / "audit.jsonl").write_text('{"event":"before"}\n', encoding="utf-8")
    writer = sqlite3.connect(source / "users.sqlite")
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("INSERT INTO records VALUES ('committed-in-wal')")
    writer.commit()
    assert (source / "users.sqlite-wal").exists()
    archive = backup(source, tmp_path / "backups")
    writer.close()

    _database(source / "users.sqlite", "after")
    (source / "audit.jsonl").write_text('{"event":"after"}\n', encoding="utf-8")
    restored = tmp_path / "restored"
    restore(archive, restored)

    with sqlite3.connect(restored / "users.sqlite") as database:
        assert database.execute("SELECT value FROM records ORDER BY rowid").fetchall() == [
            ("before",),
            ("committed-in-wal",),
        ]
    assert (restored / "audit.jsonl").read_text(encoding="utf-8") == '{"event":"before"}\n'


def test_restore_requires_explicit_replace_for_existing_data(tmp_path):
    source = tmp_path / "appdata"
    source.mkdir()
    (source / "state.json").write_text("backup", encoding="utf-8")
    archive = backup(source, tmp_path / "backups")
    destination = tmp_path / "restore"
    destination.mkdir()
    (destination / "state.json").write_text("current", encoding="utf-8")

    with pytest.raises(ValueError, match="not empty"):
        restore(archive, destination)
    restore(archive, destination, replace_existing=True)
    assert (destination / "state.json").read_text(encoding="utf-8") == "backup"


def test_restore_rejects_archive_checksum_mismatch(tmp_path):
    source = tmp_path / "appdata"
    source.mkdir()
    (source / "state.json").write_text("backup", encoding="utf-8")
    archive = backup(source, tmp_path / "backups")
    corrupted = tmp_path / "corrupted.tar.gz"
    with tarfile.open(archive, "r:gz") as original, tarfile.open(corrupted, "w:gz") as modified:
        for member in original.getmembers():
            contents = original.extractfile(member).read()
            if member.name == "state.json":
                contents = b"tampered"
                member.size = len(contents)
            modified.addfile(member, io.BytesIO(contents))

    with pytest.raises(ValueError, match="checksum mismatch"):
        restore(corrupted, tmp_path / "restore")


@pytest.mark.parametrize("unsafe", ["../outside", r"..\outside", "C:/outside", "nested//file"])
def test_backup_paths_reject_traversal_and_noncanonical_names(unsafe):
    from scripts.backup_appdata import _relative_path

    with pytest.raises(ValueError, match="Unsafe backup path"):
        _relative_path(unsafe)
