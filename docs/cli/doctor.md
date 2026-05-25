(cli-doctor)=

# rampa doctor

Report the runtime environment — Python version, rampa version,
platform, and optional dependency availability.

```console
$ rampa doctor
```

## Example output

```text
python: 3.14.0
rampa: 0.0.1
platform: linux (x86_64)
aiohttp: 3.13.5
uvloop: not installed
textual: not installed
fastmcp: 3.3.1
```

## Checked dependencies

| Dependency | Extra | Purpose |
|-----------|-------|---------|
| aiohttp | core | HTTP client |
| uvloop | performance | Event loop acceleration |
| textual | tui | TUI dashboard (planned) |
| fastmcp | mcp | MCP server |
