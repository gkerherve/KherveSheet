# Using KherveSheet from any AI assistant (MCP)

KherveSheet ships an [MCP](https://modelcontextprotocol.io) server, so
assistants other than the built-in AI chat — Claude Desktop, Claude
Code, Cursor, Zed, Continue, or anything else that speaks the Model
Context Protocol — can read and edit an open workbook directly.

An MCP client gets 36 tools — the 28 the built-in chat uses, plus
eight it does not (marked * below). The chat sits inside the window,
where File ▸ Save and the Tools menu are a click away and the user is
driving; an MCP client has no window and no menus, so those eight are
the only way it can reach the same features.

- **The grid** — read and write cells, formulas and `=PY` Python
  cells, formatting, table styles, column widths, merges.
- **Interactive cells** — `insert_control` makes checkboxes,
  dropdowns and buttons. Their values are ordinary cell text
  (`TRUE`/`FALSE`, or the chosen option), so a formula or a `=PY` cell
  can act on whatever the user picks. A checkbox says what a setting
  *is*; a button says *do this now* — clicking one writes a value into
  another cell, re-runs a `=PY` cell, or both, which is how a sheet
  gets a working control panel.
- **Charts** — the whole system, not just creation.
  `insert_chart` takes the title, axis labels, size and position in the
  same call and names each series after the header cell above its
  column. `style_chart` reaches every series (colour, line style,
  marker, plot type, area fill), the legend, the fonts and a named
  preset (`clean`, `minimal`, `publication`, `dark`). `modify_chart`
  covers axes, limits, geometry and layout. Beyond that:
  `add_chart_series` / `remove_chart_series` grow and shrink a plot
  without rebuilding it, `add_trendline` fits a curve onto the chart
  with its equation and R², `configure_axis` exposes the full Axis
  Properties surface (tick formats, minor ticks, both gridlines,
  spines, the secondary label), `annotate_chart` places text, arrows
  and lines at data coordinates, and `export_chart` writes PNG/SVG/PDF.
  `list_charts`, `get_chart_details` and `clone_chart` inspect and
  copy.
- **Analysis*** — `run_solver` (Excel-style optimisation),
  `fit_trendline` (23 regression models with goodness-of-fit),
  `fit_peaks` (lmfit peak fitting over a Shirley/ALS/polynomial
  background). These run the same code the Solver and Curve Fitting
  dialogs run; they just do it without the dialog.
- **The document*** — `get_document_info`, `save_workbook`,
  `open_workbook`, `new_workbook`.
- **Discovery** — `search_functions`, `get_function_details` and
  `list_fit_models`*, so a client that has never seen KherveSheet can
  look up exact names instead of guessing.

Everything a tool changes lands on the shared undo stack, so **Ctrl+Z
in KherveSheet reverts a remote assistant's change** just like your own.

## How it fits together

There are two doors into the same bridge:

```
 MCP host  ──stdio──▶  khervesheet.mcp_server  ──loopback TCP──▶  KherveSheet
(Claude Desktop,       (short-lived process                       (your open
 Cline, VS Code, …)     the host owns)                             workbook)

 MCP host  ──HTTP POST──────────────────────────────────────────▶  KherveSheet
(Open WebUI, n8n, …)   http://127.0.0.1:<port>/mcp                (same tools)
```

Same tools, same access level, same undo macros — the HTTP endpoint is
a second skin on the bridge, not a wider one. It binds to 127.0.0.1,
requires the same bearer token, and validates `Origin` so a web page
in your browser cannot drive the workbook (a local HTTP server needs no
CORS preflight, which is the DNS-rebinding hole the MCP spec warns
about). Copy URL and token from **Configuration for: URL only**.

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

1. **AI ▸ Connect to Claude (Simple)…**
2. Tick **Let assistants connect to this workbook**. The setting is
   remembered, so the bridge comes back automatically next launch.
3. Leave the access level on **Full** — the recommended setting (see
   **Access levels** below).
4. Pick your application under **Connect an application** and press
   **Connect**.
5. Restart it, then **mention KherveSheet in the chat**.

KherveSheet writes the entry into the host's own settings, so there is
no config file to edit by hand — it knows its own executable path,
which is the part a hand-edit usually gets wrong. Claude Desktop,
Cursor and Windsurf are edited directly; Claude Code goes through the
`claude` CLI, which owns the shape of `~/.claude.json`.

Every write backs the file up first (`.khervesheet-<timestamp>.bak`
beside it), replaces it atomically, and leaves your other servers and
unrelated settings alone. A config file that will not parse is reported
rather than overwritten.

## Then say "KherveSheet" in the chat

This is the step with no visible cue, and the one that makes a correct
setup look broken. Claude does not go looking for a spreadsheet on its
own — the tools are there, but nothing points at them until the
conversation does:

> in KherveSheet, chart column B against column A

From that first mention it keeps working in the workbook you have open,
so the rest of the conversation is ordinary — *"fit a straight line
to it"*, *"format the header row"*. If it answers with instructions
instead of doing anything, it has not connected: check the box above is
ticked and that the host was restarted.

**Zed is the exception.** Its settings file allows comments, which
rewriting would silently discard, so KherveSheet refuses to touch it —
copy the snippet in by hand.

Restart the host afterwards: hosts read their tool list once at
startup, so a newly connected one shows no tools until it reconnects.

The dialog also shows a running log of what connected clients have
actually called.

## Access levels

| Level | A connected client can |
| --- | --- |
| **Read only** | Inspect the workbook. No changes at all. |
| **Edit** | Read, write, format, chart, fit, solve, save — but **not** run Python. |
| **Full** (default, recommended) | Everything, including `set_python_cell`. |

`=PY` cells execute real Python inside KherveSheet's own process, with
the filesystem and network reach of the application. Granting
**Full** gives the connected assistant the same code-execution reach as
the built-in chat, so connect only applications you trust.

**Full is the default**, because a spreadsheet assistant that cannot
run Python cannot do half of what people connect it for, and `=PY` is
the app's own feature — the same code you run by typing it. Note
this is a wider grant than the sibling apps make: in KherveCAD and
KhervePaint the edit→full line is the filesystem, here it is code
execution in this process. **Edit** is the level to pick on a shared
machine, or for a client you are still sizing up.

Cell *text* starting with `=PY` runs exactly the same way, so
`write_cells` and `set_formula` refuse it below **Full** too — a client
cannot reach Python by writing the marker into a cell instead.

Tools above the current level are withheld from `tools/list` and
refused if called anyway, with an error naming the setting. Hosts cache
the tool list from startup, so *widening* access takes effect on their
next reconnect; *narrowing* it takes effect immediately.

## Which clients work

Any MCP client that runs **on your machine**, whatever model it drives.
That matters more than it sounds: the model is not the constraint, the
client is. Someone using GPT, Mistral or Grok reaches KherveSheet
through Cline, VS Code, LM Studio or any other local client with their
own API key.

Cloud assistants are the exception, and it is a hard one. ChatGPT
connectors, Mistral's custom connectors and Grok's Bring Your Own MCP
all require a **publicly reachable HTTPS URL** and cannot spawn a local
process. KherveSheet drives a live window on your desk, so there is
nothing for them to reach without tunnelling your workbook to the
internet — which would put a bridge that can run Python in this process
behind a public URL. That is not supported, on purpose.

### Configuring by hand

The dialog still shows the snippet, for Zed, for a machine you are
setting up remotely, or for a host KherveSheet does not know about.
Paste it into the host's config file (`claude_desktop_config.json` for
Claude Desktop) and restart it:

```json
{
  "mcpServers": {
    "khervesheet": {
      "command": "/path/to/python",
      "args": ["-m", "khervesheet.mcp_server"],
      "env": {"PYTHONPATH": "/path/to/KherveSheet"}
    }
  }
}
```

`PYTHONPATH` — not `cwd` — is what makes `-m khervesheet.mcp_server`
resolve. The host chooses the working directory and is free to ignore a
`cwd` key (Claude Code does), and without an importable checkout the
process exits before it can answer `initialize`, which the host reports
as *Server disconnected*.

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
claude mcp add khervesheet -e PYTHONPATH="/path/to/KherveSheet" -- /path/to/python -m khervesheet.mcp_server
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
| "Refused: that cell text starts with '=PY'" | Running Python needs **Full** access, and `set_python_cell` is the tool for it. |
| A `=PY` cell returns `#PYERR` on a `=PY(...)` one-liner | Not a sandbox limit. A `=PY` cell is a plain multi-line script; there is no call syntax, so anything with a statement in it is a `SyntaxError`. |
| Saving reports success but the title still shows a modified document | Should not happen — file it. Document tools deliberately run outside the undo macro so `setClean()` takes effect. |
| "Could not open a local port" | Another process is holding the port. Toggle off and on to pick a fresh one. |

Diagnostics from the stdio server go to **stderr**, which MCP hosts
capture in their own logs; stdout carries protocol only.
