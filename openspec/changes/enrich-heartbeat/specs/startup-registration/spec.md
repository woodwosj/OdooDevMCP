## ADDED Requirements

### Requirement: Request-Triggered Startup Registration
The `/mcp/v1/health` endpoint SHALL detect hostname changes by comparing `socket.gethostname()` against the `mcp.last_hostname` value stored in `ir.config_parameter`. If the hostname differs (indicating a server rebuild or migration), the endpoint SHALL trigger `register_server(env)` in a background daemon thread and update `mcp.last_hostname` to the current hostname. This mechanism SHALL be multi-worker safe because ICP writes are transactional.

#### Scenario: First request after rebuild triggers registration
- **WHEN** a GET request is made to `/mcp/v1/health`
- **AND** `socket.gethostname()` returns `"new-host-abc123"`
- **AND** `mcp.last_hostname` is set to `"old-host-xyz789"`
- **THEN** the endpoint SHALL call `register_server(env)` in a background thread
- **AND** update `mcp.last_hostname` to `"new-host-abc123"`
- **AND** return the normal health check response without blocking

#### Scenario: No rebuild detected skips registration
- **WHEN** a GET request is made to `/mcp/v1/health`
- **AND** `socket.gethostname()` matches `mcp.last_hostname`
- **THEN** the endpoint SHALL NOT trigger `register_server()`
- **AND** SHALL NOT write to `mcp.last_hostname`

#### Scenario: First-ever request initializes last_hostname
- **WHEN** a GET request is made to `/mcp/v1/health`
- **AND** `mcp.last_hostname` is empty or not set
- **THEN** the endpoint SHALL set `mcp.last_hostname` to the current hostname
- **AND** SHALL trigger `register_server(env)` since this is the first detection

#### Scenario: Health endpoint still returns normally
- **WHEN** the hostname change detection runs (or does not run)
- **THEN** the health endpoint SHALL still return `{"status": "healthy", "version": "1.0.0", "odoo_version": "..."}` with HTTP 200
- **AND** the response time SHALL NOT be affected by the background registration

#### Scenario: Background registration failure is non-blocking
- **WHEN** `register_server(env)` fails in the background thread
- **THEN** the failure SHALL be logged as a warning
- **AND** the health endpoint response SHALL NOT be affected
- **AND** the `mcp.last_hostname` SHALL still be updated (so the next request doesn't re-trigger)

### Requirement: Cron Hostname-Change Fallback
The heartbeat cron (`_cron_send_heartbeat()` in `models/mcp_heartbeat.py`) SHALL check if the current hostname differs from `mcp.last_hostname` before sending the heartbeat. If a change is detected, it SHALL call `register_server(self.env)` first, update `mcp.last_hostname`, and then proceed to send the enriched heartbeat. This provides a fallback for cases where no HTTP request reaches the health endpoint.

#### Scenario: Cron detects hostname change
- **WHEN** the heartbeat cron fires
- **AND** `socket.gethostname()` differs from `mcp.last_hostname`
- **THEN** `register_server(self.env)` SHALL be called first
- **AND** `mcp.last_hostname` SHALL be updated to the current hostname
- **AND** then `send_heartbeat(self.env)` SHALL be called

#### Scenario: Cron detects no hostname change
- **WHEN** the heartbeat cron fires
- **AND** `socket.gethostname()` matches `mcp.last_hostname`
- **THEN** only `send_heartbeat(self.env)` SHALL be called
- **AND** `register_server()` SHALL NOT be called

#### Scenario: Both health and cron detect change
- **WHEN** a rebuild changes the hostname
- **AND** the health endpoint detects the change first and triggers registration
- **AND** the cron fires afterwards
- **THEN** the cron SHALL see the updated `mcp.last_hostname` (written by the health endpoint)
- **AND** SHALL NOT trigger a duplicate registration

### Requirement: Last Hostname Config Parameter
The system SHALL use `ir.config_parameter` key `mcp.last_hostname` to store the last-known server hostname. This parameter SHALL be readable without authentication context (using `sudo()`) and SHALL persist across server restarts.

#### Scenario: Parameter survives server restart
- **WHEN** `mcp.last_hostname` is set to `"host-abc123"`
- **AND** the Odoo server is restarted
- **THEN** `mcp.last_hostname` SHALL still be `"host-abc123"` after restart

#### Scenario: Parameter is empty on fresh install
- **WHEN** the module is freshly installed
- **AND** `mcp.last_hostname` has never been set
- **THEN** the first hostname check SHALL treat this as a change and trigger registration
