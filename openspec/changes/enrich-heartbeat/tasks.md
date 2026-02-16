## 1. Enrich Heartbeat Payload

- [ ] 1.1 Add `_server_start_time = time.time()` module-level variable to `services/phone_home.py` for uptime calculation
- [ ] 1.2 Add `import os, time` to `services/phone_home.py` (move `time` import from inside `register_server` to module level)
- [ ] 1.3 Create `_build_server_payload(env) -> dict` helper in `services/phone_home.py` that returns: `server_id`, `hostname`, `ip_addresses`, `port`, `transport`, `version`, `odoo_version`, `database`, `capabilities`, `odoo_stage`
- [ ] 1.4 Refactor `register_server()` to call `_build_server_payload(env)` and add `started_at` field
- [ ] 1.5 Refactor `send_heartbeat()` to call `_build_server_payload(env)` and add `status`, `timestamp`, `uptime_seconds` fields
- [ ] 1.6 Add `get_server_hostname() -> str` convenience function to `services/phone_home.py` that returns `socket.gethostname()`

## 2. Request-Triggered Startup Registration

- [ ] 2.1 In `controllers/mcp_endpoint.py` `health_check()` method, after building the health response, check if `socket.gethostname()` differs from `mcp.last_hostname` ICP value
- [ ] 2.2 If hostname changed, call `register_server(env)` in a background `threading.Thread` (daemon=True) and update `mcp.last_hostname` ICP value to current hostname
- [ ] 2.3 Add necessary imports to `controllers/mcp_endpoint.py`: `socket`, `threading`, and `register_server` from `..services.phone_home`
- [ ] 2.4 Ensure the health endpoint still returns `auth='none'` -- the ICP read uses `sudo()` internally

## 3. Cron Hostname-Change Fallback

- [ ] 3.1 In `models/mcp_heartbeat.py` `_cron_send_heartbeat()`, before calling `send_heartbeat()`, check if `socket.gethostname()` differs from `mcp.last_hostname` ICP value
- [ ] 3.2 If hostname changed, call `register_server(self.env)` first and update `mcp.last_hostname`
- [ ] 3.3 Add `import socket` to `models/mcp_heartbeat.py`

## 4. Receiver Enriched Heartbeat Handling

- [ ] 4.1 In `receiver/server.py` `heartbeat()` function, when updating an existing server record, merge any enriched fields from the heartbeat payload (`hostname`, `ip_addresses`, `capabilities`, `odoo_version`, `port`, `transport`, `odoo_stage`) into the server record
- [ ] 4.2 Ensure backwards compatibility: if the heartbeat is a slim payload (only `server_id`, `status`, `timestamp`), the existing record fields are preserved unchanged
- [ ] 4.3 Update the unknown-server creation path to also capture any enriched fields from the heartbeat

## 5. Testing

- [ ] 5.1 Add unit tests for `_build_server_payload()`: verify all expected fields are present, `odoo_stage` reads from env var, capabilities are dynamic
- [ ] 5.2 Add unit tests for enriched `send_heartbeat()`: verify payload includes full server info plus `status`, `timestamp`, `uptime_seconds`
- [ ] 5.3 Add unit tests for hostname-change detection in health endpoint: mock `socket.gethostname()` to return a new hostname, verify `register_server()` is called
- [ ] 5.4 Add unit tests for hostname-change detection in cron: mock hostname change, verify `register_server()` is called before `send_heartbeat()`
- [ ] 5.5 Add unit tests for receiver heartbeat merge: verify enriched fields are merged into existing record, slim heartbeats leave existing fields unchanged
- [ ] 5.6 Verify all existing tests still pass: `pytest tests/ -v`

## 6. CLAUDE.md Update

- [ ] 6.1 Update CLAUDE.md architecture section to document `_build_server_payload()` helper, `mcp.last_hostname` ICP key, and health-endpoint startup registration pattern
