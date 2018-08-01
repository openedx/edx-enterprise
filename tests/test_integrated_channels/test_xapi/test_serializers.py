# -*- coding: utf-8 -*-
"""
Test for xAPI serializers.
"""

from __future__ import absolute_import, unicode_literals

import unittest
from datetime import datetime, timedelta

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark

from integrated_channels.utils import strfdelta
from integrated_channels.xapi.serializers import CourseInfoSerializer, LearnerInfoSerializer
from test_utils import TEST_COURSE, factories

FAKER = FakerFactory.create()

NOW = datetime.now()
TEST_ENTERPRISE_SSO_UID = 'saml-user-id'
TEST_COURSE_DESCRIPTION = FAKER.text()  # pylint: disable=no-member


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


@ddt.ddt
@mark.django_db
class TestCourseInfoSerializer(unittest.TestCase):
    """
    Tests for the ``CourseInfoSerializer`` model.
    """

    @ddt.data(
        (
            mock.Mock(
                **dict(
                    id=TEST_COURSE,
                    display_name='Test Course',
                    short_description=TEST_COURSE_DESCRIPTION,
                    marketing_url='https://edx.org/edx-test-course',
                    effort='3-4 weeks',
                    start=NOW,
                    end=NOW + timedelta(weeks=3, days=4),
                )
            ),
            dict(
                course_description=TEST_COURSE_DESCRIPTION,
                course_title='Test Course',
                course_duration=strfdelta((NOW + timedelta(weeks=3, days=4)) - NOW, '{W} weeks {D} days.'),
                course_effort='3-4 weeks',
                course_details_url='https://edx.org/edx-test-course',
                course_id=TEST_COURSE,
            )
        ),
        (
            mock.Mock(
                **dict(
                    id=TEST_COURSE,
                    display_name='Test Course',
                    short_description=TEST_COURSE_DESCRIPTION,
                    marketing_url='https://edx.org/edx-test-course',
                    effort='3-4 weeks',
                    start=None,
                    end=None,
                )
            ),
            dict(
                course_description=TEST_COURSE_DESCRIPTION,
                course_title='Test Course',
                course_duration='',
                course_effort='3-4 weeks',
                course_details_url='https://edx.org/edx-test-course',
                course_id=TEST_COURSE,
            )
        ),
    )
    @ddt.unpack
    def test_data(self, course_overview, expected_data):
        """
        Verify that serializer data is as expected.
        """
        assert CourseInfoSerializer(course_overview).data == expected_data
