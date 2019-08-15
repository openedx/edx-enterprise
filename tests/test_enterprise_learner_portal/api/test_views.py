# -*- coding: utf-8 -*-
"""
Tests for the EnterpriseCourseEnrollmentview of the enterprise_learner_portal app.
"""

from __future__ import absolute_import, unicode_literals

import mock
from pytest import mark

from django.core.urlresolvers import reverse
from django.test import Client, TestCase

from enterprise.models import EnterpriseCourseEnrollment
from enterprise.utils import NotConnectedToOpenEdX
from test_utils import factories


@mark.django_db
class TestEnterpriseCourseEnrollmentView(TestCase):
    """
    EnterpriseCourseEnrollmentView tests.
    """

    def setUp(self):
        super(TestEnterpriseCourseEnrollmentView, self).setUp()

        enterprise_customer = factories.EnterpriseCustomerFactory()

        # Create our user we will enroll in a course
        self.user = factories.UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        enrolled_ent_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer,
        )
        course_run_id = 'course-v1:edX+DemoX+Demo_Course'
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=enrolled_ent_customer_user,
            course_id=course_run_id,
        )

        # Create a user we will not enroll in a course
        not_enrolled_user = factories.UserFactory(
            email='not_enrolled@example.com',
        )
        factories.EnterpriseCustomerUserFactory(
            user_id=not_enrolled_user.id,
            enterprise_customer=enterprise_customer,
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
        class MockSerializer(object):
            """ Returns obj with data property. """
            @property
            def data(self):
                """ Return fake serialized data. """
                return {'hooray': 'here is the data'}

        mock_get_overviews.return_value = {'overview_info': 'this would be a larger dict'}
        mock_serializer.return_value = MockSerializer()

        url = reverse('enterprise-learner-portal-course-enrollment-list')
        resp = self.client.get(url)
        assert resp.status_code == 200
        assert resp.json() == {'hooray': 'here is the data'}

    def test_view_requires_openedx_installation(self):
        """
        View should raise error if imports to helper methods fail.
        """
        url = reverse('enterprise-learner-portal-course-enrollment-list')
        with self.assertRaises(NotConnectedToOpenEdX):
            self.client.get(url)
