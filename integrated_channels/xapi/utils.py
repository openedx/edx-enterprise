"""
Utility functions for xAPI.
"""

import logging

from enterprise.tpa_pipeline import get_user_social_auth
from integrated_channels.exceptions import ClientError
from integrated_channels.xapi.client import EnterpriseXAPIClient
from integrated_channels.xapi.statements.learner_course_completion import LearnerCourseCompletionStatement
from integrated_channels.xapi.statements.learner_course_enrollment import LearnerCourseEnrollmentStatement

LOGGER = logging.getLogger(__name__)


def _send_statement(statement, object_type, event_type, lrs_configuration,
                    customer_name, username, course_id, response_fields):
    """
    Transmit the specified xAPI Event information to the specified xAPI Learning Record Store service.
    """

    LOGGER.info(
        '[Integrated Channel][xAPI] Sending {object_type} enrollment to xAPI LRS for user: {username} '
        'for {object_type}: {course_id}'.format(
            object_type=object_type,
            username=username,
            course_id=course_id,
        )
    )

    lrs_client = EnterpriseXAPIClient(lrs_configuration)

    try:
        lrs_response = lrs_client.save_statement(statement)
        response_fields.update({
            'status': lrs_response.response.status,
            'error_message': lrs_response.data
        })

    except ClientError:
        error_message = 'EnterpriseXAPIClient request failed.'
        response_fields.update({
            'error_message': error_message
        })
        LOGGER.exception(error_message)

    status_string = 'Error transmitting'
    if response_fields['status'] == 200:
        status_string = 'Successfully transmitted'

    LOGGER.info(
        '[Integrated Channel][xAPI] {status_string} {object_type} {event_type} event to {lrs_hostname} for '
        'Enterprise Customer: {enterprise_customer}, User: {username} '
        'and {object_type}: {course_id}'.format(
            status_string=status_string,
            object_type=object_type,
            event_type=event_type,
            lrs_hostname=lrs_configuration.endpoint,
            enterprise_customer=customer_name,
            username=username,
            course_id=course_id,
        )
    )

    return response_fields


def send_course_enrollment_statement(lrs_configuration, user, course_overview, object_type, response_fields):
    """
    Send xAPI statement for course enrollment.

    Arguments:
         lrs_configuration (XAPILRSConfiguration): XAPILRSConfiguration instance where to send statements.
         user (User): User object.
         course_overview (CourseOverview): CourseOverview object containing course details.
    """
    event_type = 'enrollment'
    course_id = course_overview.course_key if object_type == 'course' else str(course_overview.id)
    username = user.username if user else 'Unavailable'
    user_social_auth = get_user_social_auth(user, lrs_configuration.enterprise_customer)

    statement = LearnerCourseEnrollmentStatement(
        lrs_configuration.enterprise_customer.site,
        user,
        user_social_auth,
        course_overview,
        object_type,
    )

    response_fields = _send_statement(
        statement,
        object_type,
        event_type,
        lrs_configuration,
        lrs_configuration.enterprise_customer.name,
        username,
        course_id,
        response_fields,
    )

    return response_fields


def send_course_completion_statement(lrs_configuration,
                                     user, course_overview, course_grade, object_type, response_fields):
    """
    Send xAPI statement for course completion.

    Arguments:
         lrs_configuration (XAPILRSConfiguration): XAPILRSConfiguration instance where to send statements.
         user (User): User object.
         course_overview (CourseOverview): Course overview object containing course details.
         course_grade (CourseGrade): Course grade object.
    """
    event_type = 'completion'
    course_id = course_overview.course_key if object_type == 'course' else str(course_overview.id)
    username = user.username if user else 'Unavailable'
    user_social_auth = get_user_social_auth(user, lrs_configuration.enterprise_customer)

    statement = LearnerCourseCompletionStatement(
        lrs_configuration.enterprise_customer.site,
        user,
        user_social_auth,
        course_overview,
        course_grade,
        object_type,
    )

    response_fields = _send_statement(
        statement,
        object_type,
        event_type,
        lrs_configuration,
        lrs_configuration.enterprise_customer.name,
        username,
        course_id,
        response_fields,
    )

    return response_fields


def is_success_response(response_fields):
    """
    Determines if a response is successful or not based on captured information
    Arguments: response_fields (dict)
    Returns: Boolean
    """
    success_response = False
    if response_fields['status'] == 200:
        success_response = True
    return success_response
