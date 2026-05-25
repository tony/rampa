(mcp)=

# MCP Server

The `rampa-mcp` server lets AI agents start, stop, and query load
tests via the Model Context Protocol.

## Install

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

## Start the server

```console
$ rampa-mcp
```

## Client configuration

### Claude Code

```console
$ claude mcp add rampa-mcp -- rampa-mcp
```

### Codex

```console
$ codex install rampa-mcp
```

::::{grid} 1 1 2 2
:gutter: 2

:::{grid-item-card} Tools
:link: tools
:link-type: doc
Start, stop, and query load test runs.
:::

:::{grid-item-card} Resources
:link: resources
:link-type: doc
URI templates for runs, metrics, and thresholds.
:::

::::

```{toctree}
:hidden:

tools
resources
```
