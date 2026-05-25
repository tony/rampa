(mcp-resources)=

# MCP Resources

The rampa MCP server exposes resources via URI templates for
structured access to run data.

## Resource URIs

| URI | Description |
|-----|-------------|
| `rampa://runs` | List all runs |
| `rampa://runs/{run_id}` | Run details |
| `rampa://runs/{run_id}/metrics` | All metrics for a run |
| `rampa://runs/{run_id}/metrics/{name}` | Single metric |
| `rampa://runs/{run_id}/thresholds` | Threshold results |
| `rampa://runs/{run_id}/events` | Event history |
