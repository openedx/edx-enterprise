# [openedx-platform] Use GradeEventContextRequested filter in grades events

Blocked by: [openedx-platform] Introduce OPEN_EDX_FILTERS_CONFIG and production merge logic (epic 00), [openedx-filters] Add GradeEventContextRequested filter

Replace the direct import of `get_enterprise_event_context` from `openedx.features.enterprise_support.context` in `lms/djangoapps/grades/events.py` with a call to the new `GradeEventContextRequested` openedx-filter. Add the filter to `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py` with an empty pipeline and `fail_silently=True`. Update tests in `grades/tests/test_events.py` to mock the filter rather than the enterprise function.

## A/C

- `from openedx.features.enterprise_support.context import get_enterprise_event_context` is removed from `lms/djangoapps/grades/events.py`.
- `course_grade_passed_first_time` calls `GradeEventContextRequested.run_filter(context=context, user_id=user_id, course_id=course_id)` and updates the local `context` dict with the returned value.
- `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py` gains an entry for `"org.openedx.learning.grade.context.requested.v1"` with `fail_silently=True` and `pipeline=[]`.
- Existing tests in `grades/tests/test_events.py` are updated to patch `GradeEventContextRequested.run_filter` instead of `get_enterprise_event_context`.
- No import of `enterprise_support` or `enterprise` remains in `grades/events.py`.
