# [edx-enterprise] Add DashboardRenderStarted pipeline step

Blocked by: [openedx-platform] Remove enterprise dashboard context imports

Add a `DashboardContextEnricher` pipeline step for the existing `DashboardRenderStarted` filter in `enterprise/filters/dashboard.py`. The step calls `get_dashboard_consent_notification(request, user, course_enrollments)`, `get_enterprise_learner_portal_context(request)`, and `is_enterprise_learner(user)` (deferred imports from `openedx.features.enterprise_support` until epic 17) to populate the dashboard context with `enterprise_message`, `consent_required_courses`, `is_enterprise_user`, and enterprise portal keys. The step will be registered in `OPEN_EDX_FILTERS_CONFIG` via `enterprise/settings/common.py` as part of epic 18.

## A/C

- `DashboardContextEnricher(PipelineStep)` is defined in `enterprise/filters/dashboard.py` and injects all enterprise dashboard context keys.
- Unit tests cover the pipeline step with enterprise and non-enterprise users.
