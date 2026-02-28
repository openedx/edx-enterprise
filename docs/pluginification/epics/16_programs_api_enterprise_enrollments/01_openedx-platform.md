# [openedx-platform] Add pluggable override to _get_enterprise_course_enrollments

No tickets block this one.

Remove `get_enterprise_course_enrollments` and `enterprise_is_enabled` imports from `openedx/core/djangoapps/programs/rest_api/v1/views.py`. Remove the `@enterprise_is_enabled` decorator from `_get_enterprise_course_enrollments`. Replace the method body with a return of `EmptyQuerySet` by default and add the `@pluggable_override('OVERRIDE_PROGRAMS_GET_ENTERPRISE_COURSE_ENROLLMENTS')` decorator.

## A/C

- `from openedx.features.enterprise_support.api import get_enterprise_course_enrollments, enterprise_is_enabled` is removed from `programs/rest_api/v1/views.py`.
- The `@enterprise_is_enabled(otherwise=EmptyQuerySet)` decorator is removed from `_get_enterprise_course_enrollments`.
- `_get_enterprise_course_enrollments` is decorated with `@pluggable_override('OVERRIDE_PROGRAMS_GET_ENTERPRISE_COURSE_ENROLLMENTS')` and its body returns `EmptyQuerySet()`.
- No import of `enterprise` or `enterprise_support` remains in the changed file.
