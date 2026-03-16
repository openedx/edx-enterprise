# Epic: Enterprise Username Change Command

JIRA: ENT-11565

## Purpose

`openedx-platform/common/djangoapps/student/management/commands/change_enterprise_user_username.py` is a management command that imports `enterprise.models.EnterpriseCustomerUser` directly and exists solely to change usernames for enterprise users affected by a specific bug (ENT-832). It has no non-enterprise use case.

## Approach

Move the management command file wholesale into edx-enterprise's own management commands directory (`enterprise/management/commands/`), where it can import enterprise models without creating a platform dependency. Remove the file and any associated tests from openedx-platform.

## Blocking Epics

None. This epic has no dependencies and can start immediately.
