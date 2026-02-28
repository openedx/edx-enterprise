# [openedx-platform] Remove enterprise dashboard context imports

No tickets block this one.

Remove the `get_dashboard_consent_notification`, `get_enterprise_learner_portal_context`, and `is_enterprise_learner` imports and their call sites from `common/djangoapps/student/views/dashboard.py`. Move the enterprise context injection to the existing `DashboardRenderStarted` filter pipeline (the filter is already invoked in the view). Also remove the `is_enterprise_learner` import and usage from `common/djangoapps/student/views/management.py`.

## A/C

- All `from openedx.features.enterprise_support...` imports are removed from `dashboard.py` and `management.py`.
- In `dashboard.py`, the three enterprise context assignments (`enterprise_message`, `is_enterprise_user`, enterprise learner portal context) are removed from the context dict before the `DashboardRenderStarted.run_filter()` call; the filter pipeline step in edx-enterprise will inject them instead.
- In `management.py`, the `is_enterprise_learner(user)` check at line ~685 and `'is_enterprise_learner'` context key at line ~212 are removed.
- No import of `enterprise` or `enterprise_support` remains in any changed file.
