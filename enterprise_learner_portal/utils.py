# -*- coding: utf-8 -*-
"""
enterprise_learner_portal utils.
"""


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
