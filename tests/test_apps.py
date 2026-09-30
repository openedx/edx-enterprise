"""
Tests for the `edx-enterprise` models module.
"""

import sys
import types
import unittest
from unittest import mock

from pytest import mark

from django.contrib import auth
from django.db.models.signals import post_save, pre_migrate
from django.dispatch import Signal

import enterprise
import integrated_channels
from enterprise.constants import (
    COURSE_ASSESSMENT_GRADE_CHANGED_DISPATCH_UID,
    COURSE_GRADE_NOW_PASSED_DISPATCH_UID,
    UNENROLL_DONE_DISPATCH_UID,
    USER_POST_SAVE_DISPATCH_UID,
)
from enterprise.platform_support import signals as platform_support_signals
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

    ``EnterpriseConfig._connect_platform_support_signals()`` imports three signals that
    only exist inside an LMS install, so standing them up as real ``Signal`` instances is
    the only way to exercise the connecting half of that method from this repo.
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

    @mock.patch('enterprise.platform_support.signals.clear_data_consent_share_cache')
    def test_ready_activates_platform_support_model_signal_handlers(self, clear_cache_mock):
        """
        ``ready()`` activates the handlers bound to this app's own model signals.

        These replace what openedx-platform's dropped ``EnterpriseSupportConfig.ready()``
        used to wire up by importing ``enterprise_support.signals``.
        """
        self.app_config.ready()

        enterprise_customer_user = EnterpriseCustomerUserFactory()
        enrollment = EnterpriseCourseEnrollmentFactory(enterprise_customer_user=enterprise_customer_user)

        clear_cache_mock.assert_called_once_with(
            enterprise_customer_user.user_id,
            enrollment.course_id,
            str(enterprise_customer_user.enterprise_customer.uuid),
        )

    def test_ready_connects_platform_support_platform_signal_handlers(self):
        """
        ``ready()`` connects the three handlers bound to openedx-platform signals.
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
            platform_support_signals.handle_enterprise_learner_passing_grade
        )
        assert connected[COURSE_ASSESSMENT_GRADE_CHANGED_DISPATCH_UID]() is (
            platform_support_signals.handle_enterprise_learner_subsection
        )
        assert connected[UNENROLL_DONE_DISPATCH_UID]() is platform_support_signals.refund_order_voucher

    def test_ready_tolerates_absent_platform_signals(self):
        """
        ``ready()`` is a no-op for the platform-bound handlers when the platform is absent.
        """
        self.app_config._connect_platform_support_signals()  # pylint: disable=protected-access


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
