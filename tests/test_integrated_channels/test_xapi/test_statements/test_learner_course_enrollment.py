"""
Test for xAPI Learner Course Enrollment Statements.
"""

import json
import unittest
from unittest.mock import Mock

from faker import Factory as FakerFactory
from pytest import mark

from integrated_channels.xapi.constants import X_API_ACTIVITY_COURSE, X_API_VERB_REGISTERED
from integrated_channels.xapi.statements.learner_course_enrollment import LearnerCourseEnrollmentStatement
from test_utils import factories


@mark.django_db
class TestLearnerCourseEnrollmentStatement(unittest.TestCase):
    """
    Tests for the ``LearnerCourseEnrollmentStatement`` model.
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

        self.object_id_course = 'https://{domain}/xapi/activities/course/{activity_id}'.format(
            domain=self.site.domain,
            activity_id=self.course_overview.course_key)

        self.object_id_courserun = 'https://{domain}/xapi/activities/courserun/{activity_id}'.format(
            domain=self.site.domain,
            activity_id=self.course_overview.id)

        self.verb = {
            'id': X_API_VERB_REGISTERED,
            'display': {'en-US': 'registered'}
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
            'definition':
                {
                    'type': X_API_ACTIVITY_COURSE,
                    'description':
                        {
                            'en-US': self.course_overview.short_description
                        },
                    'name':
                        {
                            'en-US': self.course_overview.display_name
                        },
                    "extensions": self.extensions
                },
            'id': self.object_id_course,
            'objectType': 'Activity'
        }

        self.object_courserun = {
            'definition':
                {
                    'type': X_API_ACTIVITY_COURSE,
                    'description':
                        {
                            'en-US': self.course_overview.short_description
                        },
                    'name':
                        {
                            'en-US': self.course_overview.display_name
                        },
                    "extensions": self.extensions
                },
            'id': self.object_id_courserun,
            'objectType': 'Activity'
        }

        self.expected_course = {
            'verb': self.verb,
            'version': '1.0.3',
            'actor': self.actor,
            'object': self.object_course
        }

        self.expected_courserun = {
            'verb': self.verb,
            'version': '1.0.3',
            'actor': self.actor,
            'object': self.object_courserun
        }

    def test_statement_course(self):
        """
        Validate statement when learner enrolls in a course.
        """
        statement = LearnerCourseEnrollmentStatement(
            self.site,
            self.user,
            self.mock_social_auth,
            self.course_overview,
            'course',
        )
        self.assertDictEqual(json.loads(statement.to_json()), self.expected_course)

    def test_statement_courserun(self):
        """
        Validate statement when learner enrolls in a course.
        """
        statement = LearnerCourseEnrollmentStatement(
            self.site,
            self.user,
            self.mock_social_auth,
            self.course_overview,
            'courserun',
        )
        self.assertDictEqual(json.loads(statement.to_json()), self.expected_courserun)
