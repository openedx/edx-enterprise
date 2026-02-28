# [openedx-platform] Replace enterprise logistration imports with filter calls

Blocked by: [openedx-filters] Add LogistrationContextRequested and PostLoginRedirectURLRequested filters

Remove all `enterprise_support` imports from `login_form.py`, `registration_form.py`, and `login.py` in `openedx/core/djangoapps/user_authn/views/`. Replace the enterprise customer context enrichment and cookie logic in `login_form.py` with a call to the new `LogistrationContextRequested` filter. Replace the enterprise SSO guard in `registration_form.py` (the `enterprise_customer_for_request` check that gates the SSO registration form skip) with a `StudentRegistrationRequested` pipeline step (the filter is already invoked in that view). Replace `enterprise_selection_page` in `login.py` with a call to the new `PostLoginRedirectURLRequested` filter and remove the `activate_learner_enterprise` and `get_enterprise_learner_data_from_api` imports.

## A/C

- All `from openedx.features.enterprise_support...` imports are removed from `login_form.py`, `registration_form.py`, and `login.py`.
- `login_form.py` calls `LogistrationContextRequested.run_filter(context, request)` and uses the returned context for rendering; `update_logistration_context_for_enterprise` and `handle_enterprise_cookies_for_logistration` calls are removed.
- `login_form.py` no longer directly calls `enterprise_customer_for_request`, `get_enterprise_slug_login_url`, or `enterprise_enabled`.
- `login.py` replaces `enterprise_selection_page(request, user, url)` with `PostLoginRedirectURLRequested.run_filter(redirect_url='', user=user, next_url=url)`.
- The `enterprise_selection_page` function and `activate_learner_enterprise` / `get_enterprise_learner_data_from_api` imports are removed from `login.py`.
- `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py` includes entries for `"org.openedx.learning.logistration.context.requested.v1"` and `"org.openedx.learning.auth.post_login.redirect_url.requested.v1"`.
- No import of `enterprise` or `enterprise_support` remains in any changed file.
