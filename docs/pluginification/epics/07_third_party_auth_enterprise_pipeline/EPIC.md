# Epic: Third-Party Auth Enterprise Pipeline

JIRA: ENT-11566

## Purpose

`openedx-platform/common/djangoapps/third_party_auth/` imports enterprise and enterprise_support functions in three ways: `settings.py` calls `insert_enterprise_pipeline_elements` to inject enterprise pipeline stages into `SOCIAL_AUTH_PIPELINE`, `pipeline.py` defines `associate_by_email_if_enterprise_user` with a lazy import of `enterprise_is_enabled`, and `saml.py` overrides `SAMLAuth.disconnect` with a lazy import of `unlink_enterprise_user_from_idp`. Additionally `utils.py` directly imports enterprise models.

## Approach

Three sub-parts replace these three behaviors:

1. **Pipeline injection**: Add enterprise SAML pipeline stages to `SOCIAL_AUTH_PIPELINE` via edx-enterprise's `enterprise/settings/common.py` `plugin_settings()` callback (registered in epic 18), eliminating `insert_enterprise_pipeline_elements` and the `third_party_auth/settings.py` import.

2. **Associate-by-email**: Move `associate_by_email_if_enterprise_user` into an edx-enterprise pipeline step (`enterprise.tpa_pipeline.enterprise_associate_by_email`) that will be registered via `SOCIAL_AUTH_PIPELINE` in `plugin_settings` as part of epic 18. Remove the function and its enterprise model imports from `pipeline.py` and `utils.py`.

3. **SAML disconnect**: Emit a new Django signal `SocialAuthAccountDisconnected` from `SAMLAuth.disconnect`; edx-enterprise connects a handler that calls `unlink_enterprise_user_from_idp`.

## Blocking Epics

None. This epic has no blocking dependencies.
