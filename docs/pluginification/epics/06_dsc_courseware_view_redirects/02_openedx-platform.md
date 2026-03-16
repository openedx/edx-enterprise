# [openedx-platform] Replace DSC decorator and enterprise imports in courseware

Blocked by: [openedx-filters] Add CoursewareViewRedirectURL filter

Replace all usages of `data_sharing_consent_required` from `enterprise_support.api` and `get_enterprise_consent_url` across courseware views and middleware, and remove direct enterprise model imports from `access_utils.py`. Create a new `courseware_view_redirect` decorator in `lms/djangoapps/courseware/decorators.py` that calls `CoursewareViewRedirectURL` and redirects to `redirect_urls[0]` if the list is non-empty. Apply the new decorator to `CoursewareIndex`, `CourseTabView`, `jump_to_id`, and `WikiView`. Replace the `get_enterprise_consent_url` call in `course_wiki/middleware.py` with a filter invocation. Replace enterprise model usage in `access_utils.py` with filter calls (moving the DB queries into edx-enterprise pipeline steps). Add the new filter to `OPEN_EDX_FILTERS_CONFIG`.

## A/C

- `lms/djangoapps/courseware/decorators.py` defines `courseware_view_redirect` that calls `CoursewareViewRedirectURL.run_filter(redirect_urls=[], request=request, course_key=course_key)` and returns `redirect(redirect_urls[0])` when the list is non-empty.
- All `from openedx.features.enterprise_support.api import data_sharing_consent_required` imports in `views/index.py`, `views/views.py`, `course_wiki/views.py` are removed.
- All `@data_sharing_consent_required` decorators are replaced with `@courseware_view_redirect`.
- `from openedx.features.enterprise_support.api import get_enterprise_consent_url` is removed from `course_wiki/middleware.py`; replaced with a filter call.
- `from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser` is removed from `courseware/access_utils.py`.
- `enterprise_learner_enrolled` and `check_data_sharing_consent` in `access_utils.py` are replaced with filter-based equivalents that call `CoursewareViewRedirectURL`.
- `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py` includes an entry for `"org.openedx.learning.courseware.view.redirect_url.requested.v1"` with `fail_silently=True` and `pipeline=[]`.
- Tests in `courseware/tests/test_access.py` and `courseware/tests/test_views.py` mock `CoursewareViewRedirectURL.run_filter` instead of enterprise functions.
- No import of `enterprise_support` or `enterprise` remains in any changed file.
