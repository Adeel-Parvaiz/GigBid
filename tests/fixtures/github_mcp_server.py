"""Local transport fixture, not a substitute for the official GitHub server."""
import base64

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

server = FastMCP('github-fixture')
read = ToolAnnotations(readOnlyHint=True, destructiveHint=False)


@server.tool(annotations=read)
def get_me() -> dict:
    return {'login': 'fixture-owner'}


@server.tool(annotations=read)
def get_file_contents(owner: str, repo: str, path: str, ref: str | None = None) -> dict:
    content = '# Portfolio project\nA Python analysis project with reproducible scripts.\n'
    if path.endswith('.py'):
        content = 'def reproducible_analysis(rows):\n    return sorted(rows)\n'
    return {'content': base64.b64encode(content.encode()).decode(), 'encoding': 'base64', 'sha': 'fixture-sha'}


@server.tool(annotations=read)
def search_repositories(query: str) -> dict:
    return {'items': [{'full_name': 'fixture-owner/project'}]}


if __name__ == '__main__':
    server.run(transport='stdio')
