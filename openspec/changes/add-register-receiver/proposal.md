# Change: Add register-receiver MCP tool and heartbeat infrastructure

## Why
AI agents connecting to an Odoo MCP instance have no way to dynamically register a callback URL for receiving server notifications. The phone-home infrastructure (`services/phone_home.py`) exists but has three gaps: (1) no MCP tool for agents to set the callback URL at runtime, (2) the heartbeat has no cron trigger so it never fires automatically, and (3) there is no standalone receiver server for development use. Additionally, the phone-home URL convention is inconsistent -- `register_server()` POSTs to the raw URL while `send_heartbeat()` appends `/heartbeat`, making it unclear whether the stored URL is a base URL or a full endpoint.

## What Changes
- **Fix phone-home URL convention** (`services/phone_home.py`): Store the BASE URL in `mcp.phone_home_url`. `register_server()` appends `/register` and `send_heartbeat()` appends `/heartbeat`. Make the capabilities list dynamic by reading from the tool registry instead of a hardcoded list.
- **New `register_receiver` MCP tool** (`tools/receiver.py`): Allows agents to dynamically set a receiver URL via the MCP protocol. Strips `/register` suffix if present, stores the base URL, and immediately triggers `register_server()` to POST server info to the receiver. Rate limited at 5 calls per 60 seconds.
- **Heartbeat cron job** (`models/mcp_heartbeat.py` + `data/mcp_data.xml`): An `AbstractModel` with a `_cron_send_heartbeat()` method, triggered by a new `ir.cron` record running every 1 minute. Uses Odoo 18+/19 cron format (no `numbercall`/`doall` fields).
- **Standalone Flask receiver server** (`receiver/server.py`): A development companion (NOT part of the Odoo module) that receives registration and heartbeat POSTs. Provides REST endpoints to list, inspect, and remove connected servers. Optional `--ngrok` flag for tunnel creation via pyngrok.
- **Dynamic capabilities in controller** (`controllers/mcp_endpoint.py`): Replace the hardcoded tool list in the capabilities endpoint with a dynamic read from `get_tool_registry().keys()`.

## Impact
- Affected specs: `phone-home` (URL convention fix, dynamic capabilities), `mcp-tools` (new tool), `receiver-server` (new standalone component)
- Affected code:
  - `services/phone_home.py` -- URL path convention change in `register_server()` and `send_heartbeat()`; dynamic capabilities list
  - `tools/receiver.py` -- New file: `register_receiver` tool handler
  - `tools/registry.py` -- Add `register_receiver` to both `get_tool_registry()` and `get_tool_schemas()`
  - `tools/__init__.py` -- Import new `receiver` module
  - `models/mcp_heartbeat.py` -- New file: AbstractModel for heartbeat cron
  - `models/__init__.py` -- Import new `mcp_heartbeat` module
  - `data/mcp_data.xml` -- New `ir.cron` record for heartbeat
  - `controllers/mcp_endpoint.py` -- Dynamic capabilities list
  - `receiver/server.py` -- New file: standalone Flask server (outside Odoo module)
- No database migration needed: only `ir.config_parameter` values are affected
- No breaking changes to existing MCP clients: the new tool is additive
- The URL convention change affects phone-home behavior but `mcp.phone_home_url` is typically empty (disabled) by default, so impact is minimal
