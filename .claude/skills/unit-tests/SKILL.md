---
name: unit-tests
description: Run Django unit tests in the edx-enterprise Docker container. Use when the user wants to run tests, check if tests pass, or verify test coverage.
argument-hint: "<TEST_FILES>"
allowed-tools: Bash(docker *), Bash(make *), Bash(colima *)
---

## Arguments

`<TEST_FILES>` (optional): One or more folders, test file paths, or pytest node IDs to run. Coverage is only enabled when a single folder representing a code domain is provided or no arguments are provided.

Examples:
- `/unit-tests` — run all tests with coverage
- `/unit-tests tests/test_enterprise/test_tasks.py` — run one test file without coverage
- `/unit-tests tests/test_enterprise/test_tasks.py tests/test_consent/test_helpers.py` — run multiple test files without coverage
- `/unit-tests tests/test_enterprise/test_tasks.py::TestSomeClass::test_method` — run a single test by node ID without coverage

## Routing rules (evaluate in order)

- **No arguments** → Step 2b (whole-project tests + whole-project coverage)
- **Everything else** → Step 2a (targeted tests, NO coverage)

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

### 2a. Run specific unit test files or functions

If `<TEST_FILES>` is provided, run only those tests using `pytest.local.ini` to disable coverage and warnings:

```bash
docker compose exec test-shell bash -c "pytest -c pytest.local.ini <TEST_FILES>"
```

Never enable coverage reports (by adding `--cov`) when only testing specific files, since the results will be misleading.

### 2b. Run whole-project unit tests and generate coverage

If no arguments are given, assume the user wants to run the full test suite for the entire project:

```bash
docker compose exec test-shell make test
```

Whole-project coverage will be reported in the console output. Specific line numbers with missing coverage will be reported.

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
