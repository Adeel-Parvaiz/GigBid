import hashlib
import io
import tarfile

import pytest

from scripts import install_github_mcp


@pytest.mark.parametrize(
    ("value", "expected"),
    [("x86_64", "amd64"), ("AMD64", "amd64"), ("aarch64", "arm64"), ("arm64", "arm64")],
)
def test_release_architecture_aliases(value, expected):
    assert install_github_mcp.normalize_architecture(value) == expected


def test_unknown_architecture_is_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        install_github_mcp.normalize_architecture("riscv64")


def test_checksum_manifest_requires_matching_filename_and_sha256():
    digest = "a" * 64
    assert install_github_mcp.expected_checksum(
        f"{digest} *github-mcp-server_Linux_arm64.tar.gz\n", "github-mcp-server_Linux_arm64.tar.gz"
    ) == digest
    with pytest.raises(ValueError, match="missing"):
        install_github_mcp.expected_checksum(f"{digest} other.tar.gz\n", "expected.tar.gz")
    with pytest.raises(ValueError, match="Invalid"):
        install_github_mcp.expected_checksum(
            "not-a-checksum github-mcp-server_Linux_arm64.tar.gz\n", "github-mcp-server_Linux_arm64.tar.gz"
        )


def _archive(binary: bytes) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as package:
        info = tarfile.TarInfo("github-mcp-server")
        info.size = len(binary)
        package.addfile(info, io.BytesIO(binary))
    return output.getvalue()


def test_install_downloads_selected_asset_and_verifies_checksum(tmp_path, monkeypatch):
    binary = b"\x7fELF test github mcp"
    archive = _archive(binary)
    archive_name = install_github_mcp.ARCHIVE_NAMES["arm64"]
    digest = hashlib.sha256(archive).hexdigest()

    class Response:
        def __init__(self, content=b"", text=""):
            self.content, self.text = content, text

        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **_kwargs):
            self.urls = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url):
            self.urls.append(url)
            if url.endswith(install_github_mcp.CHECKSUMS_NAME):
                return Response(text=f"{digest}  {archive_name}\n")
            return Response(content=archive)

    monkeypatch.setattr(install_github_mcp.platform, "system", lambda: "Linux")
    monkeypatch.setattr(install_github_mcp.httpx, "Client", Client)
    destination = tmp_path / "bin" / "github-mcp-server"
    result = install_github_mcp.install(destination, "aarch64")

    assert destination.read_bytes() == binary
    assert result["architecture"] == "arm64"
    assert result["source"].endswith(archive_name)


def test_install_rejects_bad_checksum_without_creating_binary(tmp_path, monkeypatch):
    archive = _archive(b"binary")

    class Response:
        content = archive
        text = f"{'0' * 64}  {install_github_mcp.ARCHIVE_NAMES['amd64']}\n"

        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url):
            return Response()

    monkeypatch.setattr(install_github_mcp.platform, "system", lambda: "Linux")
    monkeypatch.setattr(install_github_mcp.httpx, "Client", Client)
    destination = tmp_path / "github-mcp-server"
    with pytest.raises(ValueError, match="checksum mismatch"):
        install_github_mcp.install(destination, "amd64")
    assert not destination.exists()
