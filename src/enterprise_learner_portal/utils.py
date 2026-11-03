"""
enterprise_learner_portal utils.
"""
from datetime import datetime

from pytz import utc


class CourseRunProgressStatuses:
    """
    Class to group statuses that a course run can be in with respect to user progress.
    """

    IN_PROGRESS = 'in_progress'
    UPCOMING = 'upcoming'
    COMPLETED = 'completed'
    SAVED_FOR_LATER = 'saved_for_later'


def get_course_run_status(course_overview, certificate_info, enterprise_enrollment):
    """
    Get the status of a course run, given the state of a user's certificate in the course.

    A run is considered "complete" when either the course run has ended OR the user has earned a
    passing certificate.

    Arguments:
        course_overview (CourseOverview): the overview for the course run
        certificate_info: A dict containing the following key:
            ``is_passing``: whether the  user has a passing certificate in the course run

    Returns:
        status: one of (
            CourseRunProgressStatuses.SAVED_FOR_LATER,
            CourseRunProgressStatuses.COMPLETE,
            CourseRunProgressStatuses.IN_PROGRESS,
            CourseRunProgressStatuses.UPCOMING,
        )
    """
    if enterprise_enrollment and enterprise_enrollment.saved_for_later:
        return CourseRunProgressStatuses.SAVED_FOR_LATER

    is_certificate_passing = certificate_info.get('is_passing', False)

    if course_overview['has_ended'] or is_certificate_passing:
        return CourseRunProgressStatuses.COMPLETED
    if course_overview['has_started']:
        return CourseRunProgressStatuses.IN_PROGRESS
    return CourseRunProgressStatuses.UPCOMING


def get_exec_ed_course_run_status(course_details, certificate_info, enterprise_enrollment):
    """
    Get the status of a exec ed course run, given the state of a user's certificate in the course.

    A run is considered "complete" when either the course run has ended OR the user has earned a
    passing certificate.

    Arguments:
        course_details : the details for the exececutive education course run
        certificate_info: A dict containing the following key:
            ``is_passing``: whether the  user has a passing certificate in the course run

    Returns:
        status: one of (
            CourseRunProgressStatuses.SAVED_FOR_LATER,
            CourseRunProgressStatuses.COMPLETE,
            CourseRunProgressStatuses.IN_PROGRESS,
            CourseRunProgressStatuses.UPCOMING,
        )
    """
    if enterprise_enrollment and enterprise_enrollment.saved_for_later:
        return CourseRunProgressStatuses.SAVED_FOR_LATER

    is_certificate_passing = certificate_info.get('is_passing', False)
    start_date = course_details.start_date
    end_date = course_details.end_date

    has_started = datetime.now(utc) > start_date if start_date is not None else True
    has_ended = datetime.now(utc) > end_date if end_date is not None else False

    if has_ended or is_certificate_passing:
        return CourseRunProgressStatuses.COMPLETED
    if has_started:
        return CourseRunProgressStatuses.IN_PROGRESS
    return CourseRunProgressStatuses.UPCOMING
