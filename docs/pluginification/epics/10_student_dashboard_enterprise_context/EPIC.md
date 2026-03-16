# Epic: Student Dashboard Enterprise Context

JIRA: ENT-11569

## Purpose

`common/djangoapps/student/views/dashboard.py` imports three functions from `enterprise_support` to enrich the student dashboard context with enterprise consent notifications, portal links, and learner status; a fourth import exists in `management.py` for enterprise learner detection.

## Approach

The `DashboardRenderStarted` filter is already defined in openedx-filters and is already invoked in `dashboard.py`. Add a new edx-enterprise `DashboardRenderStarted` pipeline step that injects all enterprise-specific context keys (`enterprise_message`, `consent_required_courses`, `is_enterprise_user`, enterprise portal context). Remove the direct enterprise_support imports and their call sites from both `dashboard.py` and `management.py`.

## Blocking Epics

None.
