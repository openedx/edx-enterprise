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
from test_utils import factories


@mark.django_db
class TestLearnerCourseCompletionStatement(unittest.TestCase):
    """
    Tests for the ``LearnerCourseCompletionStatement`` model.
    """

    def setUp(self):
        super(TestLearnerCourseCompletionStatement, self).setUp()
        faker = FakerFactory.create()

        self.user = factories.UserFactory()
        self.mock_social_auth = Mock(provider='tpa-saml', uid='default:edxsso')
        # pylint: disable=no-member
        self.course_overview = Mock(
            id='course-v1:edX+DemoX+Demo_Course',
            display_name=faker.text(max_nb_chars=25),
            short_description=faker.text()
        )
        self.course_grade = Mock(percent=0.80, passed=True)

        self.expected = {
            'verb': {
                'id': X_API_VERB_COMPLETED,
                'display': {'en-US': 'completed'}
            },
            'version': '1.0.1',
            'actor': {
                'mbox': 'mailto:{email}'.format(email=self.user.email),
                'name': 'edxsso',
                'objectType': 'Agent'
            },
            'object': {
                'definition': {
                    'type': X_API_ACTIVITY_COURSE,
                    'description': {
                        'en-US': self.course_overview.short_description
                    },
                    'name': {
                        'en-US': self.course_overview.display_name
                    }
                },
                'id': self.course_overview.id,
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
        }

    def test_statement(self):
        """
        Validate statement when learner completes a course.
        """
        statement = LearnerCourseCompletionStatement(
            self.user,
            self.mock_social_auth,
            self.course_overview,
            self.course_grade,
        )
        self.assertDictEqual(json.loads(statement.to_json()), self.expected)
