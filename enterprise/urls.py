"""
URLs for enterprise.
"""

from edx_api_doc_tools import make_api_info, make_docs_urls

from django.conf import settings
from django.urls import include, path, re_path

from enterprise.constants import COURSE_KEY_URL_PATTERN
from enterprise.heartbeat.views import heartbeat
from enterprise.views import (
    EnterpriseLoginView,
    EnterpriseProxyLoginView,
    EnterpriseSelectionView,
    GrantDataSharingPermissions,
    RouterView,
)

ENTERPRISE_ROUTER = RouterView.as_view()

enterprise_rest_api_urls = path(
    'enterprise/api/',
    include('enterprise.api.urls'),
    name='enterprise_api'
)

urlpatterns = [
    re_path(r'^enterprise/grant_data_sharing_permissions', GrantDataSharingPermissions.as_view(),
            name='grant_data_sharing_permissions'
            ),
    re_path(r'^enterprise/select/active', EnterpriseSelectionView.as_view(),
            name='enterprise_select_active'
            ),
    re_path(r'^enterprise/login', EnterpriseLoginView.as_view(),
            name='enterprise_slug_login'
            ),
    re_path(r'^enterprise/proxy-login', EnterpriseProxyLoginView.as_view(),
            name='enterprise_proxy_login'
            ),
    re_path(
        r'^enterprise/handle_consent_enrollment/(?P<enterprise_uuid>[^/]+)/course/{}/$'.format(
            settings.COURSE_ID_PATTERN
        ),
        ENTERPRISE_ROUTER,
        name='enterprise_handle_consent_enrollment'
    ),
    re_path(
        r'^enterprise/(?P<enterprise_uuid>[^/]+)/course/{}/enroll/$'.format(COURSE_KEY_URL_PATTERN),
        ENTERPRISE_ROUTER,
        name='enterprise_course_enrollment_page'
    ),
    re_path(
        r'^enterprise/(?P<enterprise_uuid>[^/]+)/course/{}/enroll/$'.format(settings.COURSE_ID_PATTERN),
        ENTERPRISE_ROUTER,
        name='enterprise_course_run_enrollment_page'
    ),
    path(
        'enterprise/<uuid:enterprise_uuid>/program/<uuid:program_uuid>/enroll/',
        ENTERPRISE_ROUTER,
        name='enterprise_program_enrollment_page'
    ),
    re_path(
        r'^enterprise/heartbeat/', heartbeat,
        name='enterprise_heartbeat',
    ),
    enterprise_rest_api_urls,
]

# Because ROOT_URLCONF points here, we are including the urls from the other apps here for now.
urlpatterns += [
    path(
        '',
        include('consent.urls'),
        name='consent'
    ),
    path(
        'cornerstone/',
        include('integrated_channels.cornerstone.urls'),
        name='cornerstone'
    ),
    path(
        'canvas/',
        include('integrated_channels.canvas.urls'),
        name='canvas',
    ),
    path(
        'blackboard/',
        include('integrated_channels.blackboard.urls'),
        name='blackboard',
    ),
    path(
        'enterprise_learner_portal/',
        include('enterprise_learner_portal.urls'),
        name='enterprise_learner_portal_api'
    ),
    path(
        'integrated_channels/api/',
        include('integrated_channels.api.urls')
    ),
]

api_docs_urlpatterns = make_docs_urls(
    make_api_info(
        title='Enterprise API',
        version='v1',
        description='Docs for the edx-enterprise `/enterprise/api/v1` REST API.',
    ),
    api_url_patterns=[enterprise_rest_api_urls],
)

urlpatterns.append(
    path('enterprise/', include(api_docs_urlpatterns)),
)
