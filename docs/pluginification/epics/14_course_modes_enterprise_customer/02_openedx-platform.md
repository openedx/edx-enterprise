# [openedx-platform] Replace enterprise customer checkout import with filter call

Blocked by: [openedx-filters] Add CourseModeCheckoutStarted filter

Remove `enterprise_customer_for_request` (and any other enterprise_support imports used only for the enterprise checkout block) from `common/djangoapps/course_modes/views.py`. Replace the enterprise customer lookup and conditional block (lines ~191-197) with a call to `CourseModeCheckoutStarted.run_filter(context={}, request=request, course_mode=verified_mode)`. Add the new filter type to `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py`.

## A/C

- `from openedx.features.enterprise_support.api import enterprise_customer_for_request` is removed from `course_modes/views.py`.
- The checkout view calls `CourseModeCheckoutStarted.run_filter(...)` and uses the returned context dict for the ecommerce API call.
- `"org.openedx.learning.course_mode.checkout.started.v1"` is added to `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py`.
- No import of `enterprise` or `enterprise_support` remains in the changed file.
