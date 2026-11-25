"""
Tests for the utils of the enterprise_learner_portal app.
"""

from datetime import datetime, timedelta
from unittest import mock

import ddt
from edx_django_utils.cache import RequestCache, TieredCache
from edx_toggles.toggles.testutils import override_waffle_flag
from freezegun import freeze_time
from pytest import mark
from pytz import utc

from django.test import TestCase

from enterprise.toggles import SHOW_FAILED_SELF_PACED_RUNS_AS_COMPLETED
from enterprise_learner_portal.utils import (
    FAILED_COURSE_RUN_ERROR_CACHE_TIMEOUT,
    CourseRunProgressStatuses,
    get_course_run_status,
    get_failed_course_run_check,
    has_failed_course_run,
)
from test_utils import factories


@mark.django_db
@ddt.ddt
class TestUtils(TestCase):
    """
    Tests for enterprise_learner_portal utils.
    """

    @ddt.data(
        {
            'course_overview': {'has_started': False, 'has_ended': False},
            'certificate_info': {'is_passing': False},
            'saved_for_later': False,
            'expected_status': CourseRunProgressStatuses.UPCOMING,
        },
        {
            'course_overview': {'has_started': True, 'has_ended': False},
            'certificate_info': {'is_passing': False},
            'saved_for_later': False,
            'expected_status': CourseRunProgressStatuses.IN_PROGRESS,
        },
        {
            'course_overview': {'has_started': True, 'has_ended': False},
            'certificate_info': {'is_passing': True},
            'saved_for_later': False,
            'expected_status': CourseRunProgressStatuses.COMPLETED,
        },
        {
            'course_overview': {'has_started': True, 'has_ended': True},
            'certificate_info': {'is_passing': False},
            'saved_for_later': False,
            'expected_status': CourseRunProgressStatuses.COMPLETED,
        },
        {
            'course_overview': {'has_started': True, 'has_ended': True},
            'certificate_info': {'is_passing': True},
            'saved_for_later': False,
            'expected_status': CourseRunProgressStatuses.COMPLETED,
        },
        {
            'course_overview': {'has_started': True, 'has_ended': False},
            'certificate_info': {'is_passing': False},
            'saved_for_later': True,
            'expected_status': CourseRunProgressStatuses.SAVED_FOR_LATER,
        },
    )
    @ddt.unpack
    def test_get_course_run_status(
            self,
            course_overview,
            certificate_info,
            saved_for_later,
            expected_status,
    ):
        """
        Assert get_course_run_status returns the proper results based on input parameters
        """
        enterprise_enrollment = factories.EnterpriseCourseEnrollmentFactory.create(saved_for_later=saved_for_later)
        actual_status = get_course_run_status(
            course_overview,
            certificate_info,
            enterprise_enrollment
        )
        assert actual_status == expected_status

    @ddt.data(
        # has_started, has_ended, is_passing, saved_for_later, is_failed, expected_status, expect_check_called
        # an open run the learner has failed reads completed, as it does once the run ends
        (True, False, False, False, True, CourseRunProgressStatuses.COMPLETED, True),
        (True, False, False, False, False, CourseRunProgressStatuses.IN_PROGRESS, True),
        # the check reads grades, so it is skipped whenever the status does not depend on it
        (True, True, False, False, False, CourseRunProgressStatuses.COMPLETED, False),
        (True, False, True, False, False, CourseRunProgressStatuses.COMPLETED, False),
        (False, False, False, False, True, CourseRunProgressStatuses.UPCOMING, False),
        (True, False, False, True, True, CourseRunProgressStatuses.SAVED_FOR_LATER, False),
    )
    @ddt.unpack
    def test_get_course_run_status_with_failed_run_check(
            self, has_started, has_ended, is_passing, saved_for_later, is_failed, expected_status, expect_check_called,
    ):
        """
        get_course_run_status reads an open run the learner has failed as completed, and only calls
        is_failed_run for an open run without a passing certificate.
        """
        enterprise_enrollment = factories.EnterpriseCourseEnrollmentFactory.create(saved_for_later=saved_for_later)
        is_failed_run = mock.Mock(return_value=is_failed)

        actual_status = get_course_run_status(
            {'has_started': has_started, 'has_ended': has_ended},
            {'is_passing': is_passing},
            enterprise_enrollment,
            is_failed_run=is_failed_run,
        )

        assert actual_status == expected_status
        assert is_failed_run.called is expect_check_called


@ddt.ddt
class TestHasFailedCourseRun(TestCase):
    """Tests for get_failed_course_run_check and has_failed_course_run."""

    course_run_id = 'course-v1:edX+DemoX+Demo_Course'

    def setUp(self):
        super().setUp()
        self.user = mock.Mock(id=7)
        TieredCache.dangerous_clear_all_tiers()
        self.mock_factory = self._patch('CourseGradeFactory')
        self.collected_blocks = self._patch('get_course_in_cache').return_value
        self.mock_get_course_blocks = self._patch('get_course_blocks')
        self.mock_get_course_blocks.return_value.get_xblock_field.return_value = False
        self.mock_start_date_transformer = self._patch('StartDateTransformer')
        self.mock_adjust_start_date = self._patch('adjust_start_date')

    def _patch(self, name, **kwargs):
        """Patch ``name`` in enterprise_learner_portal.utils for the test."""
        patcher = mock.patch(f'enterprise_learner_portal.utils.{name}', **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    @staticmethod
    def _problem_score(problem):
        """
        A problem score for ``problem``: True (submitted) or False (not submitted) for a graded problem worth a point,
        or 'ungraded' or 'no points' for one left unsubmitted that the grade does not count.
        """
        return mock.Mock(
            graded=problem != 'ungraded',
            possible=0.0 if problem == 'no points' else 1.0,
            first_attempted=datetime.now(utc) if problem is True else None,
        )

    def _set_course_grade(self, subsections=((True,),), attempted=True, passed=False):
        """
        Make the mocked CourseGradeFactory read a grade updated now, below passing by default, whose graded subsections
        hold the problems in ``subsections`` (one tuple of ``_problem_score`` values per subsection).
        """
        course_grade = self.mock_factory.return_value.read.return_value
        course_grade.attempted, course_grade.passed = attempted, passed
        course_grade.last_updated = datetime.now(utc)
        course_grade.graded_subsections_by_format.return_value = {
            'Homework': {
                index: mock.Mock(
                    # the LMS counts a subsection as attempted once one of its problems is submitted
                    attempted_graded=any(problem is True for problem in problems),
                    problem_scores={
                        position: self._problem_score(problem) for position, problem in enumerate(problems)
                    },
                )
                for index, problems in enumerate(subsections)
            }
        }
        return course_grade

    @ddt.data(
        ('self', 'verified', True, True),
        # with the flag off the dashboard works as before
        ('self', 'verified', False, False),
        # an instructor-paced run moves to completed when it ends
        ('instructor', 'verified', True, False),
        # the LMS never shows an audit learner as not passing
        ('self', 'audit', True, False),
        # no course enrollment, so no mode
        ('self', None, True, False),
    )
    @ddt.unpack
    def test_failed_course_run_check(self, pacing, mode, flag_active, expect_check):
        """
        Only a self-paced run in a mode that earns a certificate can be failed before it ends, and only while the
        waffle flag is on.
        """
        mock_course_mode = self._patch('CourseMode')
        mock_course_mode.is_eligible_for_certificate.side_effect = lambda mode_slug: mode_slug != 'audit'
        mock_has_failed_course_run = self._patch('has_failed_course_run')

        course_overview = {'pacing': pacing, 'modified': '2026-11-18T10:00:00Z'}
        with override_waffle_flag(SHOW_FAILED_SELF_PACED_RUNS_AS_COMPLETED, active=flag_active):
            check = get_failed_course_run_check(self.user, self.course_run_id, course_overview, mode)

        if expect_check:
            assert check() is mock_has_failed_course_run.return_value
            mock_has_failed_course_run.assert_called_once_with(self.user, self.course_run_id, '2026-11-18T10:00:00Z')
        else:
            assert check is None

    @ddt.data(
        # every graded problem submitted and below passing: failed straight away
        {'subsections': ((True,), (True, True)), 'expected': True},
        # a graded subsection attempted with a graded problem left: the learner can still raise the grade
        {'subsections': ((True,), (True, False)), 'expected': False},
        # a graded subsection never attempted, or nothing graded to submit
        {'subsections': ((True,), (False, False)), 'expected': False},
        {'subsections': (), 'expected': False},
        {'subsections': (('ungraded', 'no points'),), 'expected': False},
        # a problem the grade does not count (ungraded, or worth no points) may be left
        {'subsections': ((True, 'ungraded', 'no points'),), 'expected': True},
        # content still to be released: the LMS shows the run in progress
        {'has_scheduled_content': True, 'expected': False},
        # a course with no pass mark computes passed as None, which is not a pass
        {'passed': None, 'expected': True},
    )
    @ddt.unpack
    def test_graded_subsections(self, expected, has_scheduled_content=False, **grade_values):
        """
        A learner below passing has failed once they have submitted every graded problem and no content is left to
        release.
        """
        self._set_course_grade(**grade_values)
        course_blocks = self.mock_get_course_blocks.return_value
        course_blocks.get_xblock_field.return_value = has_scheduled_content

        assert has_failed_course_run(self.user, self.course_run_id) is expected

        stored_grade_read, *structure_reads = self.mock_factory.return_value.read.call_args_list
        assert str(stored_grade_read.kwargs['course_key']) == self.course_run_id
        self.mock_get_course_blocks.assert_called_once_with(
            self.user, self.collected_blocks.root_block_usage_key,
            collected_block_structure=self.collected_blocks, include_has_scheduled_content=True,
        )
        course_blocks.get_xblock_field.assert_called_once_with(
            course_blocks.root_block_usage_key, 'has_scheduled_content'
        )
        structure_read = mock.call(self.user, course_structure=course_blocks)
        assert structure_reads == ([] if has_scheduled_content else [structure_read])

    def test_graded_subsection_must_be_attempted(self):
        """
        A graded subsection the LMS does not count as attempted is not completed, even with its problems scored.
        """
        course_grade = self._set_course_grade(subsections=((True,), (True,)))
        course_grade.graded_subsections_by_format.return_value['Homework'][1].attempted_graded = False

        assert has_failed_course_run(self.user, self.course_run_id) is False

    @ddt.data(
        # no stored grade: nothing attempted
        {'attempted': False},
        {'passed': True},
    )
    def test_not_failed_without_loading_the_course(self, grade_values):
        """
        A learner with no stored grade or a passing grade has not failed, and the course structure is not
        loaded to find that out.
        """
        self._set_course_grade(**grade_values)

        assert has_failed_course_run(self.user, self.course_run_id) is False
        self.mock_get_course_blocks.assert_not_called()

    def test_cached_until_the_grade_or_course_changes(self):
        """
        The course structure is loaded once for a stored grade and course version, and again once either changes.
        """
        course_grade = self._set_course_grade()

        assert has_failed_course_run(self.user, self.course_run_id, 'published-1') is True
        assert has_failed_course_run(self.user, self.course_run_id, 'published-1') is True
        assert self.mock_get_course_blocks.call_count == 1

        course_grade.last_updated -= timedelta(days=1)
        assert has_failed_course_run(self.user, self.course_run_id, 'published-1') is True
        assert self.mock_get_course_blocks.call_count == 2

        # a graded subsection the learner has not attempted is published, which leaves their stored grade unchanged
        course_grade.graded_subsections_by_format.return_value['Homework'][1] = mock.Mock(
            attempted_graded=False, problem_scores={0: self._problem_score(False)}
        )
        assert has_failed_course_run(self.user, self.course_run_id, 'published-2') is False
        assert self.mock_get_course_blocks.call_count == 3

    def test_scheduled_content_cached_until_released(self):
        """
        While content is scheduled the run is in progress, and that answer expires once the learner can see the next
        content, which a beta tester sees early.
        """
        self._set_course_grade()
        course_blocks = self.mock_get_course_blocks.return_value
        course_blocks.get_xblock_field.return_value = True
        now = datetime.now(utc)
        release = now + timedelta(hours=20)
        # already released, released next, released later, and a block with no start date
        start_dates = {'a': now - timedelta(days=1), 'b': release, 'c': release + timedelta(days=2), 'd': None}
        self.collected_blocks.__iter__.return_value = list(start_dates)
        self.collected_blocks.get_transformer_block_field.side_effect = lambda block_key, *_: start_dates[block_key]
        # the learner is a beta tester, who sees content half a day early
        self.collected_blocks.get_xblock_field.return_value = 0.5
        self.mock_adjust_start_date.side_effect = lambda user, days_early, start, key: (
            start - timedelta(days=days_early) if start else start
        )
        beta_release = release - timedelta(hours=12)

        def has_failed_at(moment):
            RequestCache.clear_all_namespaces()  # a new dashboard request
            with freeze_time(moment):
                return has_failed_course_run(self.user, self.course_run_id)

        assert has_failed_at(now) is False
        self.collected_blocks.get_transformer_block_field.assert_any_call(
            'b', self.mock_start_date_transformer, self.mock_start_date_transformer.MERGED_START_DATE
        )
        self.collected_blocks.get_xblock_field.assert_any_call('b', 'days_early_for_beta')
        user, _, _, course_key = self.mock_adjust_start_date.call_args.args
        assert user is self.user and str(course_key) == self.course_run_id
        # the last scheduled content is released to the learner
        course_blocks.get_xblock_field.return_value = False
        assert has_failed_at(beta_release - timedelta(minutes=1)) is False
        assert self.mock_get_course_blocks.call_count == 1
        assert has_failed_at(beta_release + timedelta(minutes=1)) is True
        assert self.mock_get_course_blocks.call_count == 2

    @ddt.data('CourseGradeFactory', 'get_course_blocks', 'get_course_in_cache', 'StartDateTransformer',
              'adjust_start_date')
    def test_not_connected_to_openedx(self, lms_api):
        """
        Outside the LMS, or when any LMS function the check needs cannot be imported, no run has failed.
        """
        self._set_course_grade()
        self._patch(lms_api, new=None)

        assert has_failed_course_run(self.user, self.course_run_id) is False
        self.mock_get_course_blocks.assert_not_called()

    def test_grade_read_error(self):
        """
        A grade that cannot be read is logged as a warning and leaves the run in progress, so the dashboard still
        loads. The read is one query, so the next dashboard load reads it again.
        """
        self.mock_factory.return_value.read.side_effect = Exception('the database is unavailable')
        mock_logger = self._patch('LOGGER')

        assert has_failed_course_run(self.user, self.course_run_id) is False
        mock_logger.warning.assert_called_once_with(
            'Could not read the course grade of user %s in %s', self.user.id, self.course_run_id, exc_info=True,
        )
        mock_logger.exception.assert_not_called()

    def test_course_structure_error_cached(self):
        """
        A course structure that cannot be loaded is logged as a warning and leaves the run in progress. That answer is
        cached for an hour, so dashboard loads in the meantime neither load the course nor log the error again.
        """
        self._set_course_grade()
        self.mock_get_course_blocks.side_effect = Exception('course structure is gone')
        mock_logger = self._patch('LOGGER')
        now = datetime.now(utc)

        def has_failed_at(moment):
            RequestCache.clear_all_namespaces()  # a new dashboard request
            with freeze_time(moment):
                return has_failed_course_run(self.user, self.course_run_id)

        assert has_failed_at(now) is False
        mock_logger.warning.assert_called_once()
        message, user_id, course_key = mock_logger.warning.call_args.args
        assert message == 'Could not check the graded subsections of user %s in %s'
        assert user_id == self.user.id and str(course_key) == self.course_run_id
        assert mock_logger.warning.call_args.kwargs == {'exc_info': True}

        timeout = timedelta(seconds=FAILED_COURSE_RUN_ERROR_CACHE_TIMEOUT)
        assert has_failed_at(now + timeout - timedelta(minutes=1)) is False
        assert self.mock_get_course_blocks.call_count == 1
        assert mock_logger.warning.call_count == 1

        assert has_failed_at(now + timeout + timedelta(minutes=1)) is False
        assert self.mock_get_course_blocks.call_count == 2
        assert mock_logger.warning.call_count == 2
