# -*- coding: utf-8 -*-
"""
Integrated channel custom exceptions.
"""


class ClientError(Exception):
    """
    Indicate a problem when interacting with an integrated channel.
    """
    def __init__(self, message, status_code=500):
        """Save the status code and message raised from the client."""
        self.status_code = status_code
        self.message = message
        super().__init__(message)
