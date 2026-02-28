# [openedx-platform] Remove enterprise retirement methods from user API views

No tickets block this one.

Remove the direct imports of `consent.models.DataSharingConsent` and `enterprise.models.EnterpriseCourseEnrollment`, `EnterpriseCustomerUser`, `PendingEnterpriseCustomerUser` from `openedx/core/djangoapps/user_api/accounts/views.py`. Delete the `retire_users_data_sharing_consent` and `retire_user_from_pending_enterprise_customer_user` static methods from `DeactivateLogoutView`, and remove the calls to those methods in the retirement pipeline. Enhance the `USER_RETIRE_LMS_CRITICAL.send(...)` call to include `retired_username=retired_username` and `retired_email=retired_email` kwargs so that the edx-enterprise signal handler has the data it needs. Remove the `("consent.DataSharingConsent", "username")` and `("consent.HistoricalDataSharingConsent", "username")` entries from `MODELS_WITH_USERNAME` in `UsernameReplacementView`.

## A/C

- `from consent.models import DataSharingConsent` is removed from `views.py`.
- `from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser, PendingEnterpriseCustomerUser` is removed from `views.py`.
- `retire_users_data_sharing_consent` and `retire_user_from_pending_enterprise_customer_user` static methods are deleted from `DeactivateLogoutView`.
- The two calls to those methods (lines ~1158 and ~1161) are removed from the retirement pipeline in `DeactivateLogoutView.post`.
- The `USER_RETIRE_LMS_CRITICAL.send(...)` call passes `retired_username=retired_username` and `retired_email=retired_email` in addition to `user=user`.
- `("consent.DataSharingConsent", "username")` and `("consent.HistoricalDataSharingConsent", "username")` are removed from `MODELS_WITH_USERNAME` in `UsernameReplacementView`.
- Tests in `accounts/tests/test_retirement_views.py` are updated to not mock enterprise model imports and instead assert that `USER_RETIRE_LMS_CRITICAL.send` is called with the `retired_username` and `retired_email` kwargs.
- No import of `enterprise` or `consent` packages remains in `views.py`.
