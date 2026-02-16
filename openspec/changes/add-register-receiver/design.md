## Context

The Odoo Dev MCP module already has phone-home infrastructure that registers the server with a remote endpoint on module install. However, AI agents connecting via MCP have no runtime mechanism to tell the Odoo server "send your registration and heartbeats to my URL." This change adds that capability along with supporting infrastructure: a heartbeat cron, a URL convention fix, and a standalone development receiver.

This is a cross-cutting change affecting the Odoo module (new tool, new model, modified service, modified controller) and introducing a standalone Flask companion server outside the module boundary.

Stakeholders: AI agent developers who connect to Odoo MCP instances and need fleet discovery / callback notifications.

## Goals / Non-Goals

**Goals:**
- Allow agents to dynamically register a receiver URL via MCP tool call
- Automate heartbeat sending via Odoo cron (1-minute interval)
- Provide a ready-to-use development receiver server with optional ngrok tunneling
- Fix the inconsistent URL convention in phone-home so both registration and heartbeat use path-based routing from a single base URL
- Make the capabilities/tool list dynamic so new tools are automatically reflected

**Non-Goals:**
- Authentication on the receiver server (development tool only)
- Persistent storage in the receiver (in-memory only, no database)
- Receiver high availability or clustering
- Phone-home auth tokens (tracked separately, not in scope)
- Modifying the MCP protocol or JSON-RPC handling

## Decisions

### Decision 1: Base URL convention for `mcp.phone_home_url`

Store the **base URL** (e.g., `https://abc123.ngrok.io`) in `mcp.phone_home_url`. Both `register_server()` and `send_heartbeat()` append their respective paths (`/register`, `/heartbeat`).

**Alternatives considered:**
- Store full endpoint URLs separately for register and heartbeat -- rejected because it creates redundancy and drift risk
- Keep current behavior (raw URL for register, append `/heartbeat`) -- rejected because it is inconsistent and confusing

**Rationale:** A single base URL is simpler to configure, easier to validate, and follows standard REST convention where the server advertises a single origin.

### Decision 2: `register_receiver` tool strips `/register` suffix

If an agent passes `https://abc123.ngrok.io/register` as the receiver URL, the tool strips the `/register` suffix before storing. This prevents double-pathing when `register_server()` later appends `/register`.

**Rationale:** Defensive normalization. Agents may copy the full registration endpoint URL from receiver output; the tool should handle both forms gracefully.

### Decision 3: AbstractModel for heartbeat cron

Use `AbstractModel` (not `Model`) for `mcp.heartbeat` because it needs no database table -- it only provides a cron method.

**Alternatives considered:**
- Use `TransientModel` -- rejected because transient models create database tables for temporary records, which is unnecessary here
- Put the cron method on the existing `mcp.config.settings` model -- rejected because it conflates configuration UI concerns with cron logic

**Rationale:** `AbstractModel` is the standard Odoo pattern for models that only provide methods (no ORM storage). It keeps the cron logic isolated and testable.

### Decision 4: Cron uses `noupdate="0"`

The heartbeat cron record uses `<data noupdate="0">` so it updates on module upgrade. This means administrators' manual changes to interval will be overwritten on upgrade.

**Rationale:** For a development tool, consistent behavior across upgrades is more important than preserving manual tweaks. Administrators who need custom intervals can modify the cron after upgrade or override via `ir.config_parameter`.

### Decision 5: Receiver server is standalone (not in the Odoo module)

The Flask receiver lives in `receiver/` at the project root, outside the Odoo module directory structure. It is a development companion, not deployed to Odoo.sh.

**Alternatives considered:**
- Embed receiver as an Odoo controller endpoint -- rejected because it creates a circular dependency (Odoo sending to itself) and the receiver is meant to run on the agent's machine
- Create a separate Python package -- rejected as over-engineering for a single-file dev tool

**Rationale:** The receiver runs on the developer/agent side, not on the Odoo server. Keeping it outside the module makes this separation explicit and avoids packaging it in the Odoo module distribution.

### Decision 6: Import `get_tool_registry` inside function body

In `services/phone_home.py`, the import of `get_tool_registry` from `tools.registry` is done inside the `register_server()` function body rather than at module level.

**Rationale:** Avoids circular import issues. The tools module imports from services in some paths, and a top-level import from services back to tools would create a cycle.

## Risks / Trade-offs

- **In-memory receiver storage** -- Data is lost on receiver restart. This is acceptable for a development tool. If persistence is needed later, it can be added with SQLite or a JSON file.
- **1-minute heartbeat interval** -- May be too frequent for production use. Mitigated by: heartbeat only fires when `mcp.phone_home_url` is set (disabled by default), and the interval can be changed in the Odoo cron UI.
- **No auth on receiver** -- The receiver accepts any POST. Acceptable for local development; should not be exposed to the public internet without ngrok's built-in auth or additional middleware.
- **URL convention is a behavioral change** -- If any existing deployment has `mcp.phone_home_url` set to a full endpoint URL (not a base URL), the registration will break after this change. Mitigated by: the URL is empty by default, and the feature is only used in development contexts where reconfiguration is trivial.

## Open Questions

- None. All architectural decisions are resolved based on codebase patterns and research findings.
