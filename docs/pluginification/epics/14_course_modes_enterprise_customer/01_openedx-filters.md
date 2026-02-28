# [openedx-filters] Add CourseModeCheckoutStarted filter

No tickets block this one.

Add a `CourseModeCheckoutStarted` filter class to `openedx_filters/learning/filters.py`. This filter is triggered when a user begins the course mode checkout flow (e.g. choosing a paid mode) and allows pipeline steps to enrich the checkout context dict with additional data such as an enterprise customer UUID for enterprise pricing.

## A/C

- `CourseModeCheckoutStarted` is defined in `openedx_filters/learning/filters.py` with filter type `"org.openedx.learning.course_mode.checkout.started.v1"`.
- `run_filter(context, request, course_mode)` returns the (possibly enriched) context dict.
- Neither the filter class name, filter type string, nor docstring mentions "enterprise".
