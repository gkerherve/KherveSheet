# Using KherveSheet from any AI assistant (MCP)

KherveSheet ships an [MCP](https://modelcontextprotocol.io) server, so
assistants other than the built-in AI chat — Claude Desktop, Claude
Code, Cursor, Zed, Continue, or anything else that speaks the Model
Context Protocol — can read and edit an open workbook directly.

The assistant gets the same tool set the built-in chat uses:

- **The grid** — read and write cells, formulas and `=PY` Python
  cells, formatting, table styles, column widths, merges.
- **Charts** — create, inspect, clone, restyle, delete.
- **Analysis** — `run_solver` (Excel-style optimisation),
  `fit_trendline` (23 regression models with goodness-of-fit),
  `fit_peaks` (lmfit peak fitting over a Shirley/ALS/polynomial
  background). These run the same code the Solver and Curve Fitting
  dialogs run; they just do it without the dialog.
- **The document** — `get_document_info`, `save_workbook`,
  `open_workbook`, `new_workbook`.
- **Discovery** — `search_functions`, `get_function_details` and
  `list_fit_models`, so a client that has never seen KherveSheet can
  look up exact names instead of guessing.

Everything a tool changes lands on the shared undo stack, so **Ctrl+Z
in KherveSheet reverts a remote assistant's change** just like your own.

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
3. Choose what clients may do (see **Access levels** below).
4. Pick your host from the dropdown and press **Copy**.

The dialog also shows a running log of what connected clients have
actually called.

## Access levels

| Level | A connected client can |
| --- | --- |
| **Read only** | Inspect the workbook. No changes at all. |
| **Edit** (default) | Read, write, format, chart, fit, solve, save — but **not** run Python. |
| **Full** | Everything, including `set_python_cell`. |

`=PY` cells execute real Python inside KherveSheet's own process, with
the filesystem and network reach of the application. That is why it
sits behind its own level rather than coming with edit access: granting
**Full** gives the connected assistant the same code-execution reach as
the built-in chat, so grant it only to hosts you trust.

Tools above the current level are withheld from `tools/list` and
refused if called anyway, with an error naming the setting. Hosts cache
the tool list from startup, so *widening* access takes effect on their
next reconnect; *narrowing* it takes effect immediately.

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
| "Refused: … access is set to …" | The access level in Tools ▸ MCP Server is below what the tool needs. |
| "still running the previous tool call" | A solve or fit is in progress. One call runs at a time; retry when it finishes. |
| Saving reports success but the title still shows a modified document | Should not happen — file it. Document tools deliberately run outside the undo macro so `setClean()` takes effect. |
| "Could not open a local port" | Another process is holding the port. Toggle off and on to pick a fresh one. |

Diagnostics from the stdio server go to **stderr**, which MCP hosts
capture in their own logs; stdout carries protocol only.
