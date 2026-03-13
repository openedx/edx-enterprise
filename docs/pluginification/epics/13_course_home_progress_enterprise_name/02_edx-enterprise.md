# [edx-enterprise] Override obfuscated_username for course home progress view

Blocked by: [openedx-platform] Add pluggable override for obfuscated username in progress view

Add an override function for `OVERRIDE_COURSE_HOME_PROGRESS_USERNAME` in edx-enterprise at `enterprise/overrides/course_home_progress.py`. The override calls `get_enterprise_learner_generic_name(request)` (deferred import from `openedx.features.enterprise_support.utils` until epic 17) and returns the generic name if found, otherwise `None`. The override setting will be configured in `enterprise/settings/common.py` as part of epic 18.

## A/C

- `enterprise_obfuscated_username(prev_fn, request, student)` is defined in `enterprise/overrides/course_home_progress.py` and returns the enterprise generic name when available, or `None`.
- Unit tests cover the override for enterprise and non-enterprise learners.
