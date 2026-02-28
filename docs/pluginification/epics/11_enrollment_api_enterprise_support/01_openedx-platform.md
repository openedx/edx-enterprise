# [openedx-platform] Remove enterprise enrollment API imports

No tickets block this one.

Remove `EnterpriseApiServiceClient`, `ConsentApiServiceClient`, and `enterprise_enabled` imports from `openedx/core/djangoapps/enrollments/views.py`. Remove the conditional block at lines ~777-796 that calls these clients when `explicit_linked_enterprise` is provided. Pass the `enterprise_uuid` field through the request data to the `CourseEnrollmentStarted` filter by ensuring it is available in the enrollment context (the filter is already invoked via the `CourseEnrollment.enroll` call chain). No direct filter call is needed in `views.py`; the enterprise-specific post-enrollment actions are handled by the edx-enterprise pipeline step.

## A/C

- All `from openedx.features.enterprise_support.api import ...` imports used only for the enterprise enrollment block are removed from `enrollments/views.py`.
- The `explicit_linked_enterprise` / `enterprise_enabled()` conditional block (lines ~777-796) is removed from the enrollment view.
- No import of `enterprise` or `enterprise_support` remains in the changed file.
