# Installing the odoo-dev Skill for Claude Code

This guide explains how to install the `odoo-dev` skill so that Claude Code can help you develop, debug, and manage Odoo modules through the MCP server.

## Prerequisites

1. **Claude Code** installed and working (`claude` CLI available)
2. **odoo_dev_mcp module** deployed on your Odoo 19 instance
3. **Odoo API key** generated for Bearer token authentication
4. **Context7 MCP server** configured (for Odoo documentation lookups)

### Generating an Odoo API Key

1. Log in to your Odoo instance as an administrator
2. Go to Settings > Users & Companies > Users
3. Select your admin user
4. Go to the "Account Security" tab (or Preferences > Account Security)
5. Click "New API Key"
6. Give it a description (e.g., "MCP Server Access")
7. Copy the generated key -- you will not see it again

## Installation

### Option A: User-wide Installation (Recommended)

This makes the skill available in all your Claude Code projects.

```bash
# Create the skills directory if it does not exist
mkdir -p ~/.claude/skills/odoo-dev-mcp

# Copy the skill file (adjust the source path to wherever you cloned the module)
cp /path/to/odoo_dev_mcp/skills/odoo-dev-mcp/SKILL.md ~/.claude/skills/odoo-dev-mcp/SKILL.md
```

Or use a symlink to stay in sync with updates:

```bash
mkdir -p ~/.claude/skills/odoo-dev-mcp
ln -sf /path/to/odoo_dev_mcp/skills/odoo-dev-mcp/SKILL.md ~/.claude/skills/odoo-dev-mcp/SKILL.md
```

### Option B: Project-specific Installation

This makes the skill available only within a specific project.

```bash
# From your project root
mkdir -p .claude/skills/odoo-dev-mcp
cp /path/to/odoo_dev_mcp/skills/odoo-dev-mcp/SKILL.md .claude/skills/odoo-dev-mcp/SKILL.md
```

## MCP Server Configuration

You need to configure the Odoo MCP server connection in your `.mcp.json` file. This file can live in your project root (project-specific) or at `~/.mcp.json` (user-wide).

### Odoo MCP Server

Create or edit `.mcp.json`:

```json
{
  "mcpServers": {
    "odoo-dev-mcp": {
      "type": "http",
      "url": "http://YOUR_ODOO_HOST:8069/mcp/v1",
      "headers": {
        "Authorization": "Bearer YOUR_ODOO_API_KEY"
      }
    }
  }
}
```

Replace:
- `YOUR_ODOO_HOST` with your Odoo server hostname or IP
- `YOUR_ODOO_API_KEY` with the API key you generated above

### Context7 MCP Server (Required for Documentation Lookups)

The skill instructs Claude to look up Odoo documentation via Context7 before making changes. Add the Context7 server to your `.mcp.json`:

```json
{
  "mcpServers": {
    "odoo-dev-mcp": {
      "type": "http",
      "url": "http://YOUR_ODOO_HOST:8069/mcp/v1",
      "headers": {
        "Authorization": "Bearer YOUR_ODOO_API_KEY"
      }
    },
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

This requires Node.js/npm to be installed. The `npx` command will download and run the Context7 MCP server on first use.

## Verifying the Installation

### 1. Check the Skill is Discovered

Start Claude Code and type `/odoo-dev`. If the skill is installed correctly, it will be listed as an available skill.

### 2. Check MCP Server Connectivity

In Claude Code, ask:

```
Check the health of my Odoo MCP server
```

Claude should use the `odoo-dev-mcp` tools to verify connectivity.

### 3. Run a Smoke Test

Ask Claude:

```
List the installed modules on my Odoo instance
```

This exercises authentication and tool execution end-to-end.

## Invoking the Skill

The skill triggers automatically when you ask about Odoo development topics. You can also invoke it explicitly:

```
/odoo-dev
```

Example prompts that will trigger the skill:

- "Create a new Odoo module for managing equipment maintenance"
- "Debug why the sale order confirmation is failing"
- "Show me the database schema for the account_move table"
- "Upgrade the inventory module on the server"
- "Check the Odoo service status and recent logs"
- "Write an ORM method to compute invoice totals"

## Troubleshooting

### Skill not found

- Verify the file exists at the expected path:
  - User-wide: `~/.claude/skills/odoo-dev-mcp/SKILL.md`
  - Project: `.claude/skills/odoo-dev-mcp/SKILL.md`
- Ensure `settingSources` in your Claude Code config includes "user" (for user-wide) or "project" (for project-specific)
- Ensure "Skill" is in the `allowedTools` list

### MCP tools not available

- Verify `.mcp.json` is in the correct location and has valid JSON
- Test the health endpoint directly: `curl http://YOUR_ODOO_HOST:8069/mcp/v1/health`
- Check that the API key is valid and belongs to an admin user
- Ensure the `odoo_dev_mcp` module is installed and the Odoo service is running

### Context7 not working

- Verify Node.js is installed: `node --version`
- Test Context7 manually: `npx -y @upstash/context7-mcp`
- Check that the `context7` entry is in your `.mcp.json`

### Rate limit errors

The MCP server enforces rate limits per tool. If you hit a limit, wait 60 seconds for the window to reset. The most restrictive is `odoo_shell` at 5 calls per minute -- ask Claude to batch operations into fewer, larger shell calls.

## Updating the Skill

If you used a symlink (Option A with `ln -sf`), the skill updates automatically when you pull the latest `odoo_dev_mcp` module. Otherwise, re-copy the SKILL.md file after updates.
