# -*- coding: utf-8 -*-
"""
Errors thrown by the APIs in the Enterprise application.
"""

from __future__ import absolute_import, unicode_literals


class CodesAPIRequestError(Exception):
    """There was a problem with a request to the Codes application's APIs."""

    pass
