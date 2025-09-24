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


class IntegratedChannelsBasicFormatter(logging.Formatter):
    """
    Basic formatter for integrated channels that outputs plain string logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format extra data stored on the log record as string.

        The extra data on the log record comes from the `extra` kwarg of the logger call.
        Only specific keys related to integrated channels are supported.
        """
        formatted_message = generate_formatted_log(
            channel_name=getattr(record, 'channel_name', None),
            enterprise_customer_uuid=getattr(record, 'enterprise_customer_uuid', None),
            lms_user_id=getattr(record, 'lms_user_id', None),
            course_or_course_run_key=getattr(record, 'course_or_course_run_key', None),
            message=record.getMessage(),
            plugin_configuration_id=getattr(record, 'plugin_configuration_id', None)
        )

        # Replace the message and clear args to prevent double formatting
        record.msg = formatted_message
        record.args = ()

        return super().format(record)


class IntegratedChannelsJSONFormatter(logging.Formatter):
    """
    JSON formatter for integrated channels that outputs structured JSON logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format extra data stored on the log record as JSON.

        The extra data on the log record comes from the `extra` kwarg of the logger call.
        Only specific keys related to integrated channels are supported.
        """
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
            'level': record.levelname.upper(),
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'service': 'integrated_channels'
        }

        if record.exc_info:
            log_entry['error.type'] = record.exc_info[0].__name__
            log_entry['error.message'] = str(record.exc_info[1])
            log_entry['error.stack'] = self.formatException(record.exc_info)
            log_entry['error.function'] = record.funcName
            log_entry['error.file'] = record.pathname
            log_entry['error.line'] = record.lineno

        # Add any extra attributes related to integrated channels
        if hasattr(record, 'channel_name'):
            log_entry['integrated_channel.code'] = record.channel_name.upper()
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

        # Add any Datadog-specific attributes
        for key, value in record.__dict__.items():
            if key.startswith('dd'):
                log_entry[key] = value

        # Use compact separators to minimize log size (no spaces after , and :)
        # This reduces storage costs and improves log processing performance
        return json.dumps(log_entry, separators=(',', ':'))


def get_integrated_channels_logger(name: str = None) -> logging.Logger:
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

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if USE_JSON_LOGGING:
        formatter = IntegratedChannelsJSONFormatter()
    else:
        formatter = IntegratedChannelsBasicFormatter()

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.setLevel(logging.DEBUG)
    logger.propagate = True

    return logger
