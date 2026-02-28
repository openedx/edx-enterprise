# [edx-enterprise] Register enterprise, consent, and enterprise_support as openedx plugins

Blocked by: None

Add `plugin_app` configuration to `EnterpriseConfig` in `enterprise/apps.py`, `ConsentConfig` in `consent/apps.py`, and a new `EnterpriseSupportConfig` in `enterprise_support/apps.py` to register each as a proper openedx plugin for the LMS. Following the naming convention from `openedx-platform/openedx/core/djangoapps/password_policy/`, implement `plugin_settings(settings)` in each app's `settings/common.py` file. The `enterprise` app's `plugin_settings` populates all core `ENTERPRISE_*` settings (using `settings.setdefault`), appends enterprise role classes to `SYSTEM_WIDE_ROLE_CLASSES`, appends `EnterpriseLanguagePreferenceMiddleware` to `MIDDLEWARE`, registers all filter pipeline steps in `OPEN_EDX_FILTERS_CONFIG`, and configures all pluggable override settings. The `consent` app's `plugin_settings` populates `ENTERPRISE_CONSENT_API_URL`. The `enterprise_support` app's `plugin_settings` populates `ENTERPRISE_READONLY_ACCOUNT_FIELDS` and `ENTERPRISE_CUSTOMER_COOKIE_NAME`.

## A/C

- `EnterpriseConfig.plugin_app` in `enterprise/apps.py` declares `ProjectType.LMS` settings config pointing to `enterprise.settings.common` and URL config for `enterprise.urls`.
- `ConsentConfig.plugin_app` in `consent/apps.py` declares `ProjectType.LMS` settings config pointing to `consent.settings.common` and URL config for `consent.urls`.
- `EnterpriseSupportConfig.plugin_app` in `enterprise_support/apps.py` declares `ProjectType.LMS` settings config pointing to `enterprise_support.settings.common`.
- `plugin_settings(settings)` in `enterprise/settings/common.py` uses `setdefault` to populate all core `ENTERPRISE_*` settings previously defined in `lms/envs/common.py` (excluding `ENTERPRISE_CONSENT_API_URL`, `ENTERPRISE_READONLY_ACCOUNT_FIELDS`, and `ENTERPRISE_CUSTOMER_COOKIE_NAME`).
- `plugin_settings` in `enterprise/settings/common.py` appends enterprise role classes to `SYSTEM_WIDE_ROLE_CLASSES` using edx-enterprise's own constants (no import of platform constants needed).
- `plugin_settings` in `enterprise/settings/common.py` appends `'enterprise.middleware.EnterpriseLanguagePreferenceMiddleware'` to `MIDDLEWARE`.
- `plugin_settings` in `enterprise/settings/common.py` derives `ENTERPRISE_API_URL` and `ENTERPRISE_PUBLIC_ENROLLMENT_API_URL` from `settings.LMS_ROOT_URL` when available.
- `plugin_settings` in `enterprise/settings/common.py` registers all filter pipeline steps in `OPEN_EDX_FILTERS_CONFIG` for all filter types used by epics 01–16 (grades, account readonly fields, discount eligibility, courseware redirects, logistration, dashboard, enrollment, course modes, support contact, support enrollment). If `OPEN_EDX_FILTERS_CONFIG` does not exist on `settings`, it is initialised to `{}`. If a filter type is not yet present in `OPEN_EDX_FILTERS_CONFIG`, it is created with `fail_silently=True` and an empty pipeline before the enterprise steps are appended.
- `plugin_settings` in `enterprise/settings/common.py` configures all pluggable override settings that were added by epics 1-16.
- `plugin_settings(settings)` in `consent/settings/common.py` uses `setdefault` to populate `ENTERPRISE_CONSENT_API_URL` derived from `settings.LMS_ROOT_URL`.
- `plugin_settings(settings)` in `enterprise_support/settings/common.py` uses `setdefault` to populate `ENTERPRISE_READONLY_ACCOUNT_FIELDS` and `ENTERPRISE_CUSTOMER_COOKIE_NAME`.
- Unit tests verify that each `plugin_settings` sets the expected settings as defaults and that filter pipeline steps are correctly registered even when `OPEN_EDX_FILTERS_CONFIG` is empty or absent.
