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

    LOGGER.info(
        '[Integrated Channel][xAPI] Statement details: Type=%s, Event=%s, LRS=%s, Customer=%s',
        object_type,
        event_type,
        lrs_configuration.endpoint,
        customer_name
    )

    lrs_client = EnterpriseXAPIClient(lrs_configuration)

    try:
        LOGGER.debug(
            '[Integrated Channel][xAPI] Preparing to send statement to LRS. Statement JSON: %s',
            statement.to_json() if hasattr(statement, 'to_json') else 'No JSON representation available'
        )

        lrs_response = lrs_client.save_statement(statement)

        LOGGER.info(
            '[Integrated Channel][xAPI] Raw LRS response received: status=%s, data_type=%s',
            getattr(lrs_response.response, 'status', 'Unknown'),
            type(lrs_response.data).__name__ if hasattr(lrs_response, 'data') else 'None'
        )

        LOGGER.info(
            '[Integrated Channel][xAPI] Response data: %s',
            str(lrs_response.data) if hasattr(lrs_response, 'data') else 'No data'
        )

        if hasattr(lrs_response, 'response'):
            LOGGER.info(
                '[Integrated Channel][xAPI] Response headers: %s',
                str(getattr(lrs_response.response, 'headers', 'No headers'))
            )
            LOGGER.info(
                '[Integrated Channel][xAPI] Response content: %s',
                str(getattr(lrs_response.response, 'content', 'No content'))
            )

        response_fields.update({
            'status': lrs_response.response.status,
            'error_message': lrs_response.data
        })

    except ClientError as exc:
        error_message = f'EnterpriseXAPIClient request failed: {str(exc)}'
        LOGGER.exception(
            '[Integrated Channel][xAPI] %s Exception details: %s',
            error_message,
            logging.traceback.format_exc()
        )
        LOGGER.error(
            '[Integrated Channel][xAPI] Exception type: %s, Message: %s',
            type(exc).__name__,
            str(exc)
        )
        response_fields.update({
            'error_message': error_message
        })

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
