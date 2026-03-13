# [openedx-platform] Replace enterprise support view imports with filter calls

Blocked by: [openedx-filters] Add SupportContactContextRequested and SupportEnrollmentDataRequested filters

Remove all `enterprise_support` imports from `lms/djangoapps/support/views/contact_us.py` and `lms/djangoapps/support/views/enrollments.py`. In `contact_us.py`, replace the `enterprise_api.enterprise_customer_for_request(request)` check and tag appending with a call to `SupportContactContextRequested.run_filter(tags=tags, request=request, user=user)`. In `enrollments.py`, replace `_enterprise_course_enrollments_by_course_id(user)` with a call to `SupportEnrollmentDataRequested.run_filter(enrollment_data={}, user=user)` and delete the `_enterprise_course_enrollments_by_course_id` method. Add the new filter types to `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py`.

## A/C

- `from openedx.features.enterprise_support import api as enterprise_api` is removed from `contact_us.py`; enterprise customer tag logic is replaced by a filter call.
- `from openedx.features.enterprise_support.api import ...` and serializer imports are removed from `enrollments.py`; `_enterprise_course_enrollments_by_course_id` is deleted.
- Both new filter types are added to `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py`.
- No import of `enterprise` or `enterprise_support` remains in any changed file.
