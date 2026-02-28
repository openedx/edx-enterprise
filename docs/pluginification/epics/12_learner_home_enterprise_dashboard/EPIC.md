# Epic: Learner Home Enterprise Dashboard

JIRA: ENT-11571

## Purpose

`lms/djangoapps/learner_home/views.py` imports `enterprise_customer_from_session_or_learner_data` and `get_enterprise_learner_data_from_db` from `enterprise_support` and uses them inside `get_enterprise_customer()` to populate the `enterpriseDashboard` key in the learner home API response.

## Approach

Decorate the existing `get_enterprise_customer` function in `learner_home/views.py` with `@pluggable_override('OVERRIDE_LEARNER_HOME_GET_ENTERPRISE_CUSTOMER')`. The default implementation returns `None`. edx-enterprise provides the override implementation that calls the enterprise_support functions. Since only one enterprise plugin is installed at a time, a pluggable override is simpler and more appropriate than a filter pipeline.

## Blocking Epics

None.
