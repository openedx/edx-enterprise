# Epic: User Retirement Enterprise Cleanup

JIRA: ENT-11473

## Purpose

`openedx-platform/openedx/core/djangoapps/user_api/accounts/views.py` directly imports and calls `DataSharingConsent`, `EnterpriseCourseEnrollment`, `EnterpriseCustomerUser`, and `PendingEnterpriseCustomerUser` from the `consent` and `enterprise` packages to retire enterprise-specific user data, creating hard dependencies on edx-enterprise inside the core user retirement API.

## Approach

Enhance the existing `USER_RETIRE_LMS_CRITICAL` Django signal to carry `retired_username` and `retired_email` kwargs in addition to `user`. Remove the two enterprise retirement methods (`retire_users_data_sharing_consent` and `retire_user_from_pending_enterprise_customer_user`) and their direct enterprise model imports from `views.py`. Implement a new signal handler in edx-enterprise that connects to `USER_RETIRE_LMS_CRITICAL` and performs both retirement operations. Also remove the `consent.DataSharingConsent` and `consent.HistoricalDataSharingConsent` entries from the `MODELS_WITH_USERNAME` list in `views.py`, moving that responsibility into edx-enterprise's own retirement configuration.

## Blocking Epics

None. This epic has no dependencies and can start immediately.
