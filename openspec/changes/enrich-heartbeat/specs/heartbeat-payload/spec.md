## MODIFIED Requirements

### Requirement: Heartbeat Payload
The `send_heartbeat()` function SHALL POST a JSON payload containing the full server info from `_build_server_payload(env)` -- `server_id`, `hostname`, `ip_addresses`, `port`, `transport`, `version`, `odoo_version`, `database`, `capabilities`, `odoo_stage` -- plus heartbeat-specific fields: `status` (string, `"healthy"`), `timestamp` (ISO 8601 UTC timestamp with `Z` suffix), and `uptime_seconds` (float, seconds since module was loaded).

#### Scenario: Enriched heartbeat contains full server info
- **WHEN** `mcp.phone_home_url` is configured
- **AND** `send_heartbeat(env)` is called
- **THEN** the heartbeat payload SHALL include `hostname`, `ip_addresses`, `port`, `transport`, `version`, `odoo_version`, `database`, `capabilities`, and `odoo_stage` in addition to `server_id`, `status`, `timestamp`, and `uptime_seconds`

#### Scenario: Heartbeat includes odoo_stage from environment
- **WHEN** `send_heartbeat(env)` is called on an Odoo.sh instance
- **AND** the `ODOO_STAGE` environment variable is set to `production`
- **THEN** the heartbeat payload `odoo_stage` field SHALL be `"production"`

#### Scenario: Heartbeat includes odoo_stage empty on self-hosted
- **WHEN** `send_heartbeat(env)` is called on a self-hosted instance
- **AND** the `ODOO_STAGE` environment variable is not set
- **THEN** the heartbeat payload `odoo_stage` field SHALL be `""`

#### Scenario: Heartbeat includes uptime
- **WHEN** `send_heartbeat(env)` is called
- **AND** the server process has been running for 300 seconds
- **THEN** the heartbeat payload `uptime_seconds` field SHALL be approximately `300.0`

#### Scenario: Successful enriched heartbeat
- **WHEN** `mcp.phone_home_url` is configured
- **AND** `send_heartbeat(env)` is called
- **AND** the remote endpoint responds with HTTP 200 or 201
- **THEN** the function SHALL return `True`

#### Scenario: Failed heartbeat
- **WHEN** the remote endpoint is unreachable or returns an error
- **THEN** the function SHALL return `False` and log a warning (no retry for heartbeats)

## ADDED Requirements

### Requirement: Shared Server Payload Builder
The `services/phone_home.py` module SHALL provide a `_build_server_payload(env) -> dict` private helper function that returns a dict containing: `server_id` (string, `{dbname}_{hostname}`), `hostname` (string), `ip_addresses` (object with `primary` and `all` keys), `port` (integer from `mcp.server_port`), `transport` (string, `"http/sse"`), `version` (string, `"1.0.0"`), `odoo_version` (string from `odoo.release`), `database` (string, database name), `capabilities` (list of tool names from `get_tool_registry().keys()`), and `odoo_stage` (string from `ODOO_STAGE` env var, empty string if not set). Both `register_server()` and `send_heartbeat()` SHALL use this helper to build their payloads.

#### Scenario: Payload builder returns all required fields
- **WHEN** `_build_server_payload(env)` is called
- **THEN** the returned dict SHALL contain all of: `server_id`, `hostname`, `ip_addresses`, `port`, `transport`, `version`, `odoo_version`, `database`, `capabilities`, `odoo_stage`

#### Scenario: Registration payload uses shared builder
- **WHEN** `register_server(env)` is called
- **THEN** the registration payload SHALL contain all fields from `_build_server_payload(env)` plus `started_at` (ISO 8601 UTC timestamp)

#### Scenario: Heartbeat payload uses shared builder
- **WHEN** `send_heartbeat(env)` is called
- **THEN** the heartbeat payload SHALL contain all fields from `_build_server_payload(env)` plus `status`, `timestamp`, and `uptime_seconds`

### Requirement: Server Uptime Tracking
The `services/phone_home.py` module SHALL define a module-level `_server_start_time` variable (set to `time.time()` at import time) used to calculate `uptime_seconds` in heartbeat payloads.

#### Scenario: Uptime increases between heartbeats
- **WHEN** two consecutive heartbeats are sent 60 seconds apart
- **THEN** the second heartbeat's `uptime_seconds` SHALL be approximately 60 seconds greater than the first

### Requirement: Odoo Stage Detection
The shared payload builder SHALL read the `ODOO_STAGE` environment variable (set by Odoo.sh to `dev`, `staging`, or `production`) and include it in the payload as `odoo_stage`. If the variable is not set, the value SHALL be an empty string.

#### Scenario: Odoo.sh production stage detected
- **WHEN** `ODOO_STAGE` is set to `production`
- **AND** `_build_server_payload(env)` is called
- **THEN** the returned dict `odoo_stage` field SHALL be `"production"`

#### Scenario: Non-Odoo.sh environment
- **WHEN** `ODOO_STAGE` is not set
- **AND** `_build_server_payload(env)` is called
- **THEN** the returned dict `odoo_stage` field SHALL be `""`

### Requirement: Receiver Enriched Heartbeat Merge
The receiver's `POST /heartbeat` endpoint SHALL merge enriched heartbeat fields (`hostname`, `ip_addresses`, `capabilities`, `odoo_version`, `port`, `transport`, `odoo_stage`) into the existing server record when present in the payload. Fields not present in the heartbeat SHALL be preserved from the existing record. The `last_seen` timestamp and `heartbeat_count` SHALL always be updated.

#### Scenario: Enriched heartbeat updates server record
- **WHEN** an enriched heartbeat is received with a new `hostname` value
- **AND** the `server_id` exists in the receiver's storage
- **THEN** the server record's `hostname` field SHALL be updated to the new value
- **AND** `last_seen` SHALL be updated
- **AND** `heartbeat_count` SHALL be incremented

#### Scenario: Slim heartbeat preserves existing record
- **WHEN** a slim heartbeat is received containing only `server_id`, `status`, and `timestamp`
- **AND** the `server_id` exists with `hostname` set to `"old-host"`
- **THEN** the server record's `hostname` field SHALL remain `"old-host"`
- **AND** `last_seen` SHALL be updated
- **AND** `heartbeat_count` SHALL be incremented

#### Scenario: Unknown server with enriched heartbeat
- **WHEN** an enriched heartbeat is received for an unknown `server_id`
- **THEN** the receiver SHALL create a new record with all enriched fields from the payload
- **AND** set `heartbeat_count` to 1
