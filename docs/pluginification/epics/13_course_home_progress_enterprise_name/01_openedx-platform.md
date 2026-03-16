# [openedx-platform] Add pluggable override for obfuscated username in progress view

No tickets block this one.

Remove the `get_enterprise_learner_generic_name` import from `lms/djangoapps/course_home_api/progress/views.py`. Introduce a new `obfuscated_username(request, student)` function decorated with `@pluggable_override('OVERRIDE_COURSE_HOME_PROGRESS_USERNAME')` that returns `None` by default. Replace `username = get_enterprise_learner_generic_name(request) or student.username` with `username = obfuscated_username(request, student) or student.username`.

## A/C

- `from openedx.features.enterprise_support.utils import get_enterprise_learner_generic_name` is removed from `progress/views.py`.
- `obfuscated_username(request, student)` is defined in `progress/views.py` with the `@pluggable_override('OVERRIDE_COURSE_HOME_PROGRESS_USERNAME')` decorator and returns `None` by default.
- Line ~209 is updated to `username = obfuscated_username(request, student) or student.username`.
- No import of `enterprise` or `enterprise_support` remains in the changed file.
