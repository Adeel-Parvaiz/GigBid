# 0001 One marketplace port, adapters behind an MCP server
Graph code depends on `MarketplacePort` only. `McpMarketplacePort` talks to the Marketplace MCP server, which wraps one adapter (sample / GigSim / Upwork). Switching marketplaces changes the adapter, not the graph. Cost: one extra hop (~50 ms measured over streamable-http).
