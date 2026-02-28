# [openedx-platform] Remove enterprise imports from third_party_auth

No tickets block this one.

Remove all enterprise and enterprise_support imports from `common/djangoapps/third_party_auth/settings.py`, `pipeline.py`, `saml.py`, and `utils.py`. Specifically: remove the `insert_enterprise_pipeline_elements` call from `apply_settings()` in `settings.py`; remove `associate_by_email_if_enterprise_user` and the `enterprise_is_enabled` decorator from `pipeline.py`; remove the `is_enterprise_customer_user` function and enterprise model imports from `utils.py`; replace the lazy `unlink_enterprise_user_from_idp` call in `SAMLAuth.disconnect` with a new `SocialAuthAccountDisconnected` Django signal. Define that signal in a new `common/djangoapps/third_party_auth/signals.py` module.

## A/C

- `from openedx.features.enterprise_support.api import insert_enterprise_pipeline_elements` and its call are removed from `third_party_auth/settings.py`.
- `associate_by_email_if_enterprise_user` and the `enterprise_is_enabled` decorator usage are removed from `third_party_auth/pipeline.py`.
- `from enterprise.models import EnterpriseCustomerIdentityProvider, EnterpriseCustomerUser` and `is_enterprise_customer_user` are removed from `third_party_auth/utils.py`.
- `from openedx.features.enterprise_support.api import unlink_enterprise_user_from_idp` and its call are removed from `third_party_auth/saml.py`.
- A new `SocialAuthAccountDisconnected` Django signal is defined in `common/djangoapps/third_party_auth/signals.py`.
- `SAMLAuth.disconnect` in `saml.py` emits `SocialAuthAccountDisconnected.send(...)` with the relevant user and provider info.
- No import of `enterprise` or `enterprise_support` remains in any changed file.
- Tests are updated to mock the new signal instead of enterprise functions.
