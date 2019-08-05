# -*- coding: utf-8 -*-

"""
Utility functions for xAPI.
"""

from __future__ import absolute_import, unicode_literals

import logging

import six

from integrated_channels.xapi.client import EnterpriseXAPIClient
from integrated_channels.xapi.serializers import CourseInfoSerializer, LearnerInfoSerializer
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
    user_details = LearnerInfoSerializer(course_enrollment.user)
    course_details = CourseInfoSerializer(
        course_enrollment.course,
        context={'site': lrs_configuration.enterprise_customer.site}
    )
    LOGGER.info(
        'Sending course enrollment to xAPI for user: {username} for course: {course_key}'.format(
            username=course_enrollment.user.username,
            course_key=six.text_type(course_enrollment.course.id)
        )
    )
    statement = LearnerCourseEnrollmentStatement(
        course_enrollment.user,
        course_enrollment.course,
        user_details.data,
        course_details.data,
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
    user_details = LearnerInfoSerializer(user)
    course_details = CourseInfoSerializer(
        course_overview,
        context={'site': lrs_configuration.enterprise_customer.site}
    )
    LOGGER.info(
        'Sending course completion to xAPI for user: {username}, course: {course_key} with {percentage}%'.format(
            username=user.username if user else '',
            course_key=six.text_type(course_overview.id),
            percentage=course_grade.percent * 100
        )
    )
    statement = LearnerCourseCompletionStatement(
        user,
        course_overview,
        user_details.data,
        course_details.data,
        course_grade,
    )
    EnterpriseXAPIClient(lrs_configuration).save_statement(statement)
