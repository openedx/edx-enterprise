# Epic: Programs API Enterprise Enrollments

JIRA: ENT-11575

## Purpose

`openedx/core/djangoapps/programs/rest_api/v1/views.py` imports `get_enterprise_course_enrollments` and `enterprise_is_enabled` from `enterprise_support` and uses them in `_get_enterprise_course_enrollments` to filter course enrollments for enterprise learners on the programs progress page.

## Approach

Decorate `_get_enterprise_course_enrollments` with `@pluggable_override('OVERRIDE_PROGRAMS_GET_ENTERPRISE_COURSE_ENROLLMENTS')`. The default implementation returns an empty queryset. edx-enterprise provides the override that queries `EnterpriseCourseEnrollment` filtered by the enterprise UUID. The `enterprise_is_enabled` decorator is removed; when edx-enterprise is not installed the default empty queryset is used automatically.

## Blocking Epics

None.
