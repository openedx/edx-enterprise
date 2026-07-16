---
name: quality-tests
description: Run code quality checks (linting, style, PII annotations) in a Docker container. Use when the user wants to run quality checks, lint code, or verify code style compliance.
allowed-tools: Bash(docker *), Bash(make *), Bash(colima *)
---

## Steps

### 1. Make sure the test-shell container is running

Always run this first — it is idempotent, and it also generates the `.env`
file which gives each clone of this repo its own docker compose project name
(so multiple clones don't fight over the same container):

```bash
make dev.up
```

IMPORTANT: always interact with the container via `docker compose` (which
reads `.env`), never via bare `docker` commands with a hardcoded container
name — the container name is different in every clone.

### 2. Run quality checks

```bash
docker compose exec test-shell make quality
```

## Troubleshooting

### ModuleNotFoundError

If tests fail due to missing imports, first try to install requirements:

```bash
docker compose exec test-shell make requirements
```

This is necessary at least when adding new requirements which have not yet been built into the image.

### Failed to connect to the docker API on MacOS

This likely just means colima needs to be started:

```bash
colima start
```
