# [openedx-platform] Introduce OPEN_EDX_FILTERS_CONFIG and production merge logic

Blocked by: None

Introduce the `OPEN_EDX_FILTERS_CONFIG` setting in `lms/envs/common.py` (initially empty) and add merge logic in `lms/envs/production.py` so that YAML-supplied filter pipeline steps are appended after those configured in code rather than wholesale overwriting the setting. This is a prerequisite for all subsequent filter epics that add entries to `OPEN_EDX_FILTERS_CONFIG`.

## A/C

- `OPEN_EDX_FILTERS_CONFIG = {}` (with a setting description comment) is defined in `lms/envs/common.py`.
- `'OPEN_EDX_FILTERS_CONFIG'` is added to the exclusion list in `lms/envs/production.py` so YAML does not wholesale override it.
- Merge logic in `lms/envs/production.py` appends YAML-supplied pipeline steps after those defined in code and honours `fail_silently` from YAML, following the pattern used by `TRACKING_BACKENDS`.
- New filter types supplied only via YAML (not present in common.py) are still added to `OPEN_EDX_FILTERS_CONFIG` via the `else` branch of the merge logic.
