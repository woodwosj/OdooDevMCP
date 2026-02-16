# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Odoo module (`odoo_dev_mcp`) that runs an MCP (Model Context Protocol) server inside Odoo 19's process. AI agents connect via HTTP JSON-RPC at `/mcp/v1` to execute shell commands, SQL queries, filesystem ops, and ORM code on the Odoo server. Includes a standalone Flask receiver for development phone-home testing.

## Commands

```bash
# Run tests (from project root)
pytest tests/ -v
pytest tests/test_phone_home.py -v          # single test file
pytest tests/test_security.py::test_name -v  # single test

# Deploy to VPS (155.138.201.83)
./deploy.sh

# Upgrade module on VPS after deploy
ssh -i ~/.ssh/odoo_vps root@155.138.201.83
su - odoo -s /bin/bash
/opt/odoo/odoo-venv/bin/python /opt/odoo/odoo-bin -c /etc/odoo.conf -d Loomworks -u odoo_dev_mcp --stop-after-init

# Start standalone Flask receiver (dev tool, NOT part of Odoo module)
cd receiver && pip install -r requirements.txt
python server.py                    # localhost:5000
python server.py --ngrok --port 5000  # with ngrok tunnel

# OpenSpec workflow
openspec list                                              # active changes
openspec spec list --long                                  # existing specs
openspec validate <change-id> --strict --no-interactive    # validate proposal
openspec archive <change-id> --yes                         # archive after deploy
```

## Architecture

**Request flow**: MCP Client -> `controllers/mcp_endpoint.py` (auth='bearer') -> `services/mcp_server.py` (MCPServerHandler) -> `tools/registry.py` (call_tool dispatch) -> individual tool handler

**Key architectural patterns**:

- **Tool registry**: `tools/registry.py` is the central dispatch. `get_tool_registry()` maps tool names to handler functions, `get_tool_schemas()` maps tool names to JSON schemas, `call_tool(env, name, params)` dispatches. All tool handlers receive `env` as first arg and return a dict.
- **Security layer**: Every tool handler imports `from ..security.security import audit_log, check_rate_limit` and calls both. Rate limiting is in-memory sliding window per-database. Audit logging writes to a file.
- **Config via ir.config_parameter**: All settings stored as `mcp.*` keys, editable in Settings UI via `mcp.config.settings` transient model.
- **Phone-home**: `services/phone_home.py` stores a base URL in `mcp.phone_home_url` and appends `/register` or `/heartbeat` paths. `_build_server_payload(env)` helper builds common payload fields (server_id, hostname, ip_addresses, port, transport, version, odoo_version, database, capabilities, odoo_stage) used by both registration and heartbeat. Capabilities list is dynamic from `get_tool_registry().keys()`. Import of registry is inside function body to avoid circular imports. Heartbeat payloads are enriched with full server info to enable receiver updates without re-registration.
- **Hostname change detection**: `mcp.last_hostname` ICP key stores the last-known hostname. Both `/mcp/v1/health` endpoint (via background thread) and heartbeat cron check for hostname changes (comparing `socket.gethostname()` to stored value). On change, triggers `register_server()` and updates ICP. This enables automatic re-registration after Odoo.sh rebuilds or hostname changes.
- **Cron**: `models/mcp_heartbeat.py` is an `AbstractModel` (no DB table) that provides `_cron_send_heartbeat()` called by an `ir.cron` record every 1 minute. Checks for hostname changes before sending heartbeat.
- **MCP protocol**: Hand-rolled JSON-RPC 2.0 handler in `MCPServerHandler`, NOT the `mcp` Python SDK decorator pattern. Routes: `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`.
- **Auth**: Odoo 19 native `auth='bearer'` on all endpoints except `/mcp/v1/health`. Uses Odoo API keys (`res.users.apikeys`).

**Standalone receiver** (`receiver/server.py`): Flask app for catching phone-home POSTs during development. Thread-safe in-memory storage, optional ngrok tunnel. Not part of the Odoo module. Heartbeat endpoint merges enriched fields from heartbeat payload into existing server records, supporting both slim (server_id/status/timestamp only) and enriched (full server info) formats.

## Adding a New Tool

1. Create handler in `tools/new_tool.py`: `def my_tool(env, param: str) -> dict:` with rate limit + audit log
2. Add `from . import new_tool` to `tools/__init__.py`
3. Add to both `get_tool_registry()` and `get_tool_schemas()` in `tools/registry.py`
4. Capabilities endpoint and phone-home payload auto-update (dynamic from registry)

## Critical Constraints

- **Odoo 19**: Use `auth='bearer'` and `type='jsonrpc'` (not deprecated `type='json'`). Cron XML: no `numbercall`/`doall` fields (removed in Odoo 18+).
- **Circular imports**: `services/phone_home.py` and `models/mcp_heartbeat.py` import from `tools.registry` and `services.phone_home` respectively inside function/method bodies, not at module level. `controllers/mcp_endpoint.py` imports `socket`, `threading`, and `register_server` inside `health_check()` method.
- **Odoo.sh compatible**: No systemd, no root shell, no stdio transport. HTTP only.
- **Config param namespace**: Always `mcp.*` prefix. Includes `mcp.last_hostname` for hostname change detection.
- **Access control**: Only `base.group_system` (admin) has access to `mcp.config.settings`.

## VPS Deployment

Target: `155.138.201.83`, SSH key: `~/.ssh/odoo_vps`, user: `root`, Odoo user: `odoo`
- Module path: `/opt/odoo/custom-addons/odoo_dev_mcp`
- Odoo venv: `/opt/odoo/odoo-venv`
- Database: `Loomworks`
- Odoo config: `/etc/odoo.conf`
- Health check: `curl http://155.138.201.83:8069/mcp/v1/health`

<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->
