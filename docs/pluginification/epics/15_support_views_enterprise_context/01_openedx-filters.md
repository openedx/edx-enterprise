# [openedx-filters] Add SupportContactContextRequested and SupportEnrollmentDataRequested filters

No tickets block this one.

Add two new filter classes to `openedx_filters/learning/filters.py`:

1. `SupportContactContextRequested` — triggered when a user submits a support contact request; pipeline steps can append custom tags to the support ticket tags list.

2. `SupportEnrollmentDataRequested` — triggered when the support enrollment view loads data for a user; pipeline steps can inject additional enrollment records (e.g. enterprise course enrollments with consent data) into the enrollment data dict keyed by course ID.

## A/C

- `SupportContactContextRequested` is defined with filter type `"org.openedx.learning.support.contact.context.requested.v1"` and `run_filter(tags, request, user)` returning the (possibly modified) tags list.
- `SupportEnrollmentDataRequested` is defined with filter type `"org.openedx.learning.support.enrollment.data.requested.v1"` and `run_filter(enrollment_data, user)` returning the (possibly modified) enrollment dict.
- Neither filter class name, filter type string, nor docstring mentions "enterprise".
