from apps.api.auth.github_mcp import GitHubMCP
from apps.api.auth.oauth_store import OAuthVault


def test_github_connection_requests_no_repository_write_scopes(tmp_path, monkeypatch):
    binary = tmp_path / 'github-mcp-server'
    binary.touch()
    monkeypatch.setenv('GITHUB_MCP_BINARY', str(binary))
    service = GitHubMCP(OAuthVault(tmp_path / 'oauth.sqlite'))
    args = service.default_connection(None)['args']
    scopes = next(arg.split('=', 1)[1] for arg in args if arg.startswith('--oauth-scopes='))
    assert scopes == 'read:user'
    assert '--read-only' in args
    assert not {'repo', 'public_repo'} & set(scopes.split(','))
