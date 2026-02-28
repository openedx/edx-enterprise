# [edx-enterprise] Add AccountSettingsReadOnlyFieldsStep pipeline step

Blocked by: [openedx-filters] Add AccountSettingsReadOnlyFieldsRequested filter

Create a new file `enterprise/filters/accounts.py` containing the `AccountSettingsReadOnlyFieldsStep` pipeline step. This step implements the `AccountSettingsReadOnlyFieldsRequested` filter by checking whether the user is linked to an enterprise customer that has an SSO identity provider with `sync_learner_profile_data` enabled. If so, the step removes the field names listed in `settings.ENTERPRISE_READONLY_ACCOUNT_FIELDS` from the `editable_fields` set and returns the reduced set. The step uses `EnterpriseCustomerUser` and `EnterpriseCustomerIdentityProvider` models and the `third_party_auth` registry, mirroring the logic previously in `get_enterprise_readonly_account_fields` in enterprise_support.

## A/C

- `enterprise/filters/accounts.py` defines `AccountSettingsReadOnlyFieldsStep(PipelineStep)`.
- The step queries `EnterpriseCustomerUser` to find the user's enterprise customer link.
- If found, the step checks whether `sync_learner_profile_data` is enabled via `EnterpriseCustomerIdentityProvider` and `third_party_auth` registry.
- If the user has a social auth record and SSO sync is active, the step returns `{"editable_fields": editable_fields - set(settings.ENTERPRISE_READONLY_ACCOUNT_FIELDS)}`.
- If the user's fullname is not SSO-backed (no `UserSocialAuth` record), `"name"` is not removed from `editable_fields`.
- If no enterprise link or no SSO sync, returns `{"editable_fields": editable_fields}` unchanged.
- Unit tests are added in `tests/filters/test_accounts.py`.
- No import of `openedx.features.enterprise_support` in the pipeline step file.
