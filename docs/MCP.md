# Using KherveSheet from any AI assistant (MCP)

KherveSheet ships an [MCP](https://modelcontextprotocol.io) server, so
assistants other than the built-in AI chat — Claude Desktop, Claude
Code, Cursor, Zed, Continue, or anything else that speaks the Model
Context Protocol — can read and edit an open workbook directly.

The assistant gets the same tool set the built-in chat uses: reading
and writing cells, formulas and `=PY` Python cells, formatting, table
styles, column widths, charts, and the formula/analysis catalogue.
Everything it does lands on the shared undo stack, so **Ctrl+Z in
KherveSheet reverts a remote assistant's change** just like your own.

## How it fits together

```
 MCP host  ──stdio──▶  khervesheet.mcp_server  ──loopback TCP──▶  KherveSheet
(Claude Desktop,       (short-lived process                       (your open
 Claude Code, …)        the host owns)                             workbook)
```

Spreadsheet tools have to touch live Qt widgets, so they run inside
the application's GUI thread. MCP hosts, meanwhile, want to spawn and
restart a subprocess of their own. The stdio server is that
subprocess; it holds no state and forwards each call over a loopback
socket to the running application.

Practical consequences:

- **KherveSheet must be running** for tools to work. The host may be
  started first — `initialize` still succeeds, and the connection
  starts working the moment the app comes up. No host restart needed.
- Restarting KherveSheet does not require restarting the host: the
  stdio server reconnects on the next call.
- The tools act on the **workbook that is open right now**.

## Turning it on

1. **Tools ▸ MCP Server…**
2. Tick **Enable MCP server**. The setting is remembered, so the
   bridge comes back automatically next launch.
3. Pick your host from the dropdown and press **Copy**.

### Claude Desktop / Cursor / Zed

Paste into the host's config file (`claude_desktop_config.json` for
Claude Desktop) and restart it:

```json
{
  "mcpServers": {
    "khervesheet": {
      "command": "/path/to/python",
      "args": ["-m", "khervesheet.mcp_server"],
      "cwd": "/path/to/KherveSheet"
    }
  }
}
```

An installed (frozen) build serves as its own MCP server, so the entry
is just the executable:

```json
{
  "mcpServers": {
    "khervesheet": {
      "command": "C:\\Program Files\\KherveSheet\\KherveSheet.exe",
      "args": ["--mcp-server"]
    }
  }
}
```

`--mcp-server` is checked before any GUI work happens: the process
speaks protocol on stdout and never opens a window.

### Claude Code

```
claude mcp add khervesheet -- /path/to/python -m khervesheet.mcp_server
```

## Security

- The listener binds to **127.0.0.1 only** — nothing on the network
  can reach it.
- Every request must carry a random per-session token, published in an
  endpoint file written user-readable only:
  - Windows: `%LOCALAPPDATA%\KherveSheet\mcp-bridge.json`
  - macOS: `~/Library/Application Support/KherveSheet/mcp-bridge.json`
  - Linux: `$XDG_CONFIG_HOME/KherveSheet/mcp-bridge.json`
- The bridge is **off until you turn it on**, and stops with the
  window (the endpoint file is removed on the way out).

Treat an enabled bridge as giving the connected assistant the same
reach over your workbook as the built-in chat — including the ability
to write and run `=PY` cells, which execute real Python.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| "KherveSheet is not reachable" | The app is not running, or Tools ▸ MCP Server is unticked. Fix and retry — no host restart needed. |
| "Invalid bridge token" | A stale endpoint file from a previous run. Toggle the checkbox off and on. |
| Host shows no tools | The host caches `tools/list` from startup; restart the host once with KherveSheet already running. |
| "Could not open a local port" | Another process is holding the port. Toggle off and on to pick a fresh one. |

Diagnostics from the stdio server go to **stderr**, which MCP hosts
capture in their own logs; stdout carries protocol only.
