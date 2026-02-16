## ADDED Requirements

### Requirement: Standalone Flask Receiver Server
The project SHALL provide a standalone Flask server at `receiver/server.py` (outside the Odoo module) that acts as a development companion for receiving phone-home registration and heartbeat notifications from Odoo MCP instances. The server SHALL NOT be part of the Odoo module package.

#### Scenario: Server starts on default port
- **WHEN** the receiver is started with `python receiver/server.py`
- **THEN** the Flask server SHALL listen on port 5000 by default
- **AND** print the base URL to stdout

#### Scenario: Server starts on custom port
- **WHEN** the receiver is started with `python receiver/server.py --port 8080`
- **THEN** the Flask server SHALL listen on port 8080

### Requirement: Registration Endpoint
The receiver SHALL expose `POST /register` that accepts a JSON payload containing server registration data (server_id, hostname, ip_addresses, port, transport, version, odoo_version, database, capabilities, started_at). The endpoint SHALL store the payload in an in-memory dict keyed by `server_id`, adding `registered_at` and `last_seen` timestamps.

#### Scenario: Receive server registration
- **WHEN** a POST request is sent to `/register` with a JSON payload containing `server_id`
- **THEN** the server SHALL store the payload in memory keyed by `server_id`
- **AND** set `registered_at` and `last_seen` to the current UTC timestamp
- **AND** return HTTP 200 with a JSON response containing `status: "registered"` and `server_id`

#### Scenario: Re-registration updates existing entry
- **WHEN** a POST request is sent to `/register` with a `server_id` that already exists
- **THEN** the server SHALL overwrite the existing entry with the new payload
- **AND** update `registered_at` and `last_seen` timestamps

### Requirement: Heartbeat Endpoint
The receiver SHALL expose `POST /heartbeat` that accepts a JSON payload containing `server_id`, `status`, and `timestamp`. The endpoint SHALL update the `last_seen` timestamp and increment a `heartbeat_count` counter for the given server.

#### Scenario: Receive heartbeat for known server
- **WHEN** a POST request is sent to `/heartbeat` with a `server_id` that exists in memory
- **THEN** the server SHALL update `last_seen` to the current UTC timestamp
- **AND** increment `heartbeat_count` by 1
- **AND** return HTTP 200 with `status: "ok"`

#### Scenario: Receive heartbeat for unknown server
- **WHEN** a POST request is sent to `/heartbeat` with a `server_id` that does not exist in memory
- **THEN** the server SHALL create a minimal entry with the `server_id`, `last_seen` timestamp, and `heartbeat_count` of 1
- **AND** return HTTP 200 with `status: "ok"`

### Requirement: Server List Endpoint
The receiver SHALL expose `GET /servers` that returns a JSON array of all connected servers with staleness indicators. A server SHALL be marked as `stale` if its `last_seen` timestamp is more than 2 minutes ago.

#### Scenario: List all servers
- **WHEN** a GET request is sent to `/servers`
- **THEN** the response SHALL be a JSON object with a `servers` array containing all stored server entries
- **AND** each entry SHALL include a `stale` boolean field indicating whether `last_seen` exceeds 2 minutes

#### Scenario: No servers registered
- **WHEN** a GET request is sent to `/servers` and no servers have registered
- **THEN** the response SHALL return `{"servers": [], "count": 0}`

### Requirement: Single Server Detail Endpoint
The receiver SHALL expose `GET /servers/<id>` that returns the full details of a single server by its `server_id`.

#### Scenario: Get existing server
- **WHEN** a GET request is sent to `/servers/mydb_myhost`
- **AND** a server with `server_id` `mydb_myhost` exists
- **THEN** the response SHALL return HTTP 200 with the full server entry JSON

#### Scenario: Get nonexistent server
- **WHEN** a GET request is sent to `/servers/unknown_server`
- **AND** no server with that `server_id` exists
- **THEN** the response SHALL return HTTP 404 with an error message

### Requirement: Server Delete Endpoint
The receiver SHALL expose `DELETE /servers/<id>` that removes a server from the in-memory storage.

#### Scenario: Delete existing server
- **WHEN** a DELETE request is sent to `/servers/mydb_myhost`
- **AND** a server with `server_id` `mydb_myhost` exists
- **THEN** the server entry SHALL be removed from memory
- **AND** the response SHALL return HTTP 200 with `status: "deleted"`

#### Scenario: Delete nonexistent server
- **WHEN** a DELETE request is sent to `/servers/unknown_server`
- **AND** no server with that `server_id` exists
- **THEN** the response SHALL return HTTP 404 with an error message

### Requirement: Health Check Endpoint
The receiver SHALL expose `GET /health` that returns the receiver's own health status including uptime and the count of tracked servers.

#### Scenario: Health check
- **WHEN** a GET request is sent to `/health`
- **THEN** the response SHALL return HTTP 200 with a JSON object containing `status: "healthy"`, `uptime_seconds` (float), and `server_count` (integer)

### Requirement: Thread-Safe Storage
The receiver SHALL use `threading.Lock` to protect all read and write operations on the in-memory server storage dict, ensuring thread safety under concurrent requests.

#### Scenario: Concurrent registration
- **WHEN** multiple POST requests to `/register` arrive simultaneously
- **THEN** all registrations SHALL be stored correctly without data corruption or race conditions

### Requirement: Ngrok Tunnel Support
The receiver SHALL accept a `--ngrok` command-line flag. When set, the server SHALL create an ngrok tunnel to the listening port using `pyngrok` and print the public tunnel URL to stdout. The tunnel SHALL be cleaned up on server shutdown.

#### Scenario: Start with ngrok tunnel
- **WHEN** the receiver is started with `python receiver/server.py --ngrok`
- **THEN** the server SHALL create an ngrok tunnel to the listening port
- **AND** print the public ngrok URL (e.g., `https://abc123.ngrok.io`) to stdout
- **AND** the ngrok URL SHALL be usable as the `receiver_url` for the `register_receiver` MCP tool

#### Scenario: Start without ngrok
- **WHEN** the receiver is started without the `--ngrok` flag
- **THEN** no ngrok tunnel SHALL be created
- **AND** the server SHALL only be accessible on localhost

### Requirement: Command-Line Interface
The receiver SHALL accept the following command-line arguments via `argparse`: `--port` (integer, default 5000), `--ngrok` (boolean flag), `--debug` (boolean flag for Flask debug mode).

#### Scenario: Custom port and debug mode
- **WHEN** the receiver is started with `python receiver/server.py --port 9000 --debug`
- **THEN** the Flask server SHALL listen on port 9000 with debug mode enabled
