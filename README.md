# CockroachDB Plugin for Codex

Use CockroachDB from Codex without leaving the chat.

This plugin connects Codex to the CockroachDB Cloud MCP endpoint, which means you can inspect clusters, browse databases and tables, run read-only queries, and explain SQL directly from Codex.

## Why this plugin exists

When you're already working inside Codex, it is a pain to keep jumping back and forth between the database console, SQL shell, and your editor just to answer simple questions:

- What databases are in this cluster?
- Which tables exist in this database?
- What does the schema for this table look like?
- What are the latest rows in this table?
- Why is this query slow?

This plugin keeps that workflow in one place.

## Highlights

- Connects Codex to CockroachDB Cloud through MCP
- Lets you inspect cluster metadata from inside Codex
- Browse databases, tables, and table schemas
- Run read-only SQL queries for quick analysis and debugging
- Explain queries without leaving the Codex session
- Works well for support, debugging, data checks, and demo environments

## What you can do

Depending on the MCP server capabilities available for your cluster, Codex can use tools like:

- `get_cluster`
- `list_databases`
- `list_tables`
- `get_table_schema`
- `select_query`
- `show_running_queries`
- `show_statement`
- `explain_query`

In the cluster this plugin was tested against, these tools were available and working.

## Example prompts

These are the kinds of prompts that work well in Codex once the plugin is installed:

```text
List all databases in my CockroachDB cluster
```

```text
Show tables in my database
```

```text
Get the schema for the users table in my database
```

```text
Run this query on my database: SELECT count(*) FROM public.users;
```

```text
Fetch the latest 10 rows from public.users
```

```text
Explain this query on my database: SELECT * FROM public.users WHERE created_at >= now() - interval '7 days';
```

## Sample queries

You can also paste direct SQL when using the query tools:

```sql
SELECT count(*) AS total_rows
FROM public.users;
```

```sql
SELECT *
FROM public.users
ORDER BY created_at DESC
LIMIT 10;
```

```sql
SELECT status, count(*) AS total
FROM public.users
GROUP BY status
ORDER BY total DESC;
```

## Installation

### 1. Put the plugin somewhere Codex can load

If you want to use it as a home-local plugin:

```bash
mkdir -p ~/plugins
ln -s /absolute/path/to/cockroachdb-plugin ~/plugins/cockroachdb
```

### 2. Add it to your local Codex marketplace

Create:

`~/.agents/plugins/marketplace.json`

with:

```json
{
  "name": "local-plugins",
  "interface": {
    "displayName": "Local Plugins"
  },
  "plugins": [
    {
      "name": "cockroachdb",
      "source": {
        "source": "local",
        "path": "./plugins/cockroachdb"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Developer Tools"
    }
  ]
}
```

### 3. Configure the MCP server

The plugin reads its MCP server definition from:

`./.mcp.json`

Example:

```json
{
  "mcpServers": {
    "cockroachdb-cloud": {
      "type": "http",
      "url": "https://cockroachlabs.cloud/mcp",
      "headers": {
        "mcp-cluster-id": "your-cluster-id",
        "Authorization": "Bearer your-token"
      }
    }
  }
}
```

### 4. Restart Codex

After restarting Codex, search for:

`CockroachDB`

and install or enable the plugin from the local marketplace.

## Repository layout

```text
.codex-plugin/plugin.json   Plugin manifest
.mcp.json                   MCP server configuration
skills/cockroachdb/         Guidance Codex can use with the plugin
scripts/                    Earlier local MCP server work kept in the repo
```

## Notes for publishing

- Do not commit real bearer tokens to GitHub
- Do not commit cluster-specific secrets in `.mcp.json`
- Use placeholders in examples and keep the real config local
- If you already committed a live token, rotate it before publishing

## Current status

This plugin has been tested against a CockroachDB Cloud cluster and used successfully for:

- listing databases
- listing tables
- fetching table schema
- running `SELECT` queries
- fetching recent rows from application tables

## Author

Vittal Pai
