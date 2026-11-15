# gigbid-portfolio MCP server
Read-only MCP server over a freelancer's portfolio: tools `search_evidence`, `get_case_study`, `list_skills`; resources `portfolio://case/{id}`, `portfolio://proposal/{id}`; prompts for screening answers and proposals.
```bash
pip install -e .   # from the repo; PyPI publishing not done yet
PORTFOLIO_DIR=/path/to/your/data PORTFOLIO_FREELANCER_ID=you python -m mcp_servers.portfolio.server   # stdio
```
Claude Desktop / Cursor config: `{"mcpServers":{"portfolio":{"command":"python","args":["-m","mcp_servers.portfolio.server"],"env":{"PORTFOLIO_DIR":"/path"}}}}`
Data files: `portfolio_items.json`, optional `past_proposals.json` (see `data/sample/`). `PORTFOLIO_RETRIEVAL=dense|hybrid|hybrid_rerank`.
