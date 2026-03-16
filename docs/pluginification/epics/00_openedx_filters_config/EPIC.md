
# Epic: OPEN_EDX_FILTERS_CONFIG Production Settings Setup

JIRA: (TBD — incorporate into epic 01)

## Purpose

`lms/envs/production.py` wholesale-overrides any setting key found in YAML, which would wipe out the `OPEN_EDX_FILTERS_CONFIG` dict defined in `lms/envs/common.py` if operators supply any YAML value for that key. Without a merge strategy, any filter pipeline step configuration baked into code would be silently lost in production deployments.

## Approach

Introduce `OPEN_EDX_FILTERS_CONFIG = {}` in `lms/envs/common.py` and protect it from wholesale YAML override by adding it to the exclusion list in `lms/envs/production.py`. Add merge logic following the established `TRACKING_BACKENDS` / `CELERY_QUEUES` pattern: pipeline steps supplied via YAML are appended after those already defined in code, and the `fail_silently` value from YAML takes precedence over the one in code.

## Blocking Epics

None. This pseudo-epic has no dependencies and should be incorporated into whichever epic first adds a filter entry — in practice, epic 01_grades_analytics_event_enrichment.
