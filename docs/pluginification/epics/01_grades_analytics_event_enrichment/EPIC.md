# Epic: Grades Analytics Event Enrichment

JIRA: ENT-11563

## Purpose

`openedx-platform/lms/djangoapps/grades/events.py` enriches grade analytics events with enterprise metadata (the enterprise UUID) by directly importing and calling `get_enterprise_event_context` from the `enterprise_support` module, creating a hard import dependency on edx-enterprise at grade-event emission time.

## Approach

Introduce a new `GradeEventContextRequested` openedx-filter with signature `run_filter(context, user_id, course_id)`. Replace the direct `get_enterprise_event_context` import and call in `events.py` with a call to this filter. Implement a new `GradeEventContextEnricher` pipeline step in edx-enterprise that queries `EnterpriseCourseEnrollment.get_enterprise_uuids_with_user_and_course` to look up the enterprise UUID and merges it into the context dict.

## Blocking Epics

Blocked by epic 00_openedx_filters_config (for the production.py merge logic). Epic 00 has no dependencies of its own and can be shipped as part of this epic's PR.
