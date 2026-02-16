# Change: Enrich heartbeat payload and add request-triggered startup registration

## Why
After an Odoo.sh rebuild, the server hostname changes but the heartbeat payload only sends `server_id`, `status`, and `timestamp` -- the receiver loses track of which server it is talking to. There is also no mechanism to re-register the server after a rebuild since `post_init_hook` only runs on module installation, not on server restarts. The receiver needs enriched heartbeat data and a startup registration trigger to maintain accurate fleet state after infrastructure changes.

## What Changes
- **Enrich heartbeat payload** (`services/phone_home.py`): Extract common payload-building into a `_build_server_payload(env)` helper used by both `register_server()` and `send_heartbeat()`. The heartbeat now includes hostname, IP addresses, capabilities, odoo_version, database, port, transport, and odoo_stage (from `ODOO_STAGE` env var), plus heartbeat-specific fields (`status`, `timestamp`, `uptime_seconds`).
- **Request-triggered startup registration** (`controllers/mcp_endpoint.py`, `services/phone_home.py`): On the health endpoint (`/mcp/v1/health`), check if the current hostname differs from the last known hostname stored in `mcp.last_hostname`. If different (rebuild happened), trigger `register_server()` and update the ICP value. This is multi-worker safe because ICP writes are transactional.
- **Cron-based hostname change detection** (`models/mcp_heartbeat.py`): The cron heartbeat also checks for hostname changes as a fallback, triggering `register_server()` if a change is detected before sending the enriched heartbeat.
- **Receiver update** (`receiver/server.py`): The heartbeat endpoint merges enriched data into the existing server record so the receiver always has the latest hostname and IP addresses, with backwards compatibility for old slim heartbeats.

## Impact
- Affected specs: `phone-home` (heartbeat payload structure, new helper), `receiver-server` (heartbeat merge behavior)
- Affected code:
  - `services/phone_home.py` -- New `_build_server_payload()` helper; `send_heartbeat()` enriched payload; new `get_server_hostname()` helper
  - `controllers/mcp_endpoint.py` -- Health endpoint triggers startup registration on hostname change
  - `models/mcp_heartbeat.py` -- Cron checks hostname change before sending heartbeat
  - `receiver/server.py` -- Heartbeat endpoint merges enriched data into server records
  - `__init__.py` -- No changes needed (post_init_hook remains as-is)
  - `__manifest__.py` -- No changes needed
- No database migration needed: only `ir.config_parameter` values are affected (new key `mcp.last_hostname`)
- No breaking changes to existing MCP clients or receiver API
- Backwards compatible: old slim heartbeats still work with receiver; enriched heartbeats are additive
