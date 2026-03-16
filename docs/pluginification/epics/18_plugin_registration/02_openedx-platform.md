# [openedx-platform] Remove enterprise app registration and settings from platform

Blocked by: [edx-enterprise] Register enterprise, consent, and enterprise_support as openedx plugins

Remove all enterprise hard-coding from openedx-platform: the `from enterprise.constants import ...` block (lines 48–61), all `ENTERPRISE_*` settings (lines ~2586–3017), enterprise entries in `SYSTEM_WIDE_ROLE_CLASSES`, the `EnterpriseLanguagePreferenceMiddleware` entry from `MIDDLEWARE`, and the conditional `enterprise.urls` include from `lms/urls.py`. Also remove the `('enterprise', None)` and `('consent', None)` entries from `OPTIONAL_APPS` in `openedx/envs/common.py`. Reset `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py` to an empty dict — all filter pipeline step registrations are now managed by the enterprise plugin's `plugin_settings`. The plugin framework injects all of these at startup when edx-enterprise is installed.

## A/C

- `from enterprise.constants import ...` block (all 13 role constant imports) is removed from `lms/envs/common.py`.
- All `ENTERPRISE_*` settings are removed from `lms/envs/common.py`.
- Enterprise entries are removed from `SYSTEM_WIDE_ROLE_CLASSES` in `lms/envs/common.py`.
- `'enterprise.middleware.EnterpriseLanguagePreferenceMiddleware'` is removed from `MIDDLEWARE` in `lms/envs/common.py`.
- `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py` is reset to `{}` — all enterprise filter step registrations move to `enterprise/settings/common.py` `plugin_settings`.
- `('enterprise', None)` and `('consent', None)` are removed from `OPTIONAL_APPS` in `openedx/envs/common.py`.
- The conditional `enterprise.urls` include is removed from `lms/urls.py`.
- openedx-platform starts without edx-enterprise installed (enterprise features disabled).
- openedx-platform starts with edx-enterprise installed (all enterprise settings injected via `plugin_settings` across all three plugins, including filter pipeline step registrations).
