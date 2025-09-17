"""
Logger setup for integrated channels with support for JSON and string formatting.
"""
import json
import logging
import sys
from datetime import datetime

from django.conf import settings

from integrated_channels.utils import generate_formatted_log

USE_JSON_LOGGING = getattr(settings, 'INTEGRATED_CHANNELS_JSON_LOGGING', False)


class IntegratedChannelsFormatter(logging.Formatter):
    """
    Custom formatter for integrated channels that supports both JSON and string formats.
    """

    def __init__(self):
        self.use_json = USE_JSON_LOGGING
        super().__init__()

    def format(self, record):
        if self.use_json:
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
                'level': record.levelname.upper(),
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
            }

            log_entry['service'] = 'integrated_channels'

            if record.exc_info:
                log_entry['error.type'] = record.exc_info[0].__name__
                log_entry['error.message'] = str(record.exc_info[1])
                log_entry['error.stack'] = self.formatException(record.exc_info)
                log_entry['error.function'] = record.funcName
                log_entry['error.file'] = record.pathname
                log_entry['error.line'] = record.lineno

            # Add any extra attributes related to integrated channels
            if hasattr(record, 'channel_name'):
                log_entry['integrated_channel.code'] = record.channel_name
            if hasattr(record, 'enterprise_customer_uuid'):
                log_entry['integrated_channel.customer_uuid'] = record.enterprise_customer_uuid
            if hasattr(record, 'plugin_configuration_id'):
                log_entry['integrated_channel.configuration_id'] = record.plugin_configuration_id
            if hasattr(record, 'lms_user_id'):
                log_entry['integrated_channel.user_id'] = record.lms_user_id
            if hasattr(record, 'course_or_course_run_key'):
                log_entry['integrated_channel.course_or_course_run_key'] = record.course_or_course_run_key
            if hasattr(record, 'transmission_type'):
                log_entry['integrated_channel.transmission_type'] = record.transmission_type
            if hasattr(record, 'enterprise_enrollment_id'):
                log_entry['integrated_channel.enrollment_id'] = record.enterprise_enrollment_id
            if hasattr(record, 'status_code'):
                log_entry['http.status_code'] = record.status_code

            for key, value in record.__dict__.items():
                if key.startswith('dd'):
                    log_entry[key] = value

            return json.dumps(log_entry, separators=(',', ':'))
        else:
            return super().format(record)


def get_integrated_channels_logger(name=None):
    """
    Get a configured logger for integrated channels.

    Args:
        name (str): Logger name, defaults to 'integrated_channels'

    Returns:
        logging.Logger: Configured logger instance
    """
    logger_name = name or 'integrated_channels'
    logger = logging.getLogger(logger_name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Set formatter
    formatter = IntegratedChannelsFormatter()
    console_handler.setFormatter(formatter)

    # Configure logger
    logger.addHandler(console_handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # Prevent duplicate logs

    return logger


def log_with_context(logger_instance, level, message, exc_info=False, **context):
    """
    Log a message with additional context.

    Args:
        logger_instance: Logger to use
        level (str): Log level (INFO, ERROR, etc.)
        message (str): Log message
        exc_info (bool): Whether to include exception information
        **context: Additional context fields
    """
    # Handle exception level specially
    if level.upper() == 'EXCEPTION':
        context_logger = logger_instance.exception
        exc_info = True
    else:
        context_logger = getattr(logger_instance, level.lower())

    if USE_JSON_LOGGING:
        context_logger(message, extra=context, exc_info=exc_info)
    else:
        formatted_message = generate_formatted_log(
            channel_name=context.get("channel_name", None),
            enterprise_customer_uuid=context.get("enterprise_customer_uuid", None),
            lms_user_id=context.get("lms_user_id", None),
            course_or_course_run_key=context.get("course_or_course_run_key", None),
            message=message,
            plugin_configuration_id=context.get("plugin_configuration_id", None)
        )
        context_logger(formatted_message, exc_info=exc_info)
