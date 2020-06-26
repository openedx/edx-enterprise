# -*- coding: utf-8 -*-
"""
Errors thrown by the APIs in the Consent application.
"""


class ConsentAPIRequestError(Exception):
    """There was a problem with a request to the Consent application's APIs."""


class ConsentAPIInternalError(Exception):
    """An internal error occurred in one of the Consent application's APIs."""


class ConsentNotProvided(ConsentAPIRequestError):
    """Consent related to this request was not provided."""


class DataSharingConsentAPIError(ConsentAPIRequestError):
    """There was an error with a request to the DSC API."""


class InvalidProxyConsent(Exception):
    """A proxy consent object with the given details could not be created."""
