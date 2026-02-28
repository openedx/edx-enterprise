# [edx-enterprise] Add change_enterprise_user_username management command

Blocked by: [openedx-platform] Remove change_enterprise_user_username management command

Copy the `change_enterprise_user_username` management command into `enterprise/management/commands/change_enterprise_user_username.py`. The logic is identical to the platform version but lives in edx-enterprise where enterprise model imports are natural. Add a unit test in `tests/management/test_change_enterprise_user_username.py`.

## A/C

- `enterprise/management/commands/change_enterprise_user_username.py` is created with the same `Command` class as the platform original.
- The command imports `EnterpriseCustomerUser` from `enterprise.models` (no platform import).
- `--user_id` and `--new_username` arguments function identically to the original.
- Unit tests confirm the command updates the username when the user is an enterprise user and logs an error when the user is not found in `EnterpriseCustomerUser`.
