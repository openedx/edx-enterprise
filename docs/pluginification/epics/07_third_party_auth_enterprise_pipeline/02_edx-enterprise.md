# [edx-enterprise] Add TPA pipeline steps and signal handler

Blocked by: [openedx-platform] Remove enterprise imports from third_party_auth

Create an enterprise SAML pipeline step `enterprise_associate_by_email` in `enterprise/tpa_pipeline.py` that replicates the `associate_by_email_if_enterprise_user` logic. Create a signal handler in `enterprise/platform_signal_handlers.py` that connects to the new `SocialAuthAccountDisconnected` signal and calls the enterprise user unlink logic. Wire up the signal handler in `EnterpriseConfig.ready()`. The SAML pipeline step will be registered in `SOCIAL_AUTH_PIPELINE` via `enterprise/settings/common.py` as part of epic 18.

## A/C

- `enterprise_associate_by_email` in `enterprise/tpa_pipeline.py` contains the associate-by-email logic using enterprise models, including the `is_enterprise_customer_user` check.
- A `handle_social_auth_disconnect` function is added to `enterprise/platform_signal_handlers.py` that calls the enterprise user unlink function.
- `handle_social_auth_disconnect` is connected to `SocialAuthAccountDisconnected` in `EnterpriseConfig.ready()`.
- Unit tests cover the pipeline step and signal handler.
