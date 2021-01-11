# -*- coding: utf-8 -*-
"""
Errors thrown by the APIs in the Enterprise application.
"""


class CodesAPIRequestError(Exception):
    """There was a problem with a request to the Codes application's APIs."""


class EnrollmentModificationException(Exception):
    """
    An exception that represents an error when modifying the state
    of an enrollment via the EnrollmentApiClient.
    """
