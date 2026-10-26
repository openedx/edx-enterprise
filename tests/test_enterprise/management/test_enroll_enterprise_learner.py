"""
Tests for the ``enroll_enterprise_learner`` management command.
"""

from unittest.mock import MagicMock, patch

import ddt
import pytest

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from consent.models import DataSharingConsent
from enterprise.devstack_api import ensure_enterprise_groups, link_user_to_enterprise
from enterprise.models import EnterpriseCourseEnrollment
from test_utils.factories import EnterpriseCustomerFactory, UserFactory


@ddt.ddt
@pytest.mark.django_db
class TestEnrollEnterpriseLearner(TestCase):
    """Tests for the enroll_enterprise_learner management command."""

    command = 'enroll_enterprise_learner'
    course_id = 'course-v1:edX+DemoX+Demo_Course'

    def setUp(self):
        ensure_enterprise_groups()
        self.enterprise = EnterpriseCustomerFactory(name='Test Enterprise')
        self.user = UserFactory(username='test_learner')
        link_user_to_enterprise(self.user, self.enterprise)
        super().setUp()

    def _mock_course_enrollment(self):
        """Return a mock CourseEnrollment class whose ``get_or_create`` yields an active enrollment."""
        mock_enrollment = MagicMock()
        mock_enrollment.is_active = True
        mock_cls = MagicMock()
        mock_cls.objects.get_or_create.return_value = (mock_enrollment, True)
        return mock_cls

    def test_creates_enterprise_course_enrollment(self):
        """Creates an EnterpriseCourseEnrollment for the user/course/customer triple."""
        mock_cls = self._mock_course_enrollment()
        with patch('enterprise.devstack_api.CourseEnrollment', mock_cls):
            call_command(
                self.command,
                '--username', 'test_learner',
                '--course-id', self.course_id,
                '--enterprise-name', 'Test Enterprise',
            )
        assert EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user__user_id=self.user.pk,
            course_id=self.course_id,
        ).exists()

    @ddt.data(
        {'extra_args': ['--grant-dsc'], 'expected_granted': True},
        {'extra_args': [], 'expected_granted': False},
    )
    @ddt.unpack
    def test_dsc_granted_flag(self, extra_args, expected_granted):
        """Sets DataSharingConsent.granted based on whether ``--grant-dsc`` is passed."""
        mock_cls = self._mock_course_enrollment()
        with patch('enterprise.devstack_api.CourseEnrollment', mock_cls):
            call_command(
                self.command,
                '--username', 'test_learner',
                '--course-id', self.course_id,
                '--enterprise-name', 'Test Enterprise',
                *extra_args,
            )
        dsc = DataSharingConsent.objects.get(
            username='test_learner',
            course_id=self.course_id,
            enterprise_customer=self.enterprise,
        )
        assert dsc.granted is expected_granted

    def test_raises_command_error_for_missing_enterprise(self):
        """Raises CommandError when ``--enterprise-name`` refers to an unknown customer."""
        with pytest.raises(CommandError, match='does not exist'):
            call_command(
                self.command,
                '--username', 'test_learner',
                '--course-id', self.course_id,
                '--enterprise-name', 'Nonexistent Enterprise',
            )

    def test_raises_command_error_for_missing_user(self):
        """Raises CommandError when ``--username`` refers to an unknown user."""
        with pytest.raises(CommandError, match='does not exist'):
            call_command(
                self.command,
                '--username', 'nonexistent_user',
                '--course-id', self.course_id,
                '--enterprise-name', 'Test Enterprise',
            )

    def test_raises_command_error_when_not_linked(self):
        """Raises CommandError when the user is not linked to the customer."""
        unlinked_user = UserFactory(username='unlinked_user')
        mock_cls = self._mock_course_enrollment()
        with patch('enterprise.devstack_api.CourseEnrollment', mock_cls):
            with pytest.raises(CommandError, match='not linked'):
                call_command(
                    self.command,
                    '--username', unlinked_user.username,
                    '--course-id', self.course_id,
                    '--enterprise-name', 'Test Enterprise',
                )

    def test_raises_command_error_for_invalid_course_id(self):
        """Raises CommandError when ``--course-id`` cannot be parsed as a course key."""
        with pytest.raises(CommandError, match='Invalid course key'):
            call_command(
                self.command,
                '--username', 'test_learner',
                '--course-id', 'not-a-valid-key',
                '--enterprise-name', 'Test Enterprise',
            )
