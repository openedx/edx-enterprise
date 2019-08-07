# -*- coding: utf-8 -*-
"""
Tests for the EnterpriseCourseEnrollmentview of the enterprise_learner_portal app.
"""

from __future__ import absolute_import, unicode_literals

from collections import OrderedDict

import mock
from pytest import mark

from django.test import RequestFactory, TestCase

from enterprise.utils import NotConnectedToOpenEdX
from enterprise_learner_portal.api.v1.serializers import EnterpriseCourseEnrollmentSerializer
from test_utils import factories


@mark.django_db
class TestEnterpriseCourseEnrollmentSerializer(TestCase):
    """
    EnterpriseCourseEnrollmentSerializer tests.
    """

    def setUp(self):
        super(TestEnterpriseCourseEnrollmentSerializer, self).setUp()

        self.user = factories.UserFactory.create(is_staff=True, is_active=True)
        self.factory = RequestFactory()

    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_course_run_status')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_emails_enabled')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_course_run_url')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_due_dates')
    @mock.patch('enterprise_learner_portal.api.v1.serializers.get_certificate_for_user')
    def test_serializer_representation(
            self,
            mock_get_cert,
            mock_get_due_dates,
            mock_get_course_run_url,
            mock_get_emails_enabled,
            mock_get_course_run_status,
    ):
        """
        EnterpriseCourseEnrollmentSerializer should create proper representation
        based on the instance data it receives (a course_overview)
        """
        mock_get_cert.return_value = {
            'download_url': 'example.com',
            'is_passing': True,
            'created': 'a datetime object',
        }
        mock_get_due_dates.return_value = ['some', 'dates']
        mock_get_course_run_url.return_value = 'example.com'
        mock_get_emails_enabled.return_value = True
        mock_get_course_run_status.return_value = 'completed'

        input_data = {
            'id': 'some+id+here',
            'start': 'a datetime object',
            'end': 'a datetime object',
            'display_name_with_default': 'a default name',
            'pacing': 'instructor',
            'display_org_with_default': 'my university',
        }

        request = self.factory.get('/')
        request.user = self.user

        serializer = EnterpriseCourseEnrollmentSerializer(
            [input_data],
            many=True,
            context={'request': request},
        )

        expected = OrderedDict([
            ('certificate_download_url', 'example.com'),
            ('emails_enabled', True),
            ('course_run_id', 'some+id+here'),
            ('course_run_status', 'completed'),
            ('start_date', 'a datetime object'),
            ('end_date', 'a datetime object'),
            ('display_name', 'a default name'),
            ('course_run_url', 'example.com'),
            ('due_dates', ['some', 'dates']),
            ('pacing', 'instructor'),
            ('org_name', 'my university'),
        ])
        actual = serializer.data[0]
        self.assertDictEqual(actual, expected)

    def test_view_requires_openedx_installation(self):
        """
        View should raise error if imports to helper methods fail.
        """
        with self.assertRaises(NotConnectedToOpenEdX):
            EnterpriseCourseEnrollmentSerializer({})
