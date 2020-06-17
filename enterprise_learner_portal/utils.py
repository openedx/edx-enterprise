# -*- coding: utf-8 -*-
"""
enterprise_learner_portal utils.
"""
from __future__ import absolute_import, unicode_literals

from datetime import datetime, timedelta

from pytz import UTC


class CourseRunProgressStatuses:
    """
    Class to group statuses that a course run can be in with respect to user progress.
    """

    IN_PROGRESS = 'in_progress'
    UPCOMING = 'upcoming'
    COMPLETED = 'completed'


def get_course_run_status(course_overview, certificate_info, enterprise_enrollment):
    """
    Get the progress status of a course run, given the state of a user's certificate in the course.

    In the case of self-paced course runs, the run is considered completed when either the course run has ended
    OR the user has earned a passing certificate 30 days ago or longer.

    Arguments:
        course_overview (CourseOverview): the overview for the course run
        certificate_info: A dict containing the following keys:
            ``is_passing``: whether the  user has a passing certificate in the course run
            ``created``: the date the certificate was created

    Returns:
        status: one of (
            CourseRunProgressStatuses.COMPLETE,
            CourseRunProgressStatuses.IN_PROGRESS,
            CourseRunProgressStatuses.UPCOMING,
        )
        None if pacing type is not matched
    """
    is_certificate_passing = certificate_info.get('is_passing', False)
    certificate_creation_date = certificate_info.get('created', datetime.max)

    if enterprise_enrollment and enterprise_enrollment.marked_done:
        return CourseRunProgressStatuses.COMPLETED
    if course_overview['pacing'] == 'instructor':
        if course_overview['has_ended']:
            return CourseRunProgressStatuses.COMPLETED
        if course_overview['has_started']:
            return CourseRunProgressStatuses.IN_PROGRESS
        return CourseRunProgressStatuses.UPCOMING
    if course_overview['pacing'] == 'self':
        thirty_days_ago = datetime.now(UTC) - timedelta(30)
        certificate_completed = is_certificate_passing and (certificate_creation_date <= thirty_days_ago)
        if course_overview['has_ended'] or certificate_completed:
            return CourseRunProgressStatuses.COMPLETED
        if course_overview['has_started']:
            return CourseRunProgressStatuses.IN_PROGRESS
        return CourseRunProgressStatuses.UPCOMING
    return None
