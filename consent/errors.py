# -*- coding: utf-8 -*-
"""
Errors thrown by the APIs in the Consent application.
"""

from __future__ import absolute_import, unicode_literals


class ConsentAPIRequestError(Exception):
    """There was a problem with a request to the Consent application's APIs."""

    pass


class ConsentAPIInternalError(Exception):
    """An internal error occurred in one of the Consent application's APIs."""

    pass


class ConsentNotProvided(ConsentAPIRequestError):
    """Consent related to this request was not provided."""

    pass


class DataSharingConsentAPIError(ConsentAPIRequestError):
    """There was an error with a request to the DSC API."""

    pass


class InvalidProxyConsent(Exception):
    """A proxy consent object with the given details could not be created."""

    pass
