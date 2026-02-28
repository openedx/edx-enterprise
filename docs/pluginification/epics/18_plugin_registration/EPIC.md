# Epic: Plugin Registration

JIRA: ENT-11577

## Purpose

`lms/envs/common.py` imports enterprise role constants at module level and defines ~40 `ENTERPRISE_*` settings and enterprise middleware/role entries; `openedx/envs/common.py` lists `enterprise` and `consent` in `OPTIONAL_APPS`. The conditional enterprise URL include in `lms/urls.py` similarly requires edx-enterprise to be importable at startup. These make edx-enterprise a mandatory platform dependency regardless of the `ENABLE_ENTERPRISE_INTEGRATION` flag.

## Approach

Register all three Django apps in edx-enterprise (`enterprise`, `consent`, and `enterprise_support`) as proper openedx plugins by adding `plugin_app` configuration to each app's `AppConfig`. Following the naming convention established by `openedx-platform/openedx/core/djangoapps/password_policy/`, implement a `plugin_settings(settings)` callback in each app's `settings/common.py`. The `enterprise` app's `plugin_settings` populates all core `ENTERPRISE_*` settings, appends enterprise role classes to `SYSTEM_WIDE_ROLE_CLASSES`, adds `EnterpriseLanguagePreferenceMiddleware`, and registers all filter pipeline steps and pluggable overrides. The `consent` app's `plugin_settings` populates consent-specific settings (e.g. `ENTERPRISE_CONSENT_API_URL`). The `enterprise_support` app's `plugin_settings` populates settings consumed by enterprise_support utilities (e.g. `ENTERPRISE_READONLY_ACCOUNT_FIELDS`, `ENTERPRISE_CUSTOMER_COOKIE_NAME`). Remove all these entries from openedx-platform, including the `from enterprise.constants import ...` block, all `ENTERPRISE_*` settings, the `INSTALLED_APPS` entries, and the conditional URL include.

## Blocking Epics

Blocked by epic 17. All enterprise and enterprise_support imports must be removed from openedx-platform before the apps can be made optional.
