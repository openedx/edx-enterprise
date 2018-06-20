# -*- coding: utf-8 -*-
"""
Test for xAPI Learner Course Enrollment Statements.
"""

from __future__ import absolute_import, unicode_literals

import json
import unittest

from faker import Factory as FakerFactory
from mock import Mock
from pytest import mark

from integrated_channels.xapi.constants import X_API_ACTIVITY_COURSE, X_API_VERB_REGISTERED
from integrated_channels.xapi.statements.learner_course_enrollment import LearnerCourseEnrollmentStatement
from test_utils import TEST_COURSE, TEST_UUID, factories


@mark.django_db
class TestLearnerCourseEnrollmentStatement(unittest.TestCase):
    """
    Tests for the ``LearnerCourseEnrollmentStatement`` model.
    """

    def setUp(self):
        super(TestLearnerCourseEnrollmentStatement, self).setUp()
        faker = FakerFactory.create()

        self.user = factories.UserFactory()
        # pylint: disable=no-member
        self.course_overview = Mock(display_name=faker.text(max_nb_chars=25), short_description=faker.text())

        self.user_details = {
            'enrollment_created_timestamp': '2018-06-25T04:45:32.642094',
            'enterprise_user_id': 1,
            'lms_user_id': 2,
            'enterprise_sso_uid': TEST_UUID,
            'user_account_creation_date': '2017-09-27T02:51:32.612293',
            'user_email': 'user@example.com',
            'user_username': 'test_user',
            'user_country_code': 'PK',
            'user_current_enrollment_mode': 'verified',
        }
        self.course_details = {
            'course_id': TEST_COURSE,
            'course_title': self.course_overview.display_name,
            'course_duration': '6 Months',
            'course_min_effort': '3 days per week',
        }

        self.expected = {
            'verb':
                {
                    'id': X_API_VERB_REGISTERED,
                    'display': {'en-US': 'registered'}
                },
            'version': '1.0.1',
            'actor':
                {
                    'mbox': 'mailto:{email}'.format(email=self.user.email),
                    'name': self.user.username,
                    'objectType': 'Agent'
                },
            'object':
                {
                    'definition':
                        {
                            'description':
                                {
                                    'en-US': self.course_overview.short_description
                                },
                            'name':
                                {
                                    'en-US': self.course_overview.display_name
                                }
                        },
                    'id': X_API_ACTIVITY_COURSE,
                    'objectType': 'Activity'
                },
            'context':
                {
                    'extensions': {
                        'http://id.tincanapi.com/extension/course-details': self.course_details,
                        'http://id.tincanapi.com/extension/user-details': self.user_details
                    }
                },
        }

    def test_statement(self):
        """
        Validate statement when learner enrolls in a course.
        """
        statement = LearnerCourseEnrollmentStatement(
            self.user,
            self.course_overview,
            self.user_details,
            self.course_details,
        )
        assert json.loads(statement.to_json()) == self.expected
