"""
Tests for the EnterpriseCourseEnrollmentview of the enterprise_learner_portal app.
"""

import uuid
from unittest import mock
from urllib.parse import urlencode

import ddt
from pytest import mark

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from enterprise.utils import NotConnectedToOpenEdX
from test_utils import factories

SERIALIZED_MOCK_ACTIVE_ENROLLMENT = {'course_id': 'foo', 'is_enrollment_active': True}
SERIALIZED_MOCK_INACTIVE_ENROLLMENT = {'course_id': 'bar', 'is_enrollment_active': False}


@mark.django_db
@ddt.ddt
class TestEnterpriseCourseEnrollmentView(TestCase):
    """
    EnterpriseCourseEnrollmentView tests.
    """

    class MockSerializer:
        """ Returns obj with data property. """

        @property
        def data(self):
            """ Return fake serialized data. """
            return [
                SERIALIZED_MOCK_ACTIVE_ENROLLMENT,
                SERIALIZED_MOCK_INACTIVE_ENROLLMENT,
            ]

    def setUp(self):
        super().setUp()

        self.enterprise_customer = factories.EnterpriseCustomerFactory.create()

        # Create our user we will enroll in a course
        self.user = factories.UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        enrolled_ent_customer_user = factories.EnterpriseCustomerUserFactory.create(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.course_run_id = 'course-v1:edX+DemoX+Demo_Course'
        self.enterprise_enrollment = factories.EnterpriseCourseEnrollmentFactory.create(
            enterprise_customer_user=enrolled_ent_customer_user,
            course_id=self.course_run_id,
        )

        # Create a user we will not enroll in a course
        not_enrolled_user = factories.UserFactory.create(
            email='not_enrolled@example.com',
        )
        factories.EnterpriseCustomerUserFactory.create(
            user_id=not_enrolled_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        self.client = Client()
        self.client.login(username=self.user.username, password="QWERTY")

    @mock.patch('enterprise_learner_portal.api.v1.views.get_resume_urls_for_course_enrollments')
    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_view_returns_information(self, mock_get_overviews, mock_serializer, mock_course_resume_urls):
        """
        View should return data created by EnterpriseCourseEnrollmentSerializer
        (which we mock in this case)
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()
        mock_course_resume_urls.return_value = {
            'course-v1:edX+DemoX+Demo_Course': '/courses/course-v1:MITx+6.86x+2T2024'
        }

        resp = self.client.get(
            '{host}{path}?enterprise_id={enterprise_id}'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list'),
                enterprise_id=str(self.enterprise_customer.uuid)
            )
        )
        assert resp.status_code == 200
        assert resp.json() == [
            SERIALIZED_MOCK_ACTIVE_ENROLLMENT,
            SERIALIZED_MOCK_INACTIVE_ENROLLMENT,
        ]

    @mock.patch('enterprise_learner_portal.api.v1.views.get_resume_urls_for_course_enrollments')
    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    @ddt.data('true', 'false')
    def test_view_get_filters_active_enrollments(
            self,
            active_filter_value,
            mock_get_overviews,
            mock_serializer,
            mock_course_resume_urls,
    ):
        """
        View should return data created by EnterpriseCourseEnrollmentSerializer
        (which we mock in this case)
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()
        mock_course_resume_urls.return_value = {
            'course-v1:edX+DemoX+Demo_Course': '/courses/course-v1:MITx+6.86x+2T2024'
        }

        resp = self.client.get(
            '{host}{path}?enterprise_id={enterprise_id}&is_active={active_filter_value}'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list'),
                enterprise_id=str(self.enterprise_customer.uuid),
                active_filter_value=active_filter_value
            )
        )
        assert resp.status_code == 200
        if active_filter_value == 'true':
            expected_result = [SERIALIZED_MOCK_ACTIVE_ENROLLMENT]
        else:
            expected_result = [SERIALIZED_MOCK_INACTIVE_ENROLLMENT]
        assert resp.json() == expected_result

    @mock.patch('enterprise_learner_portal.api.v1.views.get_resume_urls_for_course_enrollments')
    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_view_returns_bad_request_without_enterprise(
            self,
            mock_get_overviews,
            mock_serializer,
            mock_course_resume_urls
    ):
        """
        View should return a 400 because of the missing enterprise_id parameter.
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()
        mock_course_resume_urls.return_value = {
            'course-v1:edX+DemoX+Demo_Course': '/courses/course-v1:MITx+6.86x+2T2024'
        }

        resp = self.client.get(
            '{host}{path}'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list')
            )
        )
        assert resp.status_code == 400
        assert resp.json() == {'error': 'enterprise_id must be provided as a query parameter'}

    @mock.patch('enterprise_learner_portal.api.v1.views.get_resume_urls_for_course_enrollments')
    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_view_returns_not_found_unlinked_enterprise(
            self,
            mock_get_overviews,
            mock_serializer,
            mock_course_resume_urls
    ):
        """
        View should return a 404 because the user is not linked to the enterprise.
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()
        mock_course_resume_urls.return_value = {
            'course-v1:edX+DemoX+Demo_Course': '/courses/course-v1:MITx+6.86x+2T2024'
        }

        resp = self.client.get(
            '{host}{path}?enterprise_id={enterprise_id}'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list'),
                enterprise_id=str(uuid.uuid4()),
            )
        )
        assert resp.status_code == 404
        assert resp.json() == {'detail': 'Not found.'}

    @mock.patch('enterprise_learner_portal.api.v1.views.get_resume_urls_for_course_enrollments')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_certificate_for_user', mock.MagicMock())
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_view_filters_out_invalid_enterprise_enrollments(self, mock_get_overviews, mock_course_resume_urls):
        """
        View does not fail, and view filters out all enrollments whose course_enrollment
        field is None
        """
        mock_get_overviews.return_value = {}
        mock_course_resume_urls.return_value = {}

        resp = self.client.get(
            '{host}{path}?enterprise_id={enterprise_id}&is_active=true'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list'),
                enterprise_id=str(self.enterprise_customer.uuid),
            )
        )
        assert resp.status_code == 200
        # since all enterprise_enrollments in this are with empty course_enrollment
        # this check should fail if filtering is not working
        assert resp.json() == []

    def test_view_requires_openedx_installation(self):
        """
        View should raise error if imports to helper methods fail.
        """
        with self.assertRaises(NotConnectedToOpenEdX):
            self.client.get(
                '{host}{path}?enterprise_id={enterprise_id}'.format(
                    host=settings.TEST_SERVER,
                    path=reverse('enterprise-learner-portal-course-enrollment-list'),
                    enterprise_id=str(self.enterprise_customer.uuid)
                )
            )

        with self.assertRaises(NotConnectedToOpenEdX):
            query_params = {
                'enterprise_id': str(self.enterprise_customer.uuid),
                'course_id': self.course_run_id,
                'saved_for_later': True,
            }

            self.client.patch(
                '{host}{path}?{query_params}'.format(
                    host=settings.TEST_SERVER,
                    path=reverse('enterprise-learner-portal-course-enrollment-list'),
                    query_params=urlencode(query_params),
                )
            )

    @mock.patch('enterprise_learner_portal.api.v1.views.get_resume_urls_for_course_enrollments')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_course_run_status')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_emails_enabled')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_course_run_url')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_certificate_for_user')
    def test_patch_success(
        self,
        mock_get_cert,
        mock_get_course_run_url,
        mock_get_emails_enabled,
        mock_get_course_run_status,
        mock_get_overviews,
        mock_get_resume_urls,
    ):
        """
        View should update the enrollment's saved_for_later field and return serialized data from
         EnterpriseCourseEnrollmentSerializer for the enrollment (which we mock in this case)
        """
        mock_get_overviews.return_value = [{
            'id': self.course_run_id,
            'start': 'a datetime object',
            'end': 'a datetime object',
            'display_name_with_default': 'a default name',
            'pacing': 'instructor',
            'display_org_with_default': 'my university',
        }]
        mock_get_resume_urls.return_value = {
            self.course_run_id: '/courses/course-v1:MITx+6.86x+2T2024'
        }
        mock_get_cert.return_value = {
            'download_url': 'example.com',
            'is_passing': True,
            'created': 'a datetime object',
        }
        mock_get_course_run_url.return_value = 'course-run-url'
        mock_get_emails_enabled.return_value = True
        mock_get_course_run_status.return_value = 'completed'

        query_params = {
            'enterprise_id': str(self.enterprise_customer.uuid),
            'course_id': self.course_run_id,
            'saved_for_later': True,
        }

        assert not self.enterprise_enrollment.saved_for_later

        with mock.patch(
            'enterprise.models.EnterpriseCourseEnrollment.course_enrollment',
            new_callable=mock.PropertyMock,
        ) as mock_course_enrollment:
            mock_course_enrollment.return_value = mock.Mock(
                is_active=True,
                mode='verified',
            )
            resp = self.client.patch(
                '{host}{path}?{query_params}'.format(
                    host=settings.TEST_SERVER,
                    path=reverse('enterprise-learner-portal-course-enrollment-list'),
                    query_params=urlencode(query_params),
                )
            )
        assert resp.status_code == 200
        updated_record = resp.json()
        assert updated_record['course_run_id'] == self.course_run_id
        assert '/courses/course-v1:MITx+6.86x+2T2024' in updated_record['resume_course_run_url']

        self.enterprise_enrollment.refresh_from_db()
        assert self.enterprise_enrollment.saved_for_later

    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_patch_missing_params(self, mock_get_overviews, mock_serializer):
        """
        View should return 400 when called with missing required query_params.
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()
        query_params_full = {
            'enterprise_id': str(self.enterprise_customer.uuid),
            'course_id': self.course_run_id,
            'saved_for_later': 'true',
        }
        for key in query_params_full:
            query_params = query_params_full.copy()
            del query_params[key]
            resp = self.client.patch(
                '{host}{path}?{query_params}'.format(
                    host=settings.TEST_SERVER,
                    path=reverse('enterprise-learner-portal-course-enrollment-list'),
                    query_params=urlencode(query_params),
                )
            )
            assert resp.status_code == 400
            assert resp.json() == {
                'error': 'enterprise_id, course_id, and saved_for_later must be provided as query parameters'
            }

    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_patch_returns_not_found_unlinked_enterprise(self, mock_get_overviews, mock_serializer):
        """
        View should return 404 when called with an enterprise_id not associated with the user.
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()
        query_params = {
            'enterprise_id': str(uuid.uuid4()),
            'course_id': self.course_run_id,
            'saved_for_later': 'true',
        }

        resp = self.client.patch(
            '{host}{path}?{query_params}'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list'),
                query_params=urlencode(query_params),
            )
        )
        assert resp.status_code == 404
        assert resp.json() == {'detail': 'Not found.'}

    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_patch_returns_not_found_no_enrollment(self, mock_get_overviews, mock_serializer):
        """
        View should return 404 when called with an enterprise_id not associated with the user.
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()
        query_params = {
            'enterprise_id': str(self.enterprise_customer.uuid),
            'course_id': 'random_course_id',
            'saved_for_later': True,
        }

        resp = self.client.patch(
            '{host}{path}?{query_params}'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list'),
                query_params=urlencode(query_params),
            )
        )
        assert resp.status_code == 404
        assert resp.json() == {'detail': 'Not found.'}
