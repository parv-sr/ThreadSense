# ThreadSense

## Database probe parity checks

Use this Alembic preflight command to print the migration-connection database probe without applying migrations:

```bash
alembic -c backend/alembic.ini -x preflight=true upgrade head
```

The command prints:
- masked `database_url`
- `current_database()`
- `current_schema()`
- `inet_server_addr()`
- `inet_server_port()`

At runtime, the API startup logs print the same fields so you can compare migration-path vs app runtime-path targets.
