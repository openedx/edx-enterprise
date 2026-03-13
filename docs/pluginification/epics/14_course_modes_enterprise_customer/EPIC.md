# Epic: Course Modes Enterprise Customer

JIRA: ENT-11573

## Purpose

`common/djangoapps/course_modes/views.py` imports `enterprise_customer_for_request` from `enterprise_support` and uses it to enrich the checkout context with enterprise customer data for ecommerce pricing API calls.

## Approach

Create a new `CourseModeCheckoutStarted` openedx-filter that allows edx-enterprise to inject enterprise customer context into the course mode checkout flow. Replace the direct `enterprise_customer_for_request` call in the view with a filter invocation.

## Blocking Epics

None.
