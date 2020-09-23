# -*- coding: utf-8 -*-
"""
Integrated channel custom exceptions.
"""


class ClientError(Exception):
    """
    Indicate a problem when interacting with an integrated channel.
    """


class CanvasClientError(ClientError):
    """
    Exception for specific Canvas integrated channel client problems.
    """

    def __init__(self, message, status_code):
        """Add a Canvas client identifier to the beginning of the error message."""
        self.status_code = status_code
        self.message = message
        super().__init__("Canvas Client Error: " + message)
