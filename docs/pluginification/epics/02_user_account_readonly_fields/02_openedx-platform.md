# [openedx-platform] Use AccountSettingsReadOnlyFieldsRequested filter in accounts API

Blocked by: [openedx-filters] Add AccountSettingsReadOnlyFieldsRequested filter

Replace the direct import of `get_enterprise_readonly_account_fields` from `openedx.features.enterprise_support.utils` in `openedx/core/djangoapps/user_api/accounts/api.py` with a call to the new `AccountSettingsReadOnlyFieldsRequested` filter. The filter is invoked inside `_validate_read_only_fields` to obtain the set of additional read-only fields contributed by any installed plugin. Add the filter to `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py` (extending the dict added in epic 01 if already present). Update test mocks in `accounts/tests/test_api.py` to patch the filter instead of patching the enterprise_support functions directly.

## A/C

- `from openedx.features.enterprise_support.utils import get_enterprise_readonly_account_fields` is removed from `openedx/core/djangoapps/user_api/accounts/api.py`.
- `_validate_read_only_fields` calls `AccountSettingsReadOnlyFieldsRequested.run_filter(editable_fields=set(), user=user)` and uses the returned set in place of the direct `get_enterprise_readonly_account_fields` call.
- `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py` contains an entry for `"org.openedx.learning.account.settings.read_only_fields.requested.v1"` with `fail_silently=True` and `pipeline=[]`.
- `lms/envs/production.py` merge logic (added in epic 01) handles this new filter type automatically (no additional production.py changes needed if epic 01 is merged first).
- Tests in `accounts/tests/test_api.py` are updated to patch `AccountSettingsReadOnlyFieldsRequested.run_filter` instead of the old enterprise_support imports.
- No import of `enterprise_support` or `enterprise` remains in `openedx/core/djangoapps/user_api/accounts/api.py`.
