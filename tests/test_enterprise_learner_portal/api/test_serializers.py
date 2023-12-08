"""
Tests for the EnterpriseCourseEnrollmentview of the enterprise_learner_portal app.
"""

from collections import OrderedDict
from unittest import mock
from unittest.mock import patch
from urllib.parse import urlencode

import ddt
from pytest import mark

from django.conf import settings
from django.http import HttpRequest
from django.test import RequestFactory, TestCase

from enterprise.utils import NotConnectedToOpenEdX
from enterprise_learner_portal.api.v1.serializers import EnterpriseCourseEnrollmentSerializer
from test_utils import factories


@mark.django_db
@ddt.ddt
class TestEnterpriseCourseEnrollmentSerializer(TestCase):
    """
    EnterpriseCourseEnrollmentSerializer tests.
    """

    def setUp(self):
        super().setUp()

        self.user = factories.UserFactory.create(is_staff=True, is_active=True)
        self.factory = RequestFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory.create(user_id=self.user.id)

    @ddt.data(
        ('example.com', False),
        (settings.EXEC_ED_LANDING_PAGE, True),
    )
    @ddt.unpack
    @patch.object(HttpRequest, 'get_host', return_value='courses.edx.org')
    @mock.patch('enterprise.models.CourseEnrollment')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_course_run_status')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_emails_enabled')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_course_run_url')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_certificate_for_user')
    def test_serializer_representation(
            self,
            course_run_url,
            is_exec_ed_course,
            mock_get_cert,
            mock_get_course_run_url,
            mock_get_emails_enabled,
            mock_get_course_run_status,
            mock_course_enrollment_class,
            _,
    ):
        """
        EnterpriseCourseEnrollmentSerializer should create proper representation
        based on the instance data it receives (an enterprise course enrollment)
        """
        course_run_id = 'some+id+here'
        course_overviews = [{
            'id': course_run_id,
            'start': 'a datetime object',
            'end': 'a datetime object',
            'display_name_with_default': 'a default name',
            'pacing': 'instructor',
            'display_org_with_default': 'my university',
        }]
        course_enrollments_resume_urls = {
            course_run_id: '/courses/course-v1:MITx+6.86x+2T2024'
        }

        mock_get_cert.return_value = {
            'download_url': 'example.com',
            'is_passing': True,
            'created': 'a datetime object',
        }
        expected_course_run_url = course_run_url
        if is_exec_ed_course:
            exec_ed_landing_page = getattr(settings, 'EXEC_ED_LANDING_PAGE', None)
            params = {'org_id': self.enterprise_customer_user.enterprise_customer.auth_org_id}
            expected_course_run_url = '{}?{}'.format(exec_ed_landing_page, urlencode(params))

        mock_get_course_run_url.return_value = course_run_url
        mock_get_emails_enabled.return_value = True
        mock_get_course_run_status.return_value = 'completed'

        enterprise_enrollment = factories.EnterpriseCourseEnrollmentFactory.create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=course_run_id
        )
        mock_course_enrollment_class.objects.get.return_value.is_active = True
        mock_course_enrollment_class.objects.get.return_value.mode = 'verified'

        request = HttpRequest()
        request.user = self.user

        serializer = EnterpriseCourseEnrollmentSerializer(
            [enterprise_enrollment],
            many=True,
            context={
                'request': request,
                'course_overviews': course_overviews,
                'course_enrollments_resume_urls': course_enrollments_resume_urls
            },
        )

        expected = OrderedDict([
            ('certificate_download_url', 'example.com'),
            ('emails_enabled', True),
            ('course_run_id', course_run_id),
            ('course_run_status', 'completed'),
            ('created', enterprise_enrollment.created.isoformat()),
            ('start_date', 'a datetime object'),
            ('end_date', 'a datetime object'),
            ('display_name', 'a default name'),
            ('course_run_url', expected_course_run_url),
            ('due_dates', []),
            ('pacing', 'instructor'),
            ('org_name', 'my university'),
            ('is_revoked', False),
            ('is_enrollment_active', True),
            ('mode', 'verified'),
            ('resume_course_run_url', 'http://courses.edx.org/courses/course-v1:MITx+6.86x+2T2024'),
        ])
        actual = serializer.data[0]
        self.assertDictEqual(actual, expected)

    def test_view_requires_openedx_installation(self):
        """
        View should raise error if imports to helper methods fail.
        """
        with self.assertRaises(NotConnectedToOpenEdX):
            EnterpriseCourseEnrollmentSerializer({})
