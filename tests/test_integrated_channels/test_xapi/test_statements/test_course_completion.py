# -*- coding: utf-8 -*-
"""
Test for xAPI Learner Course Completion Statements.
"""

from __future__ import absolute_import, unicode_literals

import json
import unittest

from faker import Factory as FakerFactory
from mock import Mock
from pytest import mark

from integrated_channels.xapi.constants import X_API_ACTIVITY_COURSE, X_API_VERB_COMPLETED
from integrated_channels.xapi.statements.learner_course_completion import LearnerCourseCompletionStatement
from test_utils import TEST_COURSE, TEST_UUID, factories


@mark.django_db
class TestLearnerCourseCompletionStatement(unittest.TestCase):
    """
    Tests for the ``LearnerCourseCompletionStatement`` model.
    """

    def setUp(self):
        super(TestLearnerCourseCompletionStatement, self).setUp()
        faker = FakerFactory.create()

        self.user = factories.UserFactory()
        # pylint: disable=no-member
        self.course_overview = Mock(display_name=faker.text(max_nb_chars=25), short_description=faker.text())
        self.course_grade = Mock(percent=0.80, passed=True)

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
                    'id': X_API_VERB_COMPLETED,
                    'display': {'en-US': 'completed'}
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
            'result': {
                'score': {
                    'scaled': 0.8,
                    'raw': 80,
                    'min': 0,
                    'max': 100
                },
                'success': True,
                'completion': True,
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
        Validate statement when learner completes a course.
        """
        statement = LearnerCourseCompletionStatement(
            self.user,
            self.course_overview,
            self.user_details,
            self.course_details,
            self.course_grade,
        )
        assert json.loads(statement.to_json()) == self.expected
