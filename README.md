# py-mcp-gateway
go-mcp-gateway

## MCP Server Registry Repository

Repository layer for `mcp_server_registry` is implemented with:

- Domain contract: `McpServerRepository`
- PostgreSQL implementation: `PostgresMcpServerRepository`
- Database access: `asyncpg` pool + parameterized raw SQL
- Coverage for create/get/list/update/delete and exception mapping in integration tests

```json

# Discovery
{
  "serverId": "inventory-prod-02",
  "protocolVersion": "2025-06-18",
  "serverInfo": {
    "name": "inventory-mcp",
    "version": "2.4.1"
  },
  "capabilities": {
    "tools": {
      "listChanged": true
    },
    "prompts": {
      "listChanged": true
    },
    "resources": {
      "listChanged": true,
      "subscribe": true
    }
  },
  "tools": [],
  "prompts": [],
  "resources": [],
  "resourceTemplates": [],
  "discoveredAt": "2026-11-08T22:25:00-03:00",
  "contentHash": "sha256:..."
}
```

## Capability persistence (`mcp_server_capability`)

During discovery, MCP capabilities are persisted with the complete original object in `payload` (`JSONB`).

`identifier` is populated as:

- Tool: `name`
- Prompt: `name`
- Resource: `uri`
- Resource template: `uriTemplate`