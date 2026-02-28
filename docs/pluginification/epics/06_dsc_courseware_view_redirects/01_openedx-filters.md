# [openedx-filters] Add CoursewareViewRedirectURL filter

No tickets block this one.

Add a new `CoursewareViewRedirectURL` filter class to `openedx_filters/learning/filters.py`. This filter is invoked before a courseware view is rendered to determine whether the user should be redirected away from the view. Pipeline steps may append redirect URLs to the `redirect_urls` list; the caller redirects to the first URL in the list. The filter accepts an initial (typically empty) list of redirect URLs, the Django request, and the course key. No exception class is needed since the caller simply checks the returned list.

## A/C

- A new `CoursewareViewRedirectURL` class is added to `openedx_filters/learning/filters.py`, inheriting from `OpenEdxPublicFilter`.
- The filter type is `"org.openedx.learning.courseware.view.redirect_url.requested.v1"`.
- `run_filter(cls, redirect_urls, request, course_key)` returns the modified `redirect_urls` list (and the unchanged `request` and `course_key`).
- No exception subclass is defined on this filter.
- A unit test confirms the filter returns the list unchanged when no pipeline steps modify it.
