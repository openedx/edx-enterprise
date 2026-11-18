"""
enterprise_learner_portal utils.
"""
from datetime import datetime
from functools import partial

from edx_django_utils.cache import TieredCache, get_cache_key
from opaque_keys.edx.keys import CourseKey
from pytz import utc

from enterprise.logging import getEnterpriseLogger
from enterprise.toggles import show_failed_self_paced_runs_as_completed

# one import per block, so each import line runs (and is covered) outside the LMS
try:
    from common.djangoapps.course_modes.models import CourseMode
except ImportError:
    CourseMode = None
try:
    from lms.djangoapps.course_blocks.api import get_course_blocks
except ImportError:
    get_course_blocks = None
try:
    from lms.djangoapps.course_blocks.transformers.start_date import StartDateTransformer
except ImportError:
    StartDateTransformer = None
try:
    from lms.djangoapps.courseware.access_utils import adjust_start_date
except ImportError:
    adjust_start_date = None
try:
    from lms.djangoapps.grades.api import CourseGradeFactory
except ImportError:
    CourseGradeFactory = None
try:
    from openedx.core.djangoapps.content.block_structure.api import get_course_in_cache
except ImportError:
    get_course_in_cache = None

LOGGER = getEnterpriseLogger(__name__)

# Checking every graded subsection loads the course structure, so the answer is cached for at most a day.
FAILED_COURSE_RUN_CACHE_TIMEOUT = 60 * 60 * 24
# A course structure that cannot be loaded (an old run's content can be gone from the modulestore) is answered "not
# failed" for this long, so each dashboard load does not load it, and log the error, again.
FAILED_COURSE_RUN_ERROR_CACHE_TIMEOUT = 60 * 60


class CourseRunProgressStatuses:
    """
    Class to group statuses that a course run can be in with respect to user progress.
    """

    IN_PROGRESS = 'in_progress'
    UPCOMING = 'upcoming'
    COMPLETED = 'completed'
    SAVED_FOR_LATER = 'saved_for_later'


def get_course_run_status(course_overview, certificate_info, enterprise_enrollment, is_failed_run=None):
    """
    Get the status of a course run, given the state of a user's certificate in the course.

    A run is considered "complete" when either the course run has ended OR the user has earned a
    passing certificate OR, when ``is_failed_run`` is given and returns True, the user has failed
    the run before it ends.

    Arguments:
        course_overview (CourseOverview): the overview for the course run
        certificate_info: A dict containing the following key:
            ``is_passing``: whether the  user has a passing certificate in the course run
        is_failed_run (callable): optional, no arguments; only called for a started, open run without a passing cert

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
        if is_failed_run and is_failed_run():
            return CourseRunProgressStatuses.COMPLETED
        return CourseRunProgressStatuses.IN_PROGRESS
    return CourseRunProgressStatuses.UPCOMING


def get_failed_course_run_check(user, course_run_id, course_overview, enrollment_mode):
    """
    Get the ``is_failed_run`` check for a self-paced run (it ends years out) in a mode that earns a certificate, while
    the ``enterprise.show_failed_self_paced_runs_as_completed`` waffle flag is on.

    Other runs get None: the LMS never shows an audit learner as not passing. A 2U Exec Ed run gets the check too, but
    the serializer then replaces its status with ``get_exec_ed_course_run_status``.
    """
    if not show_failed_self_paced_runs_as_completed():
        return None
    if course_overview['pacing'] != 'self' or CourseMode is None or not enrollment_mode:
        return None
    if not CourseMode.is_eligible_for_certificate(enrollment_mode):
        return None
    return partial(has_failed_course_run, user, course_run_id, course_overview.get('modified'))


def has_failed_course_run(user, course_run_id, course_modified=None):
    """
    Return whether the user has failed the course run before it ends, with no waiting period.

    That is: the course grade is below passing, no content is scheduled for release, and every graded subsection the
    LMS grader counts (``graded_subsections_by_format``) is attempted. Only a learner below passing loads the course
    structure, and that answer is cached until the grade or the course (``course_modified``: each publish updates the
    course overview's ``modified``) changes, or the next release. A check that fails is logged as a warning and returns
    False, so the dashboard still loads.
    """
    if not _lms_apis_available():
        return False
    try:
        course_key = CourseKey.from_string(course_run_id)
        course_grade = CourseGradeFactory().read(user, course_key=course_key)
        # with no stored grade the user has attempted nothing
        if not course_grade.attempted or course_grade.passed:
            return False
        cache_key = get_cache_key(
            resource='failed_course_run', user_id=user.id, course_run_id=course_run_id,
            grade_updated=course_grade.last_updated, course_modified=course_modified,
        )
        cached_response = TieredCache.get_cached_response(cache_key)
        if cached_response.is_found:
            return cached_response.value
        has_failed, cache_timeout = _check_graded_subsections(user, course_key)
        TieredCache.set_all_tiers(cache_key, has_failed, cache_timeout)
        return has_failed
    except Exception:  # pylint: disable=broad-except
        LOGGER.warning('Could not read the course grade of user %s in %s', user.id, course_run_id, exc_info=True)
        return False


def _lms_apis_available():
    """
    Return whether the LMS functions ``has_failed_course_run`` needs were imported: outside the LMS they are not.
    """
    return all(
        api is not None
        for api in (CourseGradeFactory, get_course_blocks, get_course_in_cache, StartDateTransformer, adjust_start_date)
    )


def _check_graded_subsections(user, course_key):
    """
    Return whether the user has attempted every graded subsection, with no content left to release, and for how long.

    A course structure that cannot be loaded is logged as a warning and answered False for an hour.
    """
    try:
        collected_blocks = get_course_in_cache(course_key)
        course_blocks = get_course_blocks(
            user, collected_blocks.root_block_usage_key,
            collected_block_structure=collected_blocks, include_has_scheduled_content=True,
        )
        # unreleased content is left out of the learner's course blocks, so it would not count as unattempted
        if course_blocks.get_xblock_field(course_blocks.root_block_usage_key, 'has_scheduled_content'):
            return False, _seconds_until_next_release(user, course_key, collected_blocks)
        course_grade = CourseGradeFactory().read(user, course_structure=course_blocks)
        attempted = [
            grade.attempted_graded
            for grades in course_grade.graded_subsections_by_format().values() for grade in grades.values()
        ]
        return bool(attempted) and all(attempted), FAILED_COURSE_RUN_CACHE_TIMEOUT
    except Exception:  # pylint: disable=broad-except
        # an old run's content can be gone from the modulestore
        LOGGER.warning('Could not check the graded subsections of user %s in %s', user.id, course_key, exc_info=True)
        return False, FAILED_COURSE_RUN_ERROR_CACHE_TIMEOUT


def _seconds_until_next_release(user, course_key, blocks):
    """
    Return the seconds until the next of the collected ``blocks`` is released to the user, at most a day.
    """
    now = datetime.now(utc)
    # the start date the LMS enforces on a block: merged from its ancestors, and earlier for a beta tester
    start_dates = (
        adjust_start_date(
            user, blocks.get_xblock_field(key, 'days_early_for_beta'),
            blocks.get_transformer_block_field(key, StartDateTransformer, StartDateTransformer.MERGED_START_DATE),
            course_key,
        )
        for key in blocks
    )
    # one second past the release, so the answer is not refreshed just before it
    seconds_to_releases = [int((start - now).total_seconds()) + 1 for start in start_dates if start and start > now]
    return min(seconds_to_releases + [FAILED_COURSE_RUN_CACHE_TIMEOUT])


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
