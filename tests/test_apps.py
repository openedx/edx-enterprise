"""
Tests for the `edx-enterprise` models module.
"""

import sys
import types
import unittest
from unittest import mock

from openedx_events.learning.signals import COURSE_ENROLLMENT_CHANGED, COURSE_UNENROLLMENT_COMPLETED
from pytest import mark

from django.contrib import auth
from django.db.models.signals import post_save, pre_migrate
from django.dispatch import Signal
from django.test import override_settings

import enterprise
import integrated_channels
from enterprise import signals as enterprise_signals
from enterprise.constants import (
    COURSE_ASSESSMENT_GRADE_CHANGED_DISPATCH_UID,
    COURSE_GRADE_NOW_PASSED_DISPATCH_UID,
    UNENROLL_DONE_DISPATCH_UID,
    USER_POST_SAVE_DISPATCH_UID,
)
from test_utils.factories import (
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)

User = auth.get_user_model()


def _fake_platform_signal_modules():
    """
    Build the ``sys.modules`` entries that make the openedx-platform signals importable.

    ``EnterpriseConfig.ready()`` imports three signals that only exist inside an LMS install,
    so standing them up as real ``Signal`` instances is the only way to exercise the code that
    connects them from this repo.
    """
    modules = {}
    for dotted_path in (
        'common',
        'common.djangoapps',
        'common.djangoapps.student',
        'openedx',
        'openedx.core',
        'openedx.core.djangoapps',
        'openedx.core.djangoapps.signals',
    ):
        modules[dotted_path] = types.ModuleType(dotted_path)

    student_signals = types.ModuleType('common.djangoapps.student.signals')
    student_signals.UNENROLL_DONE = Signal()
    modules['common.djangoapps.student.signals'] = student_signals

    platform_signals = types.ModuleType('openedx.core.djangoapps.signals.signals')
    platform_signals.COURSE_ASSESSMENT_GRADE_CHANGED = Signal()
    platform_signals.COURSE_GRADE_NOW_PASSED = Signal()
    modules['openedx.core.djangoapps.signals.signals'] = platform_signals

    return modules


class FakeCourseEnrollment:
    """
    Stand-in for openedx-platform's ``CourseEnrollment`` model, used only as a signal sender.
    """


def _fake_platform_enrollment_and_retirement_modules():
    """
    Build the ``sys.modules`` entries for openedx-platform's ``CourseEnrollment`` and retirement signal.
    """
    modules = {}
    for dotted_path in (
        'common',
        'common.djangoapps',
        'common.djangoapps.student',
        'openedx',
        'openedx.core',
        'openedx.core.djangoapps',
        'openedx.core.djangoapps.user_api',
        'openedx.core.djangoapps.user_api.accounts',
    ):
        modules[dotted_path] = types.ModuleType(dotted_path)

    student_models = types.ModuleType('common.djangoapps.student.models')
    student_models.CourseEnrollment = FakeCourseEnrollment
    modules['common.djangoapps.student.models'] = student_models

    retirement_signals = types.ModuleType('openedx.core.djangoapps.user_api.accounts.signals')
    retirement_signals.USER_RETIRE_LMS_CRITICAL = Signal()
    modules['openedx.core.djangoapps.user_api.accounts.signals'] = retirement_signals

    return modules


@mark.django_db
class TestEnterpriseConfig(unittest.TestCase):
    """
    Test edx-enterprise app config.
    """

    def setUp(self):
        """
        Set up test environment.
        """
        super().setUp()
        self.post_save_mock = mock.Mock()
        patcher = mock.patch('enterprise.signals.handle_user_post_save', self.post_save_mock)
        patcher.start()
        self.app_config = enterprise.apps.EnterpriseConfig('enterprise', enterprise)
        self.addCleanup(patcher.stop)
        # ``ready()`` connects with a dispatch_uid, which Django refuses to connect twice.
        # Without this teardown the first test to call ``ready()`` would leave its own mock
        # wired up for every later test in the class.
        self.addCleanup(post_save.disconnect, sender=User, dispatch_uid=USER_POST_SAVE_DISPATCH_UID)

    def test_ready_connects_user_post_save_handler(self):
        self.app_config.ready()

        user = UserFactory()

        assert self.post_save_mock.call_count == 1
        call_args, call_kwargs = self.post_save_mock.call_args_list[0]
        assert call_args == ()
        assert call_kwargs["sender"] == User
        assert call_kwargs["instance"] == user
        assert call_kwargs["created"]

    def test_ready_does_not_fire_user_post_save_handler_for_other_models(self):
        self.app_config.ready()
        EnterpriseCustomerFactory()

        assert not self.post_save_mock.called

    def test_ready_disconnects_user_post_save_handler_for_migration(self):
        self.app_config.ready()
        pre_migrate.send(mock.Mock())

        UserFactory()

        assert not self.post_save_mock.called

    @mock.patch('enterprise.signals.clear_data_consent_share_cache')
    def test_ready_activates_data_sharing_consent_cache_signal_handlers(self, clear_cache_mock):
        """
        ``ready()`` activates the handlers that clear the data sharing consent cache.
        """
        self.app_config.ready()

        enterprise_customer_user = EnterpriseCustomerUserFactory()
        enrollment = EnterpriseCourseEnrollmentFactory(enterprise_customer_user=enterprise_customer_user)

        clear_cache_mock.assert_called_once_with(
            enterprise_customer_user.user_id,
            enrollment.course_id,
            str(enterprise_customer_user.enterprise_customer.uuid),
        )

    @override_settings(SERVICE_VARIANT='lms')
    def test_ready_connects_platform_signal_handlers(self):
        """
        ``ready()`` connects the three handlers bound to openedx-platform signals in the LMS.
        """
        fake_modules = _fake_platform_signal_modules()
        with mock.patch.dict(sys.modules, fake_modules):
            self.app_config.ready()

            unenroll_done = fake_modules['common.djangoapps.student.signals'].UNENROLL_DONE
            platform_signals = fake_modules['openedx.core.djangoapps.signals.signals']

            connected = {
                lookup_key[0]: receiver
                for signal in (
                    unenroll_done,
                    platform_signals.COURSE_ASSESSMENT_GRADE_CHANGED,
                    platform_signals.COURSE_GRADE_NOW_PASSED,
                )
                for lookup_key, receiver, *_ in signal.receivers
            }

        assert set(connected) == {
            COURSE_GRADE_NOW_PASSED_DISPATCH_UID,
            COURSE_ASSESSMENT_GRADE_CHANGED_DISPATCH_UID,
            UNENROLL_DONE_DISPATCH_UID,
        }
        assert connected[COURSE_GRADE_NOW_PASSED_DISPATCH_UID]() is (
            enterprise_signals.handle_enterprise_learner_passing_grade
        )
        assert connected[COURSE_ASSESSMENT_GRADE_CHANGED_DISPATCH_UID]() is (
            enterprise_signals.handle_enterprise_learner_subsection
        )
        assert connected[UNENROLL_DONE_DISPATCH_UID]() is enterprise_signals.refund_order_voucher

    def test_ready_connects_openedx_events_handlers(self):
        """
        ``ready()`` connects the course enrollment handlers bound to openedx-events signals.
        """
        self.app_config.ready()

        for signal, handler in (
            (COURSE_ENROLLMENT_CHANGED, enterprise_signals.course_enrollment_changed_receiver),
            (COURSE_UNENROLLMENT_COMPLETED, enterprise_signals.enterprise_unenrollment_receiver),
        ):
            assert handler in [receiver() for _, receiver, *_ in signal.receivers]

    def test_ready_connects_course_enrollment_and_retirement_handlers(self):
        """
        ``ready()`` connects the handlers bound to openedx-platform's enrollment model and retirement signal.
        """
        fake_modules = _fake_platform_enrollment_and_retirement_modules()
        with mock.patch.dict(sys.modules, fake_modules):
            self.app_config.ready()

        retirement_signal = fake_modules['openedx.core.djangoapps.user_api.accounts.signals'].USER_RETIRE_LMS_CRITICAL
        # ``disconnect()`` returns whether the receiver was connected, and also cleans up the
        # real ``post_save`` signal for later tests.
        assert post_save.disconnect(
            enterprise_signals.create_enterprise_enrollment_receiver,
            sender=FakeCourseEnrollment,
        )
        assert retirement_signal.disconnect(enterprise_signals.retire_user_from_pending_enterprise_customer_user)

    @override_settings(SERVICE_VARIANT='cms')
    def test_ready_skips_platform_signal_handlers_in_studio(self):
        """
        ``ready()`` leaves the three openedx-platform signals unconnected in Studio.
        """
        fake_modules = _fake_platform_signal_modules()
        with mock.patch.dict(sys.modules, fake_modules):
            self.app_config.ready()

            platform_signals = fake_modules['openedx.core.djangoapps.signals.signals']
            for signal in (
                fake_modules['common.djangoapps.student.signals'].UNENROLL_DONE,
                platform_signals.COURSE_ASSESSMENT_GRADE_CHANGED,
                platform_signals.COURSE_GRADE_NOW_PASSED,
            ):
                assert not signal.receivers

    @override_settings(SERVICE_VARIANT='lms')
    def test_ready_tolerates_absent_platform_signals(self):
        """
        ``ready()`` is a no-op for the platform-bound handlers when the platform is absent.
        """
        self.app_config.ready()


@mark.django_db
class TestIntegratedChannelConfig(unittest.TestCase):
    """
    Test integrated_channels.integrated_channel app config.
    """

    def setUp(self):
        """
        Set up test environment
        """
        super().setUp()
        self.app_config = integrated_channels.integrated_channel.apps.IntegratedChannelConfig(
            'integrated_channel', integrated_channels.integrated_channel
        )

    def test_name(self):
        assert self.app_config.name == 'integrated_channel'


@mark.django_db
class TestSAPSuccessFactorsConfig(unittest.TestCase):
    """
    Test integrated_channels.sap_success_factors app config.
    """

    def setUp(self):
        """
        Set up test environment
        """
        super().setUp()
        self.app_config = integrated_channels.sap_success_factors.apps.SAPSuccessFactorsConfig(
            'sap_success_factors', integrated_channels.sap_success_factors
        )

    def test_name(self):
        assert self.app_config.name == 'sap_success_factors'


@mark.django_db
class TestDegreedConfig(unittest.TestCase):
    """
    Test integrated_channels.degreed app config.
    """

    def setUp(self):
        """
        Set up test environment
        """
        super().setUp()
        self.app_config = integrated_channels.degreed.apps.DegreedConfig(
            'degreed', integrated_channels.degreed
        )

    def test_name(self):
        assert self.app_config.name == 'degreed'


@mark.django_db
class TestCanvasConfig(unittest.TestCase):
    """
    Test integrated_channels.canvas app config.
    """

    def setUp(self):
        """
        Set up test environment
        """
        super().setUp()
        self.app_config = integrated_channels.canvas.apps.CanvasConfig(
            'canvas', integrated_channels.canvas
        )

    def test_name(self):
        assert self.app_config.name == 'canvas'


@mark.django_db
class TestBlackboardConfig(unittest.TestCase):
    """
    Test integrated_channels.blackboard app config.
    """

    def setUp(self):
        """
        Set up test environment
        """
        super().setUp()
        self.app_config = integrated_channels.blackboard.apps.BlackboardConfig(
            'blackboard', integrated_channels.blackboard
        )

    def test_name(self):
        assert self.app_config.name == 'blackboard'


@mark.django_db
class TestXAPIConfig(unittest.TestCase):
    """
    Test integrated_channels.xapi app config.
    """

    def setUp(self):
        """
        Set up test environment
        """
        super().setUp()
        self.app_config = integrated_channels.xapi.apps.XAPIConfig(
            'xapi', integrated_channels.xapi
        )

    def test_name(self):
        assert self.app_config.name == 'xapi'


@mark.django_db
class TestMoodleConfig(unittest.TestCase):
    """
    Test integrated_channels.moodle app config.
    """

    def setUp(self):
        """
        Set up test environment
        """
        super().setUp()
        self.app_config = integrated_channels.moodle.apps.MoodleConfig(
            'moodle', integrated_channels.moodle
        )

    def test_name(self):
        assert self.app_config.name == 'moodle'
