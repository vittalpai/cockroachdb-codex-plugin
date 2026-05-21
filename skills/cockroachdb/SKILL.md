# CockroachDB

Use this plugin when the user wants to inspect or query a CockroachDB cluster from Codex.

## Workflow

1. Start with `connection_info` if the connection state is unclear.
2. Use `list_schemas` and `list_tables` to understand the shape of the database before writing queries.
3. Use `describe_table` before joining unfamiliar tables.
4. Use `run_readonly_query` for analysis queries.
5. Use `explain_query` when the user asks about query plans or performance.

## Safety

- This plugin is intentionally read-only.
- If the user asks for writes, schema changes, imports, restores, or admin operations, explain that this plugin blocks them by design.
- Prefer bounded queries and reasonable filters, even though the server already enforces a row limit.

## Configuration

- The server reads `COCKROACHDB_URL` first, then `DATABASE_URL`.
- The default schema comes from `COCKROACHDB_DEFAULT_SCHEMA`, falling back to `public`.
