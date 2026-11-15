"""Install the pinned, checksum-verified official GitHub MCP Linux release."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import io
import json
import os
import platform
import re
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

import httpx

VERSION = "v2.1.0"
CHECKSUMS_NAME = "github-mcp-server_2.1.0_checksums.txt"
RELEASE_BASE = f"https://github.com/github/github-mcp-server/releases/download/{VERSION}/"
ARCHIVE_NAMES = {
    "amd64": "github-mcp-server_Linux_x86_64.tar.gz",
    "arm64": "github-mcp-server_Linux_arm64.tar.gz",
}


def normalize_architecture(value: str) -> str:
    normalized = value.lower()
    if normalized in {"x86_64", "amd64"}:
        return "amd64"
    if normalized in {"aarch64", "arm64"}:
        return "arm64"
    raise ValueError(f"Unsupported GitHub MCP Linux architecture: {value}")


def expected_checksum(checksums: str, archive_name: str) -> str:
    for line in checksums.splitlines():
        fields = line.strip().split()
        if len(fields) < 2:
            continue
        filename = fields[-1].lstrip("*")
        if filename == archive_name:
            digest = fields[0].lower()
            if re.fullmatch(r"[0-9a-f]{64}", digest):
                return digest
            raise ValueError(f"Invalid SHA-256 checksum for {archive_name}")
    raise ValueError(f"Checksum for {archive_name} is missing from the release manifest")


def _binary_from_archive(archive: bytes) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        candidates = [
            member for member in package.getmembers()
            if PurePosixPath(member.name).name == "github-mcp-server" and member.isfile()
        ]
        if len(candidates) != 1:
            raise ValueError("Release archive must contain exactly one github-mcp-server binary")
        source = package.extractfile(candidates[0])
        if source is None:
            raise ValueError("GitHub MCP binary is unreadable in the release archive")
        return source.read()


def install(destination: Path, architecture: str | None = None) -> dict[str, str]:
    if platform.system() != "Linux":
        raise SystemExit("Install the GitHub MCP binary inside Linux or a Linux container.")

    arch = normalize_architecture(architecture or platform.machine())
    archive_name = ARCHIVE_NAMES[arch]
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        checksums_response = client.get(RELEASE_BASE + CHECKSUMS_NAME)
        checksums_response.raise_for_status()
        expected = expected_checksum(checksums_response.text, archive_name)
        archive_response = client.get(RELEASE_BASE + archive_name)
        archive_response.raise_for_status()

    archive = archive_response.content
    actual = hashlib.sha256(archive).hexdigest()
    if not hmac.compare_digest(actual, expected):
        raise ValueError("GitHub MCP release archive checksum mismatch; binary not installed")

    binary_bytes = _binary_from_archive(archive)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
            temporary.write(binary_bytes)
            temporary_path = Path(temporary.name)
        os.chmod(temporary_path, 0o755)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()

    return {
        "version": VERSION,
        "architecture": arch,
        "source": RELEASE_BASE + archive_name,
        "archive_sha256": actual,
        "checksum_source": RELEASE_BASE + CHECKSUMS_NAME,
        "binary_sha256": hashlib.sha256(binary_bytes).hexdigest(),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1] / ".local-models" / "github-mcp"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", help="Docker TARGETARCH or Linux machine architecture")
    parser.add_argument("--destination", type=Path, default=root / "github-mcp-server")
    parser.add_argument("--metadata", type=Path, default=root / "runtime.json")
    args = parser.parse_args()

    record = install(args.destination, args.architecture)
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Installed official GitHub MCP {VERSION} ({record['architecture']}); checksum verified.")


if __name__ == "__main__":
    main()
