# [openedx-platform] Remove change_enterprise_user_username management command

No tickets block this one.

Delete `common/djangoapps/student/management/commands/change_enterprise_user_username.py` from openedx-platform entirely, along with any test coverage for it in the student management test suite. The command is being moved to edx-enterprise where enterprise model imports are appropriate.

## A/C

- `common/djangoapps/student/management/commands/change_enterprise_user_username.py` is deleted from the repository.
- Any test cases in `common/djangoapps/student/tests/test_management.py` (or similar) that specifically test `change_enterprise_user_username` are removed.
- No import of `enterprise.models` remains in `common/djangoapps/student/management/`.
