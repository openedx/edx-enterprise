# [openedx-filters] Add GradeEventContextRequested filter

No tickets block this one.

Add a new `GradeEventContextRequested` filter class to `openedx_filters/learning/filters.py`. This filter is invoked when a grade-related analytics event is about to be emitted, and allows pipeline steps to enrich the event tracking context dict with additional fields. The filter accepts the current context dict, the user ID, and the course ID, and returns the (possibly enriched) context dict. No exception class is required because the filter is configured to fail silently.

## A/C

- A new `GradeEventContextRequested` class is added to `openedx_filters/learning/filters.py`, inheriting from `OpenEdxPublicFilter`.
- The filter type is `"org.openedx.learning.grade.context.requested.v1"`.
- `run_filter(cls, context, user_id, course_id)` accepts a `dict` context, an `int` user_id, and a `str`/`CourseKey` course_id, and returns the enriched context dict.
- No exception subclass is defined on this filter.
- A unit test is added (or updated) in the openedx-filters test suite confirming the filter runs the pipeline and returns the context.
