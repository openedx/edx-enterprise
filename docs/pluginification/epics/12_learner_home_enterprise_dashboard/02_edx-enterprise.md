# [edx-enterprise] Override get_enterprise_customer for learner home

Blocked by: [openedx-platform] Add pluggable override to get_enterprise_customer

Add an override function for `OVERRIDE_LEARNER_HOME_GET_ENTERPRISE_CUSTOMER` in edx-enterprise at `enterprise/overrides/learner_home.py`. The override calls `enterprise_customer_from_session_or_learner_data(request)` when not masquerading, and `get_enterprise_learner_data_from_db(user)` when masquerading (deferred imports from `openedx.features.enterprise_support.api` until epic 17). The override setting will be configured in `enterprise/settings/common.py` as part of epic 18.

## A/C

- `enterprise_get_enterprise_customer(prev_fn, user, request, is_masquerading)` is defined in `enterprise/overrides/learner_home.py` and delegates to the appropriate enterprise_support functions based on the `is_masquerading` flag.
- Unit tests cover the override for both masquerading and non-masquerading scenarios.
