# [openedx-platform] Add pluggable override to get_enterprise_customer

No tickets block this one.

Remove `enterprise_customer_from_session_or_learner_data` and `get_enterprise_learner_data_from_db` imports from `lms/djangoapps/learner_home/views.py`. Replace the body of `get_enterprise_customer` with a simple `return None` default implementation and decorate it with `@pluggable_override('OVERRIDE_LEARNER_HOME_GET_ENTERPRISE_CUSTOMER')`.

## A/C

- All `from openedx.features.enterprise_support...` imports used only by `get_enterprise_customer` are removed from `learner_home/views.py`.
- `get_enterprise_customer` is decorated with `@pluggable_override('OVERRIDE_LEARNER_HOME_GET_ENTERPRISE_CUSTOMER')` and its body returns `None` by default.
- The `@function_trace("get_enterprise_customer")` decorator (if present) is retained.
- No import of `enterprise` or `enterprise_support` remains in the changed file.
