# -*- coding: utf-8 -*-
"""
Test for xAPI serializers.
"""

from __future__ import absolute_import, unicode_literals

import unittest
from datetime import datetime, timedelta

import mock
from faker import Factory as FakerFactory
from pytest import mark

from integrated_channels.xapi.serializers import CourseInfoSerializer, LearnerInfoSerializer
from test_utils import factories

TEST_ENTERPRISE_SSO_UID = 'saml-user-id'


@mark.django_db
class TestLearnerInfoSerializer(unittest.TestCase):
    """
    Tests for the ``LearnerInfoSerializer`` model.
    """

    def setUp(self):
        super(TestLearnerInfoSerializer, self).setUp()
        self.user = factories.UserFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=self.user.id)
        # pylint: disable=invalid-name
        self.enterprise_customer_identity_provider = factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer_user.enterprise_customer
        )

        self.expected_data = {
            'enterprise_sso_uid': TEST_ENTERPRISE_SSO_UID,
            'lms_user_id': self.user.id,
            'enterprise_user_id': self.enterprise_customer_user.id,
            'user_username': self.user.username,
            'user_account_creation_date': self.user.date_joined.strftime("%Y-%m-%dT%H:%M:%SZ"),
            'user_country_code': 'PK',
            'user_email': self.user.email
        }

    @mock.patch('enterprise.models.ThirdPartyAuthApiClient')
    def test_data(self, mock_third_party_api):
        """
        Verify that serializer data is as expected.
        """
        mock_third_party_api.return_value.get_remote_id.return_value = TEST_ENTERPRISE_SSO_UID

        with mock.patch.object(self.user, 'profile', create=True) as mock_user_profile:
            mock_user_profile.country.code = 'PK'
            assert LearnerInfoSerializer(self.user).data == self.expected_data

    def test_data_with_no_enterprise_customer_user(self):
        """
        Verify that serializer data is as expected in case when user does not belong to an enterprise.
        """
        # Remove the link between the user and enterprise customer
        self.enterprise_customer_user.delete()

        # update expected data
        self.expected_data.update(enterprise_sso_uid=None, enterprise_user_id=None)

        with mock.patch.object(self.user, 'profile', create=True) as mock_user_profile:
            mock_user_profile.country.code = 'PK'
            assert LearnerInfoSerializer(self.user).data == self.expected_data


@mark.django_db
class TestCourseInfoSerializer(unittest.TestCase):
    """
    Tests for the ``CourseInfoSerializer`` model.
    """

    def setUp(self):
        super(TestCourseInfoSerializer, self).setUp()
        self.faker = FakerFactory.create()

        now = datetime.now()
        self.course_overview_mock_data = dict(
            id=self.faker.text(max_nb_chars=25),  # pylint: disable=no-member
            display_name=self.faker.text(max_nb_chars=25),  # pylint: disable=no-member
            short_description=self.faker.text(),  # pylint: disable=no-member
            marketing_url=self.faker.url(),  # pylint: disable=no-member
            effort=self.faker.text(max_nb_chars=10),  # pylint: disable=no-member
            start=now,
            end=now + timedelta(weeks=3, days=4),
        )
        self.course_overview = mock.Mock(**self.course_overview_mock_data)

        self.expected_data = {
            'course_description': self.course_overview_mock_data['short_description'],
            'course_title': self.course_overview_mock_data['display_name'],
            'course_duration': self.course_overview_mock_data['end'] - self.course_overview_mock_data['start'],
            'course_effort': self.course_overview_mock_data['effort'],
            'course_details_url': self.course_overview_mock_data['marketing_url'],
            'course_id': self.course_overview_mock_data['id'],
        }

    def test_data(self):
        """
        Verify that serializer data is as expected.
        """

        assert CourseInfoSerializer(self.course_overview).data == self.expected_data
