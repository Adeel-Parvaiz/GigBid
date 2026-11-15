"""Install the pinned, checksum-verified official GitHub MCP Linux release."""
import hashlib
import json
import platform
import tarfile
from pathlib import Path

import httpx


def main():
    if platform.system() != 'Linux' or platform.machine() not in {'x86_64', 'AMD64'}:
        raise SystemExit('Run this installer inside the project Linux x86_64/WSL environment.')
    root = Path(__file__).resolve().parents[1] / '.local-models/github-mcp'
    root.mkdir(parents=True, exist_ok=True)
    version = 'v2.1.0'
    base = f'https://github.com/github/github-mcp-server/releases/download/{version}/'
    name, checksums = 'github-mcp-server_Linux_x86_64.tar.gz', 'github-mcp-server_2.1.0_checksums.txt'
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        response = client.get(base + checksums)
        response.raise_for_status()
        expected = next(line.split()[0] for line in response.text.splitlines() if line.split()[-1] == name)
        archive = root / name
        if not archive.exists():
            response = client.get(base + name)
            response.raise_for_status()
            archive.write_bytes(response.content)
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit('GitHub MCP checksum mismatch; binary not installed.')
    binary = root / 'github-mcp-server'
    with tarfile.open(archive) as package:
        entry = next(m for m in package.getmembers() if Path(m.name).name == 'github-mcp-server' and m.isfile())
        binary.write_bytes(package.extractfile(entry).read())
    binary.chmod(0o755)
    record = {'version': version, 'source': base + name, 'archive_sha256': actual,
              'checksum_source': base + checksums, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
    (root / 'runtime.json').write_text(json.dumps(record, indent=2))
    print(f'Installed official GitHub MCP {version}; checksum verified.')


if __name__ == '__main__':
    main()
