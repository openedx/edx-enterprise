# -*- coding: utf-8 -*-
"""
Tests for the EnterpriseCourseEnrollmentview of the enterprise_learner_portal app.
"""

from __future__ import absolute_import, unicode_literals

import uuid

import mock
from pytest import mark
from six.moves.urllib.parse import urlencode  # pylint: disable=import-error

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from enterprise.utils import NotConnectedToOpenEdX
from test_utils import factories


@mark.django_db
class TestEnterpriseCourseEnrollmentView(TestCase):
    """
    EnterpriseCourseEnrollmentView tests.
    """

    class MockSerializer:
        """ Returns obj with data property. """

        @property
        def data(self):
            """ Return fake serialized data. """
            return {'hooray': 'here is the data'}

    def setUp(self):
        super(TestEnterpriseCourseEnrollmentView, self).setUp()

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

    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_view_returns_information(self, mock_get_overviews, mock_serializer):
        """
        View should return data created by EnterpriseCourseEnrollmentSerializer
        (which we mock in this case)
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()

        resp = self.client.get(
            '{host}{path}?enterprise_id={enterprise_id}'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list'),
                enterprise_id=str(self.enterprise_customer.uuid)
            )
        )
        assert resp.status_code == 200
        assert resp.json() == {'hooray': 'here is the data'}

    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_view_returns_bad_request_without_enterprise(self, mock_get_overviews, mock_serializer):
        """
        View should return a 400 because of the missing enterprise_id parameter.
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()

        resp = self.client.get(
            '{host}{path}'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list')
            )
        )
        assert resp.status_code == 400
        assert resp.json() == {'error': 'enterprise_id must be provided as a query parameter'}

    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_view_returns_not_found_unlinked_enterprise(self, mock_get_overviews, mock_serializer):
        """
        View should return a 404 because the user is not linked to the enterprise.
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()

        resp = self.client.get(
            '{host}{path}?enterprise_id={enterprise_id}'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list'),
                enterprise_id=str(uuid.uuid4()),
            )
        )
        assert resp.status_code == 404
        assert resp.json() == {'detail': 'Not found.'}

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
                'marked_done': True,
            }

            self.client.patch(
                '{host}{path}?{query_params}'.format(
                    host=settings.TEST_SERVER,
                    path=reverse('enterprise-learner-portal-course-enrollment-list'),
                    query_params=urlencode(query_params),
                )
            )

    @mock.patch('enterprise_learner_portal.api.v1.views.EnterpriseCourseEnrollmentSerializer')
    @mock.patch('enterprise_learner_portal.api.v1.views.get_course_overviews')
    def test_patch_success(self, mock_get_overviews, mock_serializer):
        """
        View should update the enrollment's marked_done field and return serialized data from
         EnterpriseCourseEnrollmentSerializer for the enrollment (which we mock in this case)
        """
        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = self.MockSerializer()
        query_params = {
            'enterprise_id': str(self.enterprise_customer.uuid),
            'course_id': self.course_run_id,
            'marked_done': 'true',
        }

        assert not self.enterprise_enrollment.marked_done

        resp = self.client.patch(
            '{host}{path}?{query_params}'.format(
                host=settings.TEST_SERVER,
                path=reverse('enterprise-learner-portal-course-enrollment-list'),
                query_params=urlencode(query_params),
            )
        )
        assert resp.status_code == 200
        assert resp.json() == {'hooray': 'here is the data'}

        self.enterprise_enrollment.refresh_from_db()
        assert self.enterprise_enrollment.marked_done

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
            'marked_done': 'true',
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
                'error': 'enterprise_id, course_id, and marked_done must be provided as query parameters'
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
            'marked_done': 'true',
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
            'marked_done': True,
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
