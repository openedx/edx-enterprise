# [openedx-platform] Delete enterprise_support module from openedx-platform

Blocked by: [edx-enterprise] Copy enterprise_support into enterprise/platform_support/

Delete the entire `openedx/features/enterprise_support/` directory from openedx-platform. Remove `'openedx.features.enterprise_support.apps.EnterpriseSupportConfig'` from `INSTALLED_APPS` in `lms/envs/common.py`. After this change openedx-platform has no dependency on edx-enterprise or the consent package at import time.

## A/C

- `openedx/features/enterprise_support/` directory is deleted entirely from openedx-platform.
- `'openedx.features.enterprise_support.apps.EnterpriseSupportConfig'` is removed from `INSTALLED_APPS` in `lms/envs/common.py`.
- No remaining `from openedx.features.enterprise_support` import exists anywhere in openedx-platform outside the now-deleted directory.
- Test suite passes without the enterprise_support module installed.
