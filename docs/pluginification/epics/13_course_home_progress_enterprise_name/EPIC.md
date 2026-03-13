# Epic: Course Home Progress Enterprise Name

JIRA: ENT-11572

## Purpose

`lms/djangoapps/course_home_api/progress/views.py` imports `get_enterprise_learner_generic_name` from `enterprise_support` to replace the student username with a generic enterprise name when the learner is an enterprise SSO user.

## Approach

Introduce an `obfuscated_username(request, student)` function in the same file and decorate it with `@pluggable_override('OVERRIDE_COURSE_HOME_PROGRESS_USERNAME')`. The default implementation returns `None`, preserving existing behavior. Replace the direct `get_enterprise_learner_generic_name` call with `obfuscated_username(request, student) or student.username`. edx-enterprise provides the override that calls `get_enterprise_learner_generic_name`.

## Blocking Epics

None.
