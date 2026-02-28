# Epic: User Account Readonly Fields

JIRA: ENT-11510

## Purpose

`openedx-platform/openedx/core/djangoapps/user_api/accounts/api.py` imports `get_enterprise_readonly_account_fields` from `enterprise_support.utils` to prevent SSO-managed account fields from being edited by enterprise learners, creating a hard dependency on edx-enterprise inside the core user API.

## Approach

Introduce a new `AccountSettingsReadOnlyFieldsRequested` openedx-filter with signature `run_filter(editable_fields, user)` that returns a (possibly reduced) set of editable field names. Replace the direct call to `get_enterprise_readonly_account_fields` in `api.py` with a call to this filter. Implement a new `AccountSettingsReadOnlyFieldsStep` pipeline step in edx-enterprise that checks if the user is linked to an enterprise SSO identity provider with `sync_learner_profile_data` enabled, and if so removes the fields in `settings.ENTERPRISE_READONLY_ACCOUNT_FIELDS` from the editable set.

## Blocking Epics

None. This epic has no dependencies and can start immediately.
