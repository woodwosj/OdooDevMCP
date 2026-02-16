## Context

The Odoo Dev MCP module phones home to a fleet receiver on module installation and sends slim heartbeats every minute via cron. On Odoo.sh, server rebuilds change the hostname and potentially IP addresses, but neither the heartbeat nor any startup mechanism informs the receiver. This means the receiver's view of the fleet becomes stale after any infrastructure event.

This is a cross-cutting change affecting the phone-home service, the health controller endpoint, the heartbeat cron model, and the standalone receiver server.

Stakeholders: DevOps engineers monitoring MCP fleet state; AI agents relying on fleet discovery.

## Goals / Non-Goals

**Goals:**
- Heartbeat payload includes full server info (hostname, IPs, capabilities, versions, odoo_stage) so the receiver can update its records without a fresh registration
- After an Odoo.sh rebuild, the receiver gets updated hostname/IP within 1 minute (via cron) or on first request (via health endpoint)
- Common payload-building logic is shared between `register_server()` and `send_heartbeat()` to avoid drift
- Receiver merges enriched heartbeat data into server records, handling both old slim and new enriched formats
- Multi-worker safe: no deadlocks, no duplicate registrations

**Non-Goals:**
- Adding `post_load` hook (research shows no DB access available, risky with multi-worker forks)
- Persistent hostname tracking beyond ICP (no new database models)
- Authentication on the receiver (separate concern)
- Modifying the registration payload structure (only heartbeat changes)

## Decisions

### Decision 1: Shared `_build_server_payload(env)` helper

Extract the common fields (server_id, hostname, ip_addresses, port, transport, version, odoo_version, database, capabilities, odoo_stage) into a private `_build_server_payload(env)` function. Both `register_server()` and `send_heartbeat()` call this helper. `register_server()` adds `started_at`; `send_heartbeat()` adds `status`, `timestamp`, `uptime_seconds`.

**Alternatives considered:**
- Duplicate payload construction in both functions -- rejected because fields will drift over time
- Pass the full registration payload to heartbeat -- rejected because heartbeat has different semantics (status vs. started_at)

**Rationale:** DRY principle. A single helper ensures both payloads stay aligned when new fields are added.

### Decision 2: Request-triggered registration via health endpoint

The `/mcp/v1/health` endpoint (auth='none') reads `socket.gethostname()` and compares to `mcp.last_hostname` in ICP. If different, it triggers `register_server()` in a background thread and updates the ICP value. This fires on the first request after any rebuild.

**Alternatives considered:**
- `post_load` hook -- rejected because it has no database access and risks deadlocks in multi-worker mode
- Module-level flag in Python memory -- rejected because each forked worker has its own memory space; a process-local flag would cause each worker to independently trigger registration
- File-based locking (`/tmp/odoo_init.lock`) -- rejected because Odoo.sh containers may not share `/tmp` across workers, and file locks add complexity

**Rationale:** ICP is transactional and shared across all workers via the database. The health endpoint is always the first thing hit after a deployment (monitoring probes, load balancer checks). The `auth='none'` means no API key needed, so automated health checks trigger it naturally. Background thread avoids blocking the health response.

### Decision 3: Hostname change detection in ICP (`mcp.last_hostname`)

Store the last-known hostname in `ir.config_parameter` key `mcp.last_hostname`. Both the health endpoint and the cron check this value. If it differs from `socket.gethostname()`, a rebuild happened.

**Alternatives considered:**
- Compare against the server_id in the registration payload -- rejected because server_id includes the hostname, creating a chicken-and-egg problem
- Use a file marker (`/tmp/.mcp_registered`) -- rejected because ephemeral storage may be cleared

**Rationale:** ICP survives server restarts and is the standard Odoo mechanism for persistent configuration. The comparison is cheap (string equality) and idempotent.

### Decision 4: Cron heartbeat as hostname-change fallback

The cron `_cron_send_heartbeat()` also checks for hostname changes before sending the heartbeat. If a change is detected, it calls `register_server()` first, then sends the enriched heartbeat. This ensures the receiver is updated even if no HTTP request hits the health endpoint.

**Rationale:** On Odoo.sh, the cron worker starts independently of HTTP workers. If no external request arrives (e.g., during a staging build with no traffic), the cron is the only mechanism that fires. Having both triggers (health + cron) provides defense in depth.

### Decision 5: Receiver merges enriched heartbeat data

When the receiver gets an enriched heartbeat (one that includes `hostname`, `ip_addresses`, etc.), it merges those fields into the existing server record. This updates the receiver's view without requiring a full re-registration.

**Alternatives considered:**
- Require explicit re-registration for any data update -- rejected because it adds latency and complexity
- Replace the entire record on heartbeat -- rejected because it would lose metadata like `registered_at` and `heartbeat_count`

**Rationale:** Merge is the least disruptive approach. Old slim heartbeats (only `server_id`, `status`, `timestamp`) still work because the merge only updates fields that are present in the payload.

### Decision 6: `uptime_seconds` in heartbeat

Heartbeat includes `uptime_seconds` calculated as time since the module's Python module was loaded (using a module-level `_server_start_time = time.time()` in `phone_home.py`). This is a rough proxy for Odoo process uptime.

**Rationale:** Useful for the receiver to distinguish between a freshly-restarted server (low uptime) and a long-running one. The module-level timestamp is set once when `phone_home.py` is first imported, which happens during Odoo's module loading.

### Decision 7: `odoo_stage` from environment variable

Include `os.environ.get('ODOO_STAGE', '')` in the payload. On Odoo.sh this is `dev`, `staging`, or `production`. On self-hosted instances it is empty string.

**Rationale:** Helps the receiver distinguish between environments without requiring manual configuration.

## Risks / Trade-offs

- **Health endpoint triggers DB write** -- The hostname check reads ICP (fast, cached) and only writes on change (rare). The background thread prevents blocking. Risk: if the health endpoint is called before the database is ready (extremely unlikely in normal Odoo boot), it could fail silently.
- **Cron and health may both detect the change** -- Both trigger `register_server()`. This results in at most 2 registrations, which is idempotent (the receiver overwrites on re-registration). Acceptable trade-off for reliability.
- **`_server_start_time` is per-process** -- In multi-worker mode, each worker has its own start time. The cron worker's start time is used for heartbeat uptime. This is acceptable since the cron worker is the one sending heartbeats.
- **Backwards compatibility** -- Old receivers that don't expect enriched heartbeat fields will simply ignore them (they only read `server_id`, `status`, `timestamp`). New receivers handle both formats.

## Open Questions

- None. All decisions are resolved based on research findings and codebase patterns.
