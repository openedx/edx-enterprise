# -*- coding: utf-8 -*-
"""
Utility functions for the SAP SuccessFactors integrated channel.
"""

from __future__ import absolute_import, unicode_literals

from logging import getLogger

from enterprise.utils import is_course_run_enrollable
from integrated_channels.sap_success_factors.constants import SUCCESSFACTORS_OCN_LANGUAGE_CODES

LOGGER = getLogger(__name__)


def course_available_for_enrollment(course_run):
    """
    Check if a course run is available for enrollment.
    """
    if course_run['availability'] not in ['Current', 'Starting Soon', 'Upcoming']:
        # course is archived so not available for enrollment
        return False

    # now check if the course run is enrollable on the basis of enrollment
    # start and end date
    return is_course_run_enrollable(course_run)


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
