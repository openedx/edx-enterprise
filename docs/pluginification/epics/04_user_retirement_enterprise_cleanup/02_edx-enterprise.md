# [edx-enterprise] Add USER_RETIRE_LMS_CRITICAL signal handler for enterprise retirement

Blocked by: [openedx-platform] Remove enterprise retirement methods from user API views

Create a new file `enterprise/platform_signal_handlers.py` containing the `handle_user_retirement` function, which connects to the `USER_RETIRE_LMS_CRITICAL` signal from `openedx.core.djangoapps.user_api.accounts.signals`. The handler retires `DataSharingConsent` records by updating the `username` field to `retired_username`, and retires `PendingEnterpriseCustomerUser` records by updating `user_email` to `retired_email`. Wire the handler into `EnterpriseConfig.ready()` in `enterprise/apps.py`. No new signal definition is needed — this epic reuses the enhanced `USER_RETIRE_LMS_CRITICAL` signal.

## A/C

- `enterprise/platform_signal_handlers.py` defines `handle_user_retirement(sender, user, retired_username, retired_email, **kwargs)`.
- The handler calls `DataSharingConsent.objects.filter(username=user.username).update(username=retired_username)`.
- The handler calls `PendingEnterpriseCustomerUser.objects.filter(user_email=user.email).update(user_email=retired_email)`.
- The handler is connected to `USER_RETIRE_LMS_CRITICAL` in `EnterpriseConfig.ready()`.
- Unit tests in `tests/test_platform_signal_handlers.py` cover the retirement operations using mocked model querysets.
- The handler uses `**kwargs` to forward-compatibly ignore unknown signal kwargs.
