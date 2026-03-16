# Epic: Enrollment API Enterprise Support

JIRA: ENT-11570

## Purpose

`openedx/core/djangoapps/enrollments/views.py` imports `EnterpriseApiServiceClient`, `ConsentApiServiceClient`, and `enterprise_enabled` from `enterprise_support` and calls them after enrollment when an `explicit_linked_enterprise` parameter is provided.

## Approach

Add a new edx-enterprise pipeline step for the existing `CourseEnrollmentStarted` filter (already defined in openedx-filters and invoked in the platform). The step detects when an `enterprise_uuid` is present in the enrollment context, posts the enrollment to the enterprise API, and records consent. Remove the enterprise_support imports and conditional block from `enrollments/views.py`.

## Blocking Epics

None.
