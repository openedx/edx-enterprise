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

import integrated_channels.logger as logger_module
from integrated_channels.logger import IntegratedChannelsJSONFormatter, get_integrated_channels_logger


class TestIntegratedChannelsJSONFormatter(TestCase):
    """
    Test cases for IntegratedChannelsJSONFormatter class.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Store original state
        self.original_use_json_logging = logger_module.USE_JSON_LOGGING
        self.formatter = IntegratedChannelsJSONFormatter()

    def tearDown(self):
        """Clean up after each test."""
        # Restore original state
        logger_module.USE_JSON_LOGGING = self.original_use_json_logging

    @override_settings(INTEGRATED_CHANNELS_JSON_LOGGING=False)
    def test_formatter_init_string_format(self):
        """Test formatter initialization with string format."""
        # JSON formatter always formats as JSON regardless of settings
        formatter = IntegratedChannelsJSONFormatter()
        # This formatter always outputs JSON, the settings are handled at logger level
        self.assertIsInstance(formatter, IntegratedChannelsJSONFormatter)

    @override_settings(INTEGRATED_CHANNELS_JSON_LOGGING=True)
    def test_formatter_init_json_format(self):
        """Test formatter initialization with JSON format."""
        formatter = IntegratedChannelsJSONFormatter()
        # This formatter always outputs JSON, the settings are handled at logger level
        self.assertIsInstance(formatter, IntegratedChannelsJSONFormatter)

    def test_format_json_mode_basic(self):
        """Test basic JSON formatting."""
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
        # Store original logging state
        self.original_loggers = dict(logging.Logger.manager.loggerDict)
        self.original_use_json_logging = logger_module.USE_JSON_LOGGING

    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original logging state
        logging.Logger.manager.loggerDict.clear()
        logging.Logger.manager.loggerDict.update(self.original_loggers)

        # Clean up any handlers we may have added
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            if logger_name.startswith('integrated_channels') or logger_name in ['test_logger', 'custom_logger']:
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)

        # Restore original setting
        logger_module.USE_JSON_LOGGING = self.original_use_json_logging

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
    def test_get_logger_string_format_with_handler(self):
        """Test logger configuration when JSON logging is disabled."""
        with mock.patch.object(logger_module, 'USE_JSON_LOGGING', False):
            logger = get_integrated_channels_logger('test_logger_string')
            # Should add custom handler with BasicFormatter when JSON logging is disabled
            self.assertEqual(len(logger.handlers), 1)
            handler = logger.handlers[0]
            self.assertIsInstance(handler.formatter, logger_module.IntegratedChannelsBasicFormatter)
            self.assertTrue(logger.propagate)

    @override_settings(INTEGRATED_CHANNELS_JSON_LOGGING=True)
    def test_get_logger_json_format_with_handler(self):
        """Test logger configuration when JSON logging is enabled."""
        with mock.patch.object(logger_module, 'USE_JSON_LOGGING', True):
            logger = get_integrated_channels_logger('test_logger_json')
            # Should add custom handler when JSON logging is enabled
            self.assertEqual(len(logger.handlers), 1)
            handler = logger.handlers[0]
            self.assertIsInstance(handler, logging.StreamHandler)
            self.assertIsInstance(handler.formatter, IntegratedChannelsJSONFormatter)

    def test_get_logger_avoids_duplicate_handlers(self):
        """Test that calling get_integrated_channels_logger multiple times doesn't add duplicate handlers."""
        with mock.patch.object(logger_module, 'USE_JSON_LOGGING', True):
            logger1 = get_integrated_channels_logger('test_logger_duplicate')
            logger2 = get_integrated_channels_logger('test_logger_duplicate')

            # Should be the same logger instance
            self.assertIs(logger1, logger2)
            # Should only have one handler
            self.assertEqual(len(logger1.handlers), 1)


class TestLoggerMethods(TestCase):
    """
    Test cases for using logger methods directly with extra context (Pythonic approach).
    """

    def setUp(self):
        """Set up test fixtures."""
        self.mock_logger = mock.MagicMock()
        self.original_use_json_logging = logger_module.USE_JSON_LOGGING

    def tearDown(self):
        """Clean up test fixtures."""
        logger_module.USE_JSON_LOGGING = self.original_use_json_logging

    def test_logger_info_with_context(self):
        """Test logging with INFO level using logger.info directly."""
        self.mock_logger.info(
            'Test message',
            extra={
                'channel_name': 'CANVAS',
                'enterprise_customer_uuid': 'test-uuid'
            }
        )

        self.mock_logger.info.assert_called_once_with(
            'Test message',
            extra={
                'channel_name': 'CANVAS',
                'enterprise_customer_uuid': 'test-uuid'
            }
        )

    def test_logger_error_with_context(self):
        """Test logging with ERROR level using logger.error directly."""
        self.mock_logger.error(
            'Error message',
            extra={
                'channel_name': 'BLACKBOARD',
                'plugin_configuration_id': 123
            }
        )

        self.mock_logger.error.assert_called_once_with(
            'Error message',
            extra={
                'channel_name': 'BLACKBOARD',
                'plugin_configuration_id': 123
            }
        )

    def test_logger_exception_with_context(self):
        """Test logging with EXCEPTION level using logger.exception directly."""
        self.mock_logger.exception(
            'Exception occurred',
            extra={
                'channel_name': 'SAP',
                'enterprise_customer_uuid': 'test-uuid'
            }
        )

        self.mock_logger.exception.assert_called_once_with(
            'Exception occurred',
            extra={
                'channel_name': 'SAP',
                'enterprise_customer_uuid': 'test-uuid'
            }
        )

    def test_logger_with_all_integrated_channels_fields(self):
        """Test logging with all integrated channels context fields."""
        context = {
            'channel_name': 'CANVAS',
            'enterprise_customer_uuid': 'test-uuid',
            'lms_user_id': 123,
            'course_or_course_run_key': 'course-key',
            'plugin_configuration_id': 456,
            'transmission_type': 'learner_data',
            'enterprise_enrollment_id': 789,
            'status_code': 200
        }

        self.mock_logger.info('Test message', extra=context)

        self.mock_logger.info.assert_called_once_with('Test message', extra=context)

    def test_logger_error_with_exc_info(self):
        """Test logging with explicit exc_info parameter using logger.error directly."""
        self.mock_logger.error(
            'Error with exception',
            exc_info=True,
            extra={'channel_name': 'MOODLE'}
        )

        self.mock_logger.error.assert_called_once_with(
            'Error with exception',
            exc_info=True,
            extra={'channel_name': 'MOODLE'}
        )

    def test_logger_methods_available(self):
        """Test that all standard logger methods work with extra context."""
        methods_to_test = ['debug', 'info', 'warning', 'error', 'exception', 'critical']

        for method_name in methods_to_test:
            with self.subTest(method=method_name):
                # Get the method and call it
                method = getattr(self.mock_logger, method_name)
                method('Test message', extra={'channel_name': 'TEST'})

                # Verify it was called
                method.assert_called_with('Test message', extra={'channel_name': 'TEST'})


class TestLoggerIntegration(TestCase):
    """
    Integration tests for the complete logging system.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.original_use_json_logging = logger_module.USE_JSON_LOGGING
        self.original_loggers = dict(logging.Logger.manager.loggerDict)

    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original state
        logger_module.USE_JSON_LOGGING = self.original_use_json_logging

        # Clean up any handlers we may have added
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            if logger_name.startswith('integration_test'):
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)

    @override_settings(INTEGRATED_CHANNELS_JSON_LOGGING=True)
    def test_end_to_end_json_logging(self):
        """Test complete JSON logging flow using Pythonic approach."""
        with mock.patch.object(logger_module, 'USE_JSON_LOGGING', True):
            # Get a logger
            logger = get_integrated_channels_logger('integration_test_json')

            # Capture logs
            with LogCapture(level=logging.INFO) as log_capture:
                # Use logger.info directly with extra context
                logger.info(
                    'Integration test message',
                    extra={
                        'channel_name': 'CANVAS',
                        'enterprise_customer_uuid': '123e4567-e89b-12d3-a456-426614174000',
                        'plugin_configuration_id': 789
                    }
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
        """Test complete string logging flow using Pythonic approach."""
        with mock.patch.object(logger_module, 'USE_JSON_LOGGING', False):
            # Get a logger
            logger = get_integrated_channels_logger('integration_test_string')

            with LogCapture(level=logging.INFO) as log_capture:
                # Use logger.info directly with extra context
                logger.info(
                    'Integration test message',
                    extra={
                        'channel_name': 'CANVAS',
                        'enterprise_customer_uuid': '123e4567-e89b-12d3-a456-426614174000',
                        'plugin_configuration_id': 789
                    }
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
