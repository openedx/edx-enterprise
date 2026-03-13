# [edx-enterprise] Add logistration context and post-login redirect pipeline steps

Blocked by: [openedx-platform] Replace enterprise logistration imports with filter calls

Implement two pipeline steps in edx-enterprise:

1. `LogistrationContextEnricher` — a `LogistrationContextRequested` pipeline step in `enterprise/filters/logistration.py` that calls `enterprise_customer_for_request(request)` to look up the enterprise customer, then delegates to `update_logistration_context_for_enterprise` and `handle_enterprise_cookies_for_logistration` (deferred imports from `openedx.features.enterprise_support.utils` until epic 17 ships).

2. `PostLoginEnterpriseRedirect` — a `PostLoginRedirectURLRequested` pipeline step in `enterprise/filters/logistration.py` that replicates the `enterprise_selection_page` logic: calls `get_enterprise_learner_data_from_api(user)`, and if the user is associated with multiple enterprises, returns the enterprise selection page URL.

## A/C

- `LogistrationContextEnricher(PipelineStep)` is defined and enriches the logistration context dict with enterprise customer sidebar context, slug login URL, and cookie-setting.
- `PostLoginEnterpriseRedirect(PipelineStep)` returns the enterprise selection page redirect URL when the user is linked to multiple enterprises.
- Unit tests cover both pipeline steps.
