# -*- coding: utf-8 -*-
"""
Tests for the ``RouterView`` view of the Enterprise app.
"""

from __future__ import absolute_import, unicode_literals

import ddt
import mock
from pytest import mark

from django.core.urlresolvers import reverse
from django.test import TestCase

from enterprise import views
from test_utils import factories


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
        super(TestRouterView, self).setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.course_run_id = 'course-v1:edX+DemoX+Demo_Course'
        self.request = mock.MagicMock(path=reverse(
            'enterprise_course_enrollment_page',
            args=[self.enterprise_customer.uuid, self.course_run_id]
        ))
        self.request.user.id = 1
        self.kwargs = {
            'enterprise_uuid': str(self.enterprise_customer.uuid),
            'course_id': self.course_run_id,
        }
        views_mock = mock.patch('enterprise.views.RouterView.VIEWS')
        self.views_mock = views_mock.start()
        self.views_mock.__getitem__.side_effect = self.TEST_VIEWS.__getitem__
        self.addCleanup(views_mock.stop)
        tracker_mock = mock.patch('enterprise.utils.tracker')
        self.tracker_mock = tracker_mock.start()
        self.tracker_mock.get_tracker.return_value.resolve_context.return_value = {}
        self.addCleanup(tracker_mock.stop)
        analytics = mock.patch('enterprise.utils.analytics')
        self.analytics = analytics.start()
        self.addCleanup(analytics.stop)

    @ddt.data(
        (
            {'enterprise_uuid': 'fake-uuid', 'course_id': 'fake-course-id'},
            ('fake-uuid', 'fake-course-id'),
        ),
        (
            {'enterprise_uuid': 'fake-uuid', 'program_uuid': 'fake-program-uuid'},
            ('fake-uuid', 'fake-program-uuid'),
        ),
        (
            {'enterprise_uuid': 'fake-uuid', 'course_id': 'fake-course-id', 'program_uuid': 'fake-program-uuid'},
            ('fake-uuid', 'fake-course-id'),
        ),
        (
            {'enterprise_uuid': 'fake-uuid', 'course_id': '', 'program_uuid': 'fake-program-uuid'},
            ('fake-uuid', 'fake-program-uuid'),
        ),
        (
            {'enterprise_uuid': '', 'course_id': '', 'program_uuid': 'fake-program-uuid'},
            ('', 'fake-program-uuid'),
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
        self.request.GET.get = mock.MagicMock(return_value=request_has_audit_query_param)
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

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('enterprise.views.RouterView', new_callable=views.RouterView)
    def test_get_direct_audit_enrollment(self, router_view_mock, enrollment_api_client_mock):
        """
        ``get`` redirects to the LMS courseware when the request is fully eligible for direct audit enrollment.
        """
        enrollment_api_client_mock.return_value.is_enrolled.return_value = False
        router_view_mock.eligible_for_direct_audit_enrollment = mock.MagicMock(return_value=True)
        response = router_view_mock.get(self.request, **self.kwargs)
        enrollment_api_client_mock.return_value.enroll_user_in_course.assert_called_once()
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
