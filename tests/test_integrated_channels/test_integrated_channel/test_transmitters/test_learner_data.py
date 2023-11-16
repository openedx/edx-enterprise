"""
Tests for the base learner data transmitter.
"""

import unittest
from unittest import mock
from unittest.mock import MagicMock, Mock

import ddt
from pytest import mark

from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.integrated_channel.tasks import transmit_single_learner_data
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter
from test_utils import factories


@mark.django_db
@ddt.ddt
class TestLearnerDataTransmitter(unittest.TestCase):
    """
    Tests for the class ``LearnerDataTransmitter``.
    """

    def setUp(self):
        super().setUp()

        enterprise_customer = factories.EnterpriseCustomerFactory(name='Starfleet Academy')

        # We need some non-abstract configuration for these things to work,
        # so it's okay for it to be any arbitrary channel. We randomly choose SAPSF.
        self.enterprise_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=enterprise_customer,
            key="client_id",
            sapsf_base_url="http://test.successfactors.com/",
            sapsf_company_id="company_id",
            sapsf_user_id="user_id",
            secret="client_secret",
        )

        self.learner_transmitter = LearnerTransmitter(self.enterprise_config)

    def test_default_channel_settings(self):
        """
        If you add any settings to the ChannelSettingsMixin, add a test here for the common default value
        """
        assert LearnerTransmitter(self.enterprise_config).INCLUDE_GRADE_FOR_COMPLETION_AUDIT_CHECK is True

    def test_transmit_single_learner_data_signal_kwargs(self):
        """
        transmit_single_learner_data is called with kwargs as a shared task from OpenEdx,
        so test that interface hasn't changed.
        """
        edx_platform_api_signal_kwargs = {
            'username': "fake_username",
            'course_run_id': "TEST_COURSE_RUN_KEY"
        }
        # If you change the arg names to transmit_single_learner_data
        # this test will now fail with a TypeError:
        try:
            transmit_single_learner_data(**edx_platform_api_signal_kwargs)
        except TypeError:
            assert False  # if we see a Type error, the test should fail because we failed with bad keyword parameters
        except Exception:
            pass  # otherwise it's because we set the test up with no data.

    @mock.patch("integrated_channels.integrated_channel.models.LearnerDataTransmissionAudit")
    @mock.patch("integrated_channels.utils.is_already_transmitted")
    def test_transmit_create_success(self, already_transmitted_mock, learner_data_transmission_audit_mock):
        """
        Test successful creation assessment level learner data during transmission.
        """
        LearnerExporterMock = LearnerExporter

        # Serialized payload is used in the client's assessment reporting as well as the transmission audit check.
        # Both of these are mocked out, so mock out the necessary attributes
        learner_data_transmission_audit_mock.serialize = Mock(return_value='serialized data')
        learner_data_transmission_audit_mock.grade = '1.0'
        learner_data_transmission_audit_mock.subsection_id = 'subsection_id'
        learner_data_transmission_audit_mock.user_id = 1
        learner_data_transmission_audit_mock.enterprise_course_enrollment_id = 1
        LearnerExporterMock.bulk_assessment_level_export = Mock(return_value=[learner_data_transmission_audit_mock])

        already_transmitted_mock.return_value = False

        self.learner_transmitter.client.create_assessment_reporting = Mock(return_value=(200, 'success'))

        self.learner_transmitter.assessment_level_transmit(
            LearnerExporterMock,
            remote_user_id='user_id'
        )

        assert learner_data_transmission_audit_mock.save.called
        assert learner_data_transmission_audit_mock.error_message == ''
        assert learner_data_transmission_audit_mock.status == '200'

    @mock.patch('integrated_channels.integrated_channel.transmitters.'
                'learner_data.LearnerExporterUtility.lms_user_id_for_ent_course_enrollment_id')
    @mock.patch('integrated_channels.integrated_channel.transmitters.learner_data.is_already_transmitted')
    def test_raises_client_error_on_status_code(self, is_already_tx, mock_lms_id):
        mock_lms_id.return_value = 'abc'
        is_already_tx.return_value = False
        self.learner_transmitter.client.create_course_completion = Mock(return_value=(401, 'fail'))
        exporter = MagicMock()
        records = MagicMock()
        records.course_completed = True
        records.serialize = Mock(return_value='serialized data')
        exporter.export = MagicMock(return_value=[records])
        self.learner_transmitter.process_transmission_error = Mock()
        self.learner_transmitter.transmit(
            exporter,
            remote_user_id='user_id'
        )
        self.learner_transmitter.process_transmission_error.assert_called_once()

    def test_learner_data_transmission_feature_flag(self):
        """
        Test that a customer's configuration can disable learner data transmissions
        """
        # Set feature flag to true
        self.enterprise_config.disable_learner_data_transmissions = True

        self.learner_transmitter.client.create_assessment_reporting = Mock()
        self.learner_transmitter.client.create_course_completion = Mock()

        LearnerExporterMock = LearnerExporter
        self.learner_transmitter.single_learner_assessment_grade_transmit(
            LearnerExporterMock,
            remote_user_id='user_id'
        )
        # with disable_learner_data_transmissions = True we shouldn't be able to call this method
        assert not self.learner_transmitter.client.create_assessment_reporting.called

        self.learner_transmitter.assessment_level_transmit(
            LearnerExporterMock,
            remote_user_id='user_id'
        )
        # with disable_learner_data_transmissions = True we shouldn't be able to call this method
        assert not self.learner_transmitter.client.create_assessment_reporting.called

        self.learner_transmitter.transmit(
            LearnerExporterMock,
            remote_user_id='user_id'
        )
        # with disable_learner_data_transmissions = True we shouldn't be able to call this method
        assert not self.learner_transmitter.client.create_course_completion.called

    @mock.patch("integrated_channels.integrated_channel.models.LearnerDataTransmissionAudit")
    @mock.patch("integrated_channels.utils.is_already_transmitted")
    def test_learner_data_transmission_dry_run_mode(self, already_transmitted_mock, learner_data_transmission_audit_mock):
        """
        Test that a customer's configuration can run in dry run mode
        """
        # Set feature flag to true
        self.enterprise_config.dry_run_mode_enabled = True

        self.learner_transmitter.client.create_assessment_reporting = Mock()
        self.learner_transmitter.client.create_course_completion = Mock()

        LearnerExporterMock = LearnerExporter

        # Serialized payload is used in the client's assessment reporting as well as the transmission audit check.
        # Both of these are mocked out, so mock out the necessary attributes
        learner_data_transmission_audit_mock.serialize = Mock(return_value='serialized data')
        learner_data_transmission_audit_mock.grade = '1.0'
        learner_data_transmission_audit_mock.subsection_id = 'subsection_id'
        learner_data_transmission_audit_mock.user_id = 1
        learner_data_transmission_audit_mock.enterprise_course_enrollment_id = 1
        LearnerExporterMock.export = Mock(return_value=[learner_data_transmission_audit_mock])
        LearnerExporterMock.single_assessment_level_export = Mock(return_value=[learner_data_transmission_audit_mock])
        LearnerExporterMock.bulk_assessment_level_export = Mock(return_value=[learner_data_transmission_audit_mock])

        already_transmitted_mock.return_value = False

        self.learner_transmitter.process_transmission_error = Mock()
        self.learner_transmitter.transmit(
            LearnerExporterMock,
            remote_user_id='user_id'
        )
        # with dry_run_mode_enabled = True we shouldn't be able to call this method
        assert not self.learner_transmitter.client.create_course_completion.called

        self.learner_transmitter.single_learner_assessment_grade_transmit(
            LearnerExporterMock,
            remote_user_id='user_id'
        )
        # with dry_run_mode_enabled = True we shouldn't be able to call this method
        assert not self.learner_transmitter.client.create_assessment_reporting.called

        self.learner_transmitter.assessment_level_transmit(
            LearnerExporterMock,
            remote_user_id='user_id'
        )
        # with dry_run_mode_enabled = True we shouldn't be able to call this method
        assert not self.learner_transmitter.client.create_assessment_reporting.called
