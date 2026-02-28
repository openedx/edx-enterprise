# [edx-enterprise] Override _get_enterprise_course_enrollments for programs API

Blocked by: [openedx-platform] Add pluggable override to _get_enterprise_course_enrollments

Add an override function for `OVERRIDE_PROGRAMS_GET_ENTERPRISE_COURSE_ENROLLMENTS` in edx-enterprise at `enterprise/overrides/programs.py`. The override queries `EnterpriseCourseEnrollment` from `enterprise.models` directly (no enterprise_support import needed) filtered by `enterprise_customer__uuid=enterprise_uuid`, then calls `get_course_enrollments(user, True, list(enterprise_enrollment_course_ids))` (deferred import from `common.djangoapps.student.api`). The override setting will be configured in `enterprise/settings/common.py` as part of epic 18.

## A/C

- `enterprise_get_enterprise_course_enrollments(prev_fn, self, enterprise_uuid, user)` is defined in `enterprise/overrides/programs.py` and returns the filtered course enrollments queryset.
- Unit tests cover the override.
