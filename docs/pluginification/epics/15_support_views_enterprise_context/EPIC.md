# Epic: Support Views Enterprise Context

JIRA: ENT-11574

## Purpose

Two support views in `lms/djangoapps/support/views/` import from `enterprise_support`: `contact_us.py` tags support tickets with `'enterprise_learner'` when the user is an enterprise customer, and `enrollments.py` queries enterprise enrollments and consent records for the support enrollment view.

## Approach

Create two new openedx-filters: `SupportContactContextRequested` for enriching the support contact context with custom tags, and `SupportEnrollmentDataRequested` for populating the support enrollment view with enterprise enrollment data. edx-enterprise provides pipeline steps for both.

## Blocking Epics

None.
