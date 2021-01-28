# -*- coding: utf-8 -*-
"""
Tests for the ``RouterView`` view of the Enterprise app.
"""

import ddt
import mock
from pytest import mark

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from enterprise import views
from test_utils import factories, fake_catalog_api, fake_enrollment_api


@mark.django_db
@ddt.ddt
class TestRouterView(TestCase):
    """
    ``enterprise.views.RouterView`` tests.
    """

    TEST_VIEWS = {
        views.RouterView.COURSE_ENROLLMENT_VIEW_URL: mock.MagicMock(
            as_view=mock.MagicMock(return_value=lambda request, *args, **kwargs: 'course_enrollment_view')
        ),
        views.RouterView.PROGRAM_ENROLLMENT_VIEW_URL: mock.MagicMock(
            as_view=mock.MagicMock(return_value=lambda request, *args, **kwargs: 'program_enrollment_view')
        ),
        views.RouterView.HANDLE_CONSENT_ENROLLMENT_VIEW_URL: mock.MagicMock(
            as_view=mock.MagicMock(return_value=lambda request, *args, **kwargs: 'handle_consent_enrollment_view')
        ),
    }

    def setUp(self):
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.course_run_id = 'course-v1:edX+DemoX+Demo_Course'
        self.request = mock.MagicMock(
            path=reverse(
                'enterprise_course_run_enrollment_page',
                args=[self.enterprise_customer.uuid, self.course_run_id]
            ),
            user=factories.UserFactory(),
            GET={},
        )
        self.kwargs = {
            'enterprise_uuid': str(self.enterprise_customer.uuid),
            'course_id': self.course_run_id,
        }
        views_mock = mock.patch('enterprise.views.RouterView.VIEWS')
        self.views_mock = views_mock.start()
        self.views_mock.__getitem__.side_effect = self.TEST_VIEWS.__getitem__
        self.addCleanup(views_mock.stop)
        analytics = mock.patch('enterprise.utils.segment')
        self.analytics = analytics.start()
        self.addCleanup(analytics.stop)

    @ddt.data(
        (
            {'enterprise_uuid': 'fake-uuid', 'course_id': 'fake-course-id'},
            ('fake-uuid', 'fake-course-id', '', ''),
        ),
        (
            {'enterprise_uuid': 'fake-uuid', 'program_uuid': 'fake-program-uuid'},
            ('fake-uuid', '', '', 'fake-program-uuid'),
        ),
        (
            {'enterprise_uuid': 'fake-uuid', 'course_id': 'fake-course-id', 'program_uuid': 'fake-program-uuid'},
            ('fake-uuid', 'fake-course-id', '', 'fake-program-uuid'),
        ),
        (
            {'enterprise_uuid': 'fake-uuid', 'course_id': '', 'program_uuid': 'fake-program-uuid'},
            ('fake-uuid', '', '', 'fake-program-uuid'),
        ),
        (
            {'enterprise_uuid': '', 'course_id': '', 'program_uuid': 'fake-program-uuid'},
            ('', '', '', 'fake-program-uuid'),
        ),
        (
            {'enterprise_uuid': 'fake-uuid', 'course_key': 'fake-course-key'},
            ('fake-uuid', '', 'fake-course-key', ''),
        ),
    )
    @ddt.unpack
    def test_get_path_variables(self, kwargs, expected_return):
        """
        ``get_path_variables`` returns the customer UUID as well as the course ID.
        """
        assert views.RouterView.get_path_variables(**kwargs) == expected_return

    @ddt.data(
        (False, True, True, True, False),
        (True, False, True, True, False),
        (True, True, False, True, False),
        (True, True, True, False, False),
        (True, True, True, True, True),
    )
    @ddt.unpack
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_eligible_for_direct_audit_enrollment(
            self,
            request_has_audit_query_param,
            is_course_enrollment_url,
            customer_catalog_contains_course,
            has_course_mode,
            expected_eligibility,
            enrollment_api_client_mock,
    ):  # pylint: disable=invalid-name
        """
        ``eligible_for_direct_audit_enrollment`` returns whether the request is eligible for direct audit enrollment.
        """
        self.request.GET['audit'] = request_has_audit_query_param
        self.request.path = self.request.path if is_course_enrollment_url else None
        self.enterprise_customer.catalog_contains_course = mock.MagicMock(return_value=customer_catalog_contains_course)
        enrollment_api_client_mock.return_value.has_course_mode.return_value = has_course_mode
        assert views.RouterView().eligible_for_direct_audit_enrollment(
            self.request,
            self.enterprise_customer,
            self.course_run_id
        ) == expected_eligibility

    def test_redirect_to_course_enrollment_view(self):
        """
        ``redirect`` properly redirects to ``enterprise.views.CourseEnrollmentView``.
        """
        assert views.RouterView().redirect(self.request, **self.kwargs) == 'course_enrollment_view'

    def test_redirect_to_program_enrollment_view(self):
        """
        ``redirect`` properly redirects to ``enterprise.views.ProgramEnrollmentView``.
        """
        self.request = mock.MagicMock(path=reverse(
            'enterprise_program_enrollment_page',
            args=[self.enterprise_customer.uuid, '52ad909b-c57d-4ff1-bab3-999813a2479b']
        ))
        self.kwargs = {
            'enterprise_uuid': str(self.enterprise_customer.uuid),
            'program_uuid': '52ad909b-c57d-4ff1-bab3-999813a2479b'
        }
        assert views.RouterView().redirect(self.request, **self.kwargs) == 'program_enrollment_view'

    def test_redirect_to_handle_consent_enrollment_view(self):
        """
        ``redirect`` properly redirects to ``enterprise.views.HandleConsentEnrollmentView``.
        """
        self.request = mock.MagicMock(path=reverse(
            'enterprise_handle_consent_enrollment',
            args=[self.enterprise_customer.uuid, self.course_run_id]
        ))
        assert views.RouterView().redirect(self.request, **self.kwargs) == 'handle_consent_enrollment_view'

    @mock.patch('enterprise.views.RouterView', new_callable=views.RouterView)
    def test_get_redirects_by_default(self, router_view_mock):
        """
        ``get`` performs a redirect by default.
        """
        router_view_mock.eligible_for_direct_audit_enrollment = mock.MagicMock(return_value=False)
        router_view_mock.redirect = mock.MagicMock(return_value=None)
        router_view_mock.get(self.request, **self.kwargs)
        router_view_mock.redirect.assert_called_once()

    @ddt.data(
        True, False
    )
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.RouterView', new_callable=views.RouterView)
    def test_get_redirects_with_course_key(
            self,
            is_user_already_enrolled,
            router_view_mock,
            enrollment_api_mock,
            catalog_api_mock
    ):
        """
        ``get`` performs a redirect with a course key in the request path.
        """
        if is_user_already_enrolled:
            enrollment_api_mock.get_enrolled_courses.return_value = None
        else:
            enrollment_api_mock.get_enrolled_courses.side_effect = fake_enrollment_api.get_enrolled_courses
        fake_catalog_api.setup_course_catalog_api_client_mock(catalog_api_mock)
        router_view_mock.eligible_for_direct_audit_enrollment = mock.MagicMock(return_value=False)
        router_view_mock.redirect = mock.MagicMock(return_value=None)
        kwargs = {
            'enterprise_uuid': str(self.enterprise_customer.uuid),
            'course_key': 'fake_course_key'
        }
        router_view_mock.get(self.request, **kwargs)
        router_view_mock.redirect.assert_called_once()

    @mock.patch('enterprise.views.get_global_context')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_raises_404_with_bad_catalog_client(self, catalog_api_mock, mock_global_context):
        """
        ``get`` responds with a 404 when the catalog client is not properly configured.
        """
        mock_global_context.return_value = {}
        catalog_api_mock.return_value.get_course_details.side_effect = ImproperlyConfigured()
        kwargs = {
            'enterprise_uuid': str(self.enterprise_customer.uuid),
            'course_key': 'fake_course_key'
        }
        with mock.patch('enterprise.views.render') as mock_render:
            mock_render.return_value = HttpResponse()  # Must return response to keep view happy
            views.RouterView().get(self.request, **kwargs)
            assert mock_render.call_args_list[0][1]['status'] == 404

    @mock.patch('enterprise.views.get_global_context')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_raises_404_with_bad_course_key(self, catalog_api_mock, enrollment_api_mock, mock_global_context):
        """
        ``get`` responds with a 404 when a course run cannot be found given the provided course key.
        """
        mock_global_context.return_value = {}
        fake_catalog_api.setup_course_catalog_api_client_mock(
            catalog_api_mock,
            course_overrides={'course_runs': []}
        )
        enrollment_api_mock.get_enrolled_courses.return_value = None
        kwargs = {
            'enterprise_uuid': str(self.enterprise_customer.uuid),
            'course_key': 'fake_course_key'
        }
        with mock.patch('enterprise.views.render') as mock_render:
            mock_render.return_value = HttpResponse()  # Must return response to keep view happy
            views.RouterView().get(self.request, **kwargs)
            assert mock_render.call_args_list[0][1]['status'] == 404

    @mock.patch('enterprise.views.track_enrollment')
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('enterprise.views.RouterView', new_callable=views.RouterView)
    def test_get_direct_audit_enrollment(self, router_view_mock, enrollment_api_client_mock, track_enrollment_mock):
        """
        ``get`` redirects to the LMS courseware when the request is fully eligible for direct audit enrollment.
        """
        enrollment_api_client_mock.return_value.get_course_enrollment.return_value = None
        router_view_mock.eligible_for_direct_audit_enrollment = mock.MagicMock(return_value=True)
        response = router_view_mock.get(self.request, **self.kwargs)
        enrollment_api_client_mock.return_value.enroll_user_in_course.assert_called_once()
        track_enrollment_mock.assert_called_once_with(
            'direct-audit-enrollment',
            self.request.user.id,
            self.course_run_id,
            self.request.get_full_path(),
        )
        self.assertRedirects(
            response,
            'http://lms.example.com/courses/{}/courseware'.format(self.course_run_id),
            fetch_redirect_response=False,
        )

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('enterprise.views.RouterView', new_callable=views.RouterView)
    def test_get_direct_audit_enrollment_user_already_enrolled(self, router_view_mock, enrollment_api_client_mock):
        """
        ``get`` redirects to the LMS courseware when the request is fully eligible for direct audit enrollment.
        """
        enrollment_api_client_mock.return_value.get_course_enrollment.return_value = {
            'is_active': True,
            'mode': 'verified,'
        }
        router_view_mock.eligible_for_direct_audit_enrollment = mock.MagicMock(return_value=True)
        response = router_view_mock.get(self.request, **self.kwargs)
        enrollment_api_client_mock.return_value.enroll_user_in_course.assert_not_called()
        self.assertRedirects(
            response,
            'http://lms.example.com/courses/{}/courseware'.format(self.course_run_id),
            fetch_redirect_response=False,
        )

    @mock.patch('enterprise.views.RouterView', new_callable=views.RouterView)
    def test_post_redirects_by_default(self, router_view_mock):
        """
        ``post`` simply performs a redirect by default.
        """
        router_view_mock.redirect = mock.MagicMock(return_value=None)
        router_view_mock.post(self.request, **self.kwargs)
        router_view_mock.redirect.assert_called_once()
