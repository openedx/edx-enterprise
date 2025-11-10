"""
Test for xAPI Learner Course Completion Statements.
"""

import json
import unittest
from unittest.mock import Mock

from faker import Factory as FakerFactory
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
        super().setUp()
        faker = FakerFactory.create()

        self.site = Mock(domain='xapi.testing.com')
        self.user = factories.UserFactory()
        self.mock_social_auth = Mock(provider='tpa-saml', uid='default:edxsso')

        self.course_overview = Mock(
            id='course-v1:edX+DemoX+Demo_Course',
            display_name=faker.text(max_nb_chars=25),  # pylint: disable=no-member
            short_description=faker.text(),  # pylint: disable=no-member
            course_key='edX+DemoX',
            course_uuid='b1e7c719af3c42288c6f50e2124bb913',
        )
        self.course_grade = Mock(percent_grade=0.80, passed_timestamp='2020-04-01')
        self.course_grade_notpassed = Mock(percent_grade=0.50, passed_timestamp=None)

        self.object_id_course = 'https://{domain}/xapi/activities/course/{activity_id}'.format(
            domain=self.site.domain,
            activity_id=self.course_overview.course_key)

        self.object_id_courserun = 'https://{domain}/xapi/activities/courserun/{activity_id}'.format(
            domain=self.site.domain,
            activity_id=self.course_overview.id)

        self.verb = {
            'id': X_API_VERB_COMPLETED,
            'display': {'en-US': 'completed'}
        }
        self.actor = {
            'mbox': 'mailto:{email}'.format(email=self.user.email),
            'name': 'edxsso',
            'objectType': 'Agent'
        }

        self.extensions = {}

        self.extension_course_key = 'https://{domain}/course/key'.format(domain=self.site.domain)
        self.extensions[self.extension_course_key] = self.course_overview.course_key

        self.extension_course_uuid = 'https://{domain}/course/uuid'.format(domain=self.site.domain)
        self.extensions[self.extension_course_uuid] = self.course_overview.course_uuid

        self.object_course = {
            'definition': {
                'type': X_API_ACTIVITY_COURSE,
                'description': {
                    'en-US': self.course_overview.short_description
                },
                'name': {
                    'en-US': self.course_overview.display_name
                },
                "extensions": self.extensions
            },
            'id': self.object_id_course,
            'objectType': 'Activity'
        }

        self.object_courserun = {
            'definition': {
                'type': X_API_ACTIVITY_COURSE,
                'description': {
                    'en-US': self.course_overview.short_description
                },
                'name': {
                    'en-US': self.course_overview.display_name
                },
                "extensions": self.extensions
            },
            'id': self.object_id_courserun,
            'objectType': 'Activity'
        }

        self.result = {
            'score': {
                'scaled': 0.8,
                'raw': 80,
                'min': 0,
                'max': 100
            },
            'success': True,
            'completion': True,
        }

        self.result_notpassed = {
            'score': {
                'scaled': 0.5,
                'raw': 50,
                'min': 0,
                'max': 100
            },
            'success': False,
            'completion': False,
        }

        self.expected_course = {
            'verb': self.verb,
            'version': '1.0.3',
            'actor': self.actor,
            'object': self.object_course,
            'result': self.result,
        }

        self.expected_courserun = {
            'verb': self.verb,
            'version': '1.0.3',
            'actor': self.actor,
            'object': self.object_courserun,
            'result': self.result,
        }

        self.expected_notpassed = {
            'verb': self.verb,
            'version': '1.0.3',
            'actor': self.actor,
            'object': self.object_course,
            'result': self.result_notpassed,
        }

    def test_statement_course(self):
        """
        Validate statement when learner completes a course.
        """
        statement = LearnerCourseCompletionStatement(
            self.site,
            self.user,
            self.mock_social_auth,
            self.course_overview,
            self.course_grade,
            'course'
        )
        self.assertDictEqual(json.loads(statement.to_json()), self.expected_course)

    def test_statement_courserun(self):
        """
        Validate statement when learner completes a course.
        """
        statement = LearnerCourseCompletionStatement(
            self.site,
            self.user,
            self.mock_social_auth,
            self.course_overview,
            self.course_grade,
            'courserun'
        )
        self.assertDictEqual(json.loads(statement.to_json()), self.expected_courserun)

    def test_statement_notpassed(self):
        """
        Validate statement when learner completes a course.
        """
        statement = LearnerCourseCompletionStatement(
            self.site,
            self.user,
            self.mock_social_auth,
            self.course_overview,
            self.course_grade_notpassed,
            'course'
        )
        self.assertDictEqual(json.loads(statement.to_json()), self.expected_notpassed)
