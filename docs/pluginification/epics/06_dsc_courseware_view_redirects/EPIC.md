# Epic: DSC Courseware View Redirects

JIRA: ENT-11544

## Purpose

Multiple courseware views in openedx-platform are decorated with the enterprise-specific `data_sharing_consent_required` decorator imported from `enterprise_support.api`, and `WikiAccessMiddleware` calls `get_enterprise_consent_url` directly. Additionally, `courseware/access_utils.py` imports `enterprise.models` directly to check enterprise learner enrollment status. These create hard dependencies on edx-enterprise in core courseware and wiki code paths.

## Approach

Introduce a new `CoursewareViewRedirectURL` openedx-filter with signature `run_filter(redirect_urls, request, course_key)` that returns a list of redirect URLs. Create a new `courseware_view_redirect` decorator in the platform that calls this filter and redirects to the first URL in the list (or passes if the list is empty). Replace all usages of `@data_sharing_consent_required` with `@courseware_view_redirect`, replace the `get_enterprise_consent_url` call in `WikiAccessMiddleware` with the filter call, and replace the direct enterprise model imports in `access_utils.py` with filter calls. Implement two pipeline steps in edx-enterprise: one for DSC consent redirects and one for enterprise learner portal redirects.

## Blocking Epics

None. This is the largest epic but has no blocking dependencies.
