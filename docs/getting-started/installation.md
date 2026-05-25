(installation)=

# Installation

## Requirements

- Python 3.14+

## Install

::::{tab-set}

:::{tab-item} uv (recommended)
```console
$ uv add rampa
```
:::

:::{tab-item} pip
```console
$ pip install rampa
```
:::

:::{tab-item} uvx (no install)
```console
$ uvx rampa run load_test.py
```
:::

::::

## Optional extras

### MCP server

To use `rampa-mcp` with AI agent CLIs:

::::{tab-set}

:::{tab-item} uv
```console
$ uv add "rampa[mcp]"
```
:::

:::{tab-item} pip
```console
$ pip install "rampa[mcp]"
```
:::

::::

## Verify

```console
$ rampa doctor
```

Expected output:

```text
python: 3.14.0
rampa: 0.0.1
platform: linux (x86_64)
aiohttp: 3.13.5
uvloop: not installed
textual: not installed
fastmcp: not installed
```
