## 1. Phone-Home URL Convention Fix

- [x] 1.1 Update `register_server()` in `services/phone_home.py` to append `/register` to the base URL stored in `mcp.phone_home_url` before POSTing
- [x] 1.2 Update `send_heartbeat()` in `services/phone_home.py` to treat `mcp.phone_home_url` as a base URL and append `/heartbeat` (remove the existing conditional append logic)
- [x] 1.3 Make the capabilities list in `register_server()` dynamic by calling `get_tool_registry().keys()` (import inside the function body to avoid circular imports)
- [x] 1.4 Create or update `test_phone_home.py` to cover URL path appending behavior (`/register` and `/heartbeat` suffixes)

## 2. New `register_receiver` MCP Tool

- [x] 2.1 Create `tools/receiver.py` with `register_receiver(env, receiver_url: str) -> dict` handler following the project tool pattern (env first arg, rate limiting, audit logging, returns dict)
- [x] 2.2 Handler logic: strip trailing `/register` from `receiver_url` if present, store base URL in `mcp.phone_home_url` via `ir.config_parameter`, call `register_server(env)`, return success dict with `server_id`, `url_stored`, and `heartbeat_schedule` info
- [x] 2.3 Add rate limiting: `check_rate_limit(env, 'register_receiver', max_calls=5, period=60)`
- [x] 2.4 Add audit logging: `audit_log(env, tool='register_receiver', receiver_url=receiver_url)`
- [x] 2.5 Register in `tools/registry.py`: add `register_receiver` entry to `get_tool_registry()` dict
- [x] 2.6 Register schema in `tools/registry.py`: add `register_receiver` entry to `get_tool_schemas()` dict with `receiver_url` as required string parameter
- [x] 2.7 Add `from . import receiver` to `tools/__init__.py`

## 3. Heartbeat Cron Job

- [x] 3.1 Create `models/mcp_heartbeat.py` with `AbstractModel` class: `_name = 'mcp.heartbeat'`, `_description = 'MCP Heartbeat Cron'`
- [x] 3.2 Implement `_cron_send_heartbeat(self)` method that calls `send_heartbeat(self.env)` from `services/phone_home.py`
- [x] 3.3 Add `from . import mcp_heartbeat` to `models/__init__.py`
- [x] 3.4 Add `ir.cron` record to `data/mcp_data.xml` in a `<data noupdate="0">` block: name "MCP: Send Heartbeat", active True, user_id ref `base.user_root`, interval_number 1, interval_type minutes, model_id ref `model_mcp_heartbeat`, state "code", code `model._cron_send_heartbeat()`

## 4. Standalone Flask Receiver Server

- [x] 4.1 Create `receiver/server.py` with Flask app: `POST /register`, `POST /heartbeat`, `GET /servers`, `GET /servers/<id>`, `DELETE /servers/<id>`, `GET /health`
- [x] 4.2 Implement thread-safe in-memory storage using `threading.Lock` and a dict keyed by `server_id`
- [x] 4.3 `POST /register` stores full server info payload in memory dict, updates `registered_at` and `last_seen` timestamps
- [x] 4.4 `POST /heartbeat` updates `last_seen` timestamp and increments `heartbeat_count` for the given `server_id`
- [x] 4.5 `GET /servers` lists all servers with staleness indicators (stale if last_seen > 2 minutes ago)
- [x] 4.6 `GET /servers/<id>` returns single server details or 404
- [x] 4.7 `DELETE /servers/<id>` removes a server from the dict or returns 404
- [x] 4.8 `GET /health` returns receiver health status with uptime and server count
- [x] 4.9 Add `--ngrok` flag via argparse to auto-create tunnel with pyngrok; print tunnel URL on startup
- [x] 4.10 Add `--port` flag (default 5000) and `--debug` flag via argparse
- [x] 4.11 Add `if __name__ == '__main__':` block with argument parsing and Flask app startup

## 5. Dynamic Capabilities in Controller

- [x] 5.1 Update `controllers/mcp_endpoint.py` `capabilities()` method to read tool list from `get_tool_registry().keys()` instead of hardcoded list
- [x] 5.2 Add import for `get_tool_registry` from `..tools.registry`

## 6. Testing and Verification

- [x] 6.1 Verify all existing tests pass after phone-home URL convention change
- [x] 6.2 Test `register_receiver` tool manually via MCP client or `odoo_shell`
- [x] 6.3 Test Flask receiver server standalone: start, register, heartbeat, list, delete
- [x] 6.4 Test Flask receiver with `--ngrok` flag (requires ngrok auth token)
- [x] 6.5 Verify heartbeat cron triggers correctly after module install/upgrade
- [x] 6.6 Write unit tests for `register_receiver` tool handler (URL normalization, rate limiting, empty/invalid URL rejection)
- [x] 6.7 Write unit tests for `_cron_send_heartbeat()` method
