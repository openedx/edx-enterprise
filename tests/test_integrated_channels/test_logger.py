"""
Unit tests for integrated_channels.logger module.
"""
import json
import logging
import sys
import unittest
from unittest import mock

from testfixtures import LogCapture

from django.test import TestCase, override_settings

from integrated_channels.logger import IntegratedChannelsFormatter, get_integrated_channels_logger, log_with_context


class TestIntegratedChannelsFormatter(TestCase):
    """
    Test cases for IntegratedChannelsFormatter class.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.formatter = IntegratedChannelsFormatter()

    @override_settings(INTEGRATED_CHANNELS_JSON_LOGGING=False)
    def test_formatter_init_string_format(self):
        """Test formatter initialization with string format."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', False):
            formatter = IntegratedChannelsFormatter()
            self.assertFalse(formatter.use_json)

    @override_settings(INTEGRATED_CHANNELS_JSON_LOGGING=True)
    def test_formatter_init_json_format(self):
        """Test formatter initialization with JSON format."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', True):
            formatter = IntegratedChannelsFormatter()
            self.assertTrue(formatter.use_json)

    def test_format_string_mode(self):
        """Test formatting in string mode."""
        with mock.patch.object(self.formatter, 'use_json', False):
            # Create a mock log record
            record = logging.LogRecord(
                name='test_logger',
                level=logging.INFO,
                pathname='/test/path.py',
                lineno=123,
                msg='Test message',
                args=(),
                exc_info=None
            )

            # Mock the parent format method
            with mock.patch.object(logging.Formatter, 'format', return_value='formatted_string'):
                result = self.formatter.format(record)
                self.assertEqual(result, 'formatted_string')

    def test_format_json_mode_basic(self):
        """Test basic JSON formatting."""
        with mock.patch.object(self.formatter, 'use_json', True):
            record = logging.LogRecord(
                name='integrated_channels.test',
                level=logging.INFO,
                pathname='/test/path.py',
                lineno=123,
                msg='Test message',
                args=(),
                exc_info=None
            )
            record.module = 'test_module'
            record.funcName = 'test_function'

            result = self.formatter.format(record)

            # Parse the JSON result
            log_data = json.loads(result)

            # Verify basic fields
            self.assertEqual(log_data['level'], 'INFO')
            self.assertEqual(log_data['logger'], 'integrated_channels.test')
            self.assertEqual(log_data['message'], 'Test message')
            self.assertEqual(log_data['module'], 'test_module')
            self.assertEqual(log_data['service'], 'integrated_channels')
            self.assertIn('timestamp', log_data)

    def test_format_json_mode_with_exception(self):
        """Test JSON formatting with exception information."""
        with mock.patch.object(self.formatter, 'use_json', True):
            exc_info = None
            try:
                raise ValueError("Test exception")
            except ValueError:
                exc_info = sys.exc_info()

            record = logging.LogRecord(
                name='integrated_channels.test',
                level=logging.ERROR,
                pathname='/test/path.py',
                lineno=123,
                msg='Error occurred',
                args=(),
                exc_info=exc_info
            )
            record.module = 'test_module'
            record.funcName = 'test_function'

            result = self.formatter.format(record)
            log_data = json.loads(result)

            # Verify exception fields
            self.assertEqual(log_data['error.type'], 'ValueError')
            self.assertEqual(log_data['error.message'], 'Test exception')
            self.assertIn('error.stack', log_data)
            self.assertEqual(log_data['error.function'], 'test_function')
            self.assertEqual(log_data['error.file'], '/test/path.py')
            self.assertEqual(log_data['error.line'], 123)

    def test_format_json_mode_with_integrated_channels_context(self):
        """Test JSON formatting with integrated channels specific context."""
        with mock.patch.object(self.formatter, 'use_json', True):
            record = logging.LogRecord(
                name='integrated_channels.test',
                level=logging.INFO,
                pathname='/test/path.py',
                lineno=123,
                msg='Test message',
                args=(),
                exc_info=None
            )
            record.module = 'test_module'

            # Add integrated channels specific attributes
            record.channel_name = 'CANVAS'
            record.enterprise_customer_uuid = '123e4567-e89b-12d3-a456-426614174000'
            record.plugin_configuration_id = 456
            record.lms_user_id = 789
            record.course_or_course_run_key = 'course-v1:edX+Demo+2023'
            record.transmission_type = 'learner_data'
            record.enterprise_enrollment_id = 101112
            record.status_code = 200

            result = self.formatter.format(record)
            log_data = json.loads(result)

            # Verify integrated channels fields
            self.assertEqual(log_data['integrated_channel.code'], 'CANVAS')
            self.assertEqual(log_data['integrated_channel.customer_uuid'], '123e4567-e89b-12d3-a456-426614174000')
            self.assertEqual(log_data['integrated_channel.configuration_id'], 456)
            self.assertEqual(log_data['integrated_channel.user_id'], 789)
            self.assertEqual(log_data['integrated_channel.course_or_course_run_key'], 'course-v1:edX+Demo+2023')
            self.assertEqual(log_data['integrated_channel.transmission_type'], 'learner_data')
            self.assertEqual(log_data['integrated_channel.enrollment_id'], 101112)
            self.assertEqual(log_data['http.status_code'], 200)

    def test_format_json_mode_with_datadog_attributes(self):
        """Test JSON formatting with Datadog specific attributes."""
        with mock.patch.object(self.formatter, 'use_json', True):
            record = logging.LogRecord(
                name='integrated_channels.test',
                level=logging.INFO,
                pathname='/test/path.py',
                lineno=123,
                msg='Test message',
                args=(),
                exc_info=None
            )
            record.module = 'test_module'

            # Add Datadog specific attributes
            record.dd_trace_id = '12345'
            record.dd_span_id = '67890'
            record.dd_service = 'integrated_channels'

            result = self.formatter.format(record)
            log_data = json.loads(result)

            # Verify Datadog fields are included
            self.assertEqual(log_data['dd_trace_id'], '12345')
            self.assertEqual(log_data['dd_span_id'], '67890')
            self.assertEqual(log_data['dd_service'], 'integrated_channels')

    def test_timestamp_format(self):
        """Test that timestamp format matches Datadog expectations."""
        with mock.patch.object(self.formatter, 'use_json', True):
            # Mock datetime to get predictable timestamp
            mock_timestamp = 1693497436.252
            with mock.patch('integrated_channels.logger.datetime') as mock_datetime:
                mock_datetime.fromtimestamp.return_value.strftime.return_value = '2023-08-31 17:27:16,252000'

                record = logging.LogRecord(
                    name='test_logger',
                    level=logging.INFO,
                    pathname='/test/path.py',
                    lineno=123,
                    msg='Test message',
                    args=(),
                    exc_info=None
                )
                record.created = mock_timestamp
                record.module = 'test_module'

                result = self.formatter.format(record)
                log_data = json.loads(result)

                # Verify timestamp format (should have milliseconds, not microseconds)
                self.assertEqual(log_data['timestamp'], '2023-08-31 17:27:16,252')


class TestGetIntegratedChannelsLogger(TestCase):
    """
    Test cases for get_integrated_channels_logger function.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing loggers to avoid state pollution
        logging.Logger.manager.loggerDict.clear()

    def test_get_logger_default_name(self):
        """Test getting logger with default name."""
        logger = get_integrated_channels_logger()
        self.assertEqual(logger.name, 'integrated_channels')
        self.assertEqual(logger.level, logging.DEBUG)
        self.assertTrue(logger.propagate)

    def test_get_logger_custom_name(self):
        """Test getting logger with custom name."""
        logger = get_integrated_channels_logger('custom_logger')
        self.assertEqual(logger.name, 'custom_logger')

    @override_settings(INTEGRATED_CHANNELS_JSON_LOGGING=False)
    def test_get_logger_string_format_no_handler(self):
        """Test logger configuration when JSON logging is disabled."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', False):
            logger = get_integrated_channels_logger('test_logger')
            # Should not add custom handler when JSON logging is disabled
            self.assertEqual(len(logger.handlers), 0)
            self.assertTrue(logger.propagate)

    @override_settings(INTEGRATED_CHANNELS_JSON_LOGGING=True)
    def test_get_logger_json_format_with_handler(self):
        """Test logger configuration when JSON logging is enabled."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', True):
            logger = get_integrated_channels_logger('test_logger')
            # Should add custom handler when JSON logging is enabled
            self.assertEqual(len(logger.handlers), 1)
            handler = logger.handlers[0]
            self.assertIsInstance(handler, logging.StreamHandler)
            self.assertIsInstance(handler.formatter, IntegratedChannelsFormatter)

    def test_get_logger_avoids_duplicate_handlers(self):
        """Test that calling get_integrated_channels_logger multiple times doesn't add duplicate handlers."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', True):
            logger1 = get_integrated_channels_logger('test_logger')
            logger2 = get_integrated_channels_logger('test_logger')

            # Should be the same logger instance
            self.assertIs(logger1, logger2)
            # Should only have one handler
            self.assertEqual(len(logger1.handlers), 1)


class TestLogWithContext(TestCase):
    """
    Test cases for log_with_context function.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.mock_logger = mock.MagicMock()

    def test_log_with_context_info_level(self):
        """Test logging with INFO level."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', True):
            log_with_context(
                self.mock_logger,
                'INFO',
                'Test message',
                channel_name='CANVAS',
                enterprise_customer_uuid='test-uuid'
            )

            self.mock_logger.info.assert_called_once_with(
                'Test message',
                extra={
                    'channel_name': 'CANVAS',
                    'enterprise_customer_uuid': 'test-uuid'
                },
                exc_info=False
            )

    def test_log_with_context_error_level(self):
        """Test logging with ERROR level."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', True):
            log_with_context(
                self.mock_logger,
                'ERROR',
                'Error message',
                channel_name='BLACKBOARD',
                plugin_configuration_id=123
            )

            self.mock_logger.error.assert_called_once_with(
                'Error message',
                extra={
                    'channel_name': 'BLACKBOARD',
                    'plugin_configuration_id': 123
                },
                exc_info=False
            )

    def test_log_with_context_exception_level(self):
        """Test logging with EXCEPTION level."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', True):
            log_with_context(
                self.mock_logger,
                'EXCEPTION',
                'Exception occurred',
                channel_name='SAP',
                enterprise_customer_uuid='test-uuid'
            )

            self.mock_logger.exception.assert_called_once_with(
                'Exception occurred',
                extra={
                    'channel_name': 'SAP',
                    'enterprise_customer_uuid': 'test-uuid'
                },
                exc_info=True
            )

    def test_log_with_context_string_format(self):
        """Test logging with string format (non-JSON)."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', False):
            with mock.patch('integrated_channels.logger.generate_formatted_log') as mock_generate:
                mock_generate.return_value = 'formatted message'

                log_with_context(
                    self.mock_logger,
                    'INFO',
                    'Test message',
                    channel_name='CANVAS',
                    enterprise_customer_uuid='test-uuid',
                    lms_user_id=123,
                    course_or_course_run_key='course-key',
                    plugin_configuration_id=456
                )

                # Verify generate_formatted_log was called with correct parameters
                mock_generate.assert_called_once_with(
                    channel_name='CANVAS',
                    enterprise_customer_uuid='test-uuid',
                    lms_user_id=123,
                    course_or_course_run_key='course-key',
                    message='Test message',
                    plugin_configuration_id=456
                )

                # Verify logger was called with formatted message
                self.mock_logger.info.assert_called_once_with(
                    'formatted message',
                    exc_info=False
                )

    def test_log_with_context_with_exc_info(self):
        """Test logging with explicit exc_info parameter."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', True):
            log_with_context(
                self.mock_logger,
                'ERROR',
                'Error with exception',
                exc_info=True,
                channel_name='MOODLE'
            )

            self.mock_logger.error.assert_called_once_with(
                'Error with exception',
                extra={'channel_name': 'MOODLE'},
                exc_info=True
            )

    def test_log_with_context_case_insensitive_level(self):
        """Test that log level is case insensitive."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', True):
            # Test lowercase
            log_with_context(self.mock_logger, 'info', 'Test message')
            self.mock_logger.info.assert_called()

            self.mock_logger.reset_mock()

            # Test uppercase
            log_with_context(self.mock_logger, 'INFO', 'Test message')
            self.mock_logger.info.assert_called()

            self.mock_logger.reset_mock()

            # Test mixed case
            log_with_context(self.mock_logger, 'Info', 'Test message')
            self.mock_logger.info.assert_called()


class TestLoggerIntegration(TestCase):
    """
    Integration tests for the complete logging system.
    """

    @override_settings(INTEGRATED_CHANNELS_JSON_LOGGING=True)
    def test_end_to_end_json_logging(self):
        """Test complete JSON logging flow."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', True):
            # Get a logger
            logger = get_integrated_channels_logger('integration_test')

            # Capture logs
            with LogCapture(level=logging.INFO) as log_capture:
                # Use log_with_context
                log_with_context(
                    logger,
                    'INFO',
                    'Integration test message',
                    channel_name='CANVAS',
                    enterprise_customer_uuid='123e4567-e89b-12d3-a456-426614174000',
                    plugin_configuration_id=789
                )

                # Verify log was captured
                self.assertEqual(len(log_capture.records), 1)

                # Get the formatted message
                record = log_capture.records[0]
                formatted_message = logger.handlers[0].formatter.format(record)

                # Parse as JSON
                log_data = json.loads(formatted_message)

                # Verify content
                self.assertEqual(log_data['message'], 'Integration test message')
                self.assertEqual(log_data['integrated_channel.code'], 'CANVAS')
                self.assertEqual(log_data['integrated_channel.customer_uuid'], '123e4567-e89b-12d3-a456-426614174000')
                self.assertEqual(log_data['integrated_channel.configuration_id'], 789)

    @override_settings(INTEGRATED_CHANNELS_JSON_LOGGING=False)
    def test_end_to_end_string_logging(self):
        """Test complete string logging flow."""
        with mock.patch('integrated_channels.logger.USE_JSON_LOGGING', False):
            logger = get_integrated_channels_logger('integration_test')

            with LogCapture(level=logging.INFO) as log_capture:
                log_with_context(
                    logger,
                    'INFO',
                    'Integration test message',
                    channel_name='CANVAS',
                    enterprise_customer_uuid='123e4567-e89b-12d3-a456-426614174000',
                    plugin_configuration_id=789
                )

                self.assertEqual(len(log_capture.records), 1)
                record = log_capture.records[0]

                message = record.getMessage()
                self.assertIn('integrated_channel=CANVAS', message)
                self.assertIn(
                    'integrated_channel_enterprise_customer_uuid=123e4567-e89b-12d3-a456-426614174000',
                    message
                )
                self.assertIn('integrated_channel_plugin_configuration_id=789', message)
                self.assertIn('Integration test message', message)


if __name__ == '__main__':
    unittest.main()
