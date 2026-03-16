# [openedx-filters] Add LogistrationContextRequested and PostLoginRedirectURLRequested filters

No tickets block this one.

Add two new filter classes to `openedx_filters/learning/filters.py`. The first, `LogistrationContextRequested`, is triggered just before the combined login-and-registration page is rendered; pipeline steps can modify the context dict and response object (e.g. to inject enterprise customer data, set cookies, or update sidebar context). The second, `PostLoginRedirectURLRequested`, is triggered after a user successfully logs in; pipeline steps can return an optional redirect URL to send the user to an enterprise selection page or similar destination before the normal post-login redirect.

## A/C

- `LogistrationContextRequested` is defined in `openedx_filters/learning/filters.py` with filter type `"org.openedx.learning.logistration.context.requested.v1"` and `run_filter(context, request)` returning the modified context dict.
- `PostLoginRedirectURLRequested` is defined in `openedx_filters/learning/filters.py` with filter type `"org.openedx.learning.auth.post_login.redirect_url.requested.v1"` and `run_filter(redirect_url, user, next_url)` returning the (possibly modified) redirect URL.
- Neither filter class name, filter type string, nor docstring mentions "enterprise".
