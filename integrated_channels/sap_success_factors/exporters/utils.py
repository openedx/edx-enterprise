"""
Utility functions for the SAP SuccessFactors integrated channel.
"""

from logging import getLogger

from integrated_channels.sap_success_factors.constants import SUCCESSFACTORS_OCN_LANGUAGE_CODES

LOGGER = getLogger(__name__)


def transform_language_code(code):
    """
    Transform ISO language code (e.g. en-us) to the language name expected by SAPSF.
    """
    if code is None:
        return 'English'

    components = code.split('-', 2)
    language_code = components[0]
    try:
        country_code = components[1]
    except IndexError:
        country_code = '_'

    language_family = SUCCESSFACTORS_OCN_LANGUAGE_CODES.get(language_code)
    if not language_family:
        return 'English'

    return language_family.get(country_code, language_family['_'])
