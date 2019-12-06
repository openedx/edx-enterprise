# -*- coding: utf-8 -*-

"""
xAPI statement for learner course enrollment.
"""
from __future__ import absolute_import, unicode_literals

from tincan import LanguageMap, Verb

from integrated_channels.xapi.constants import X_API_VERB_REGISTERED
from integrated_channels.xapi.statements.base import EnterpriseStatement


class LearnerCourseEnrollmentStatement(EnterpriseStatement):
    """
    xAPI statement to serialize data related to course registration.
    """

    def __init__(self, user, user_social_auth, course_overview, *args, **kwargs):
        """
        Initialize and populate statement with learner info and course info.

        Arguments:
            user (User): Auth User object containing information about the learner enrolling in the course.
            user_social_auth (UserSocialAuth): UserSocialAuth object of learner for the enterprise if learner has a
            linked third party auth account
            course_overview (CourseOverview): course overview object containing course details.
        """
        kwargs.update(
            actor=self.get_actor(user, user_social_auth),
            verb=self.get_verb(),
            object=self.get_object(course_overview),
        )
        super(LearnerCourseEnrollmentStatement, self).__init__(*args, **kwargs)

    def get_verb(self):
        """
        Get verb for course enrollment statement.
        """
        return Verb(
            id=X_API_VERB_REGISTERED,
            display=LanguageMap({'en-US': 'registered'}),
        )
