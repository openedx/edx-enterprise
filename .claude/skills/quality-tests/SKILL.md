---
name: quality-tests
description: Run code quality checks (linting, style, PII annotations) in a Docker container. Use when the user wants to run quality checks, lint code, or verify code style compliance.
allowed-tools: Bash(docker *), Bash(make *), Bash(colima *)
---

## Steps

### 1. Make sure the test-shell container is running

Determine if the test-shell container is running:

```bash
docker compose ps
```

Start the test-shell container if not running:

```bash
make dev.up
```

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
