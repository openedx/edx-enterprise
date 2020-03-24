# -*- coding: utf-8 -*-

"""
Utility functions for xAPI.
"""

from __future__ import absolute_import, unicode_literals

import logging

import six

from enterprise.tpa_pipeline import get_user_social_auth
from integrated_channels.xapi.client import EnterpriseXAPIClient
from integrated_channels.xapi.statements.learner_course_completion import LearnerCourseCompletionStatement
from integrated_channels.xapi.statements.learner_course_enrollment import LearnerCourseEnrollmentStatement

LOGGER = logging.getLogger(__name__)


def send_course_enrollment_statement(lrs_configuration, course_enrollment):
    """
    Send xAPI statement for course enrollment.

    Arguments:
         lrs_configuration (XAPILRSConfiguration): XAPILRSConfiguration instance where to send statements.
         course_enrollment (CourseEnrollment): Course enrollment object.
    """
    user = course_enrollment.user
    LOGGER.info(
        'Sending course enrollment to xAPI for user: {username} for course: {course_key}'.format(
            username=user.username,
            course_key=six.text_type(course_enrollment.course.id)
        )
    )

    user_social_auth = get_user_social_auth(user, lrs_configuration.enterprise_customer)
    statement = LearnerCourseEnrollmentStatement(
        user,
        user_social_auth,
        course_enrollment.course,
    )
    EnterpriseXAPIClient(lrs_configuration).save_statement(statement)


def send_course_completion_statement(lrs_configuration, user, course_overview, course_grade):
    """
    Send xAPI statement for course completion.

    Arguments:
         lrs_configuration (XAPILRSConfiguration): XAPILRSConfiguration instance where to send statements.
         user (User): Django User object.
         course_overview (CourseOverview): Course over view object containing course details.
         course_grade (CourseGrade): course grade object.
    """
    LOGGER.info(
        'Sending course completion to xAPI for user: {username}, course: {course_key} with {percentage}%'.format(
            username=user.username if user else '',
            course_key=six.text_type(course_overview.id),
            percentage=course_grade.percent * 100
        )
    )
    user_social_auth = get_user_social_auth(user, lrs_configuration.enterprise_customer)
    statement = LearnerCourseCompletionStatement(
        user,
        user_social_auth,
        course_overview,
        course_grade,
    )
    return EnterpriseXAPIClient(lrs_configuration).save_statement(statement)
