"""
Logging utilities for Enterprise
"""
import logging

import crum


def getEnterpriseLogger(name):
    """
    Get an Enterprise-ready logger
    """
    base_logger = logging.getLogger(name)
    return EnterpriseRequestIdLoggerAdapter(base_logger, {})


def get_request_id():
    """
    Helper to get the request id - usually set via an X-Request-ID header
    """
    request = crum.get_current_request()
    if request is not None and request.headers is not None:
        return request.headers.get('X-Request-ID')
    else:
        return None


class EnterpriseRequestIdLoggerAdapter(logging.LoggerAdapter):
    """
    A utility for logging X-Request-ID information
    https://docs.python.org/3/howto/logging-cookbook.html#using-loggeradapters-to-impart-contextual-information
    """
    def process(self, msg, kwargs):
        if request_id := get_request_id():
            msg = f'[request_id {request_id}] {msg}'
        return msg, kwargs
