"""
Helper functions for the Consent application.
"""

import logging
from urllib.parse import urlencode

from edx_django_utils.cache import TieredCache

from django.apps import apps
from django.conf import settings
from django.contrib.sites.models import Site
from django.urls import reverse

from consent.models import ProxyDataSharingConsent
from enterprise.api_client.discovery import get_course_catalog_api_service_client
from enterprise.core_api import get_active_enterprise_customer_user
from enterprise.utils import get_enterprise_customer

# ENT-11576: CONSENT_FAILED_PARAMETER, ConsentApiClient, enterprise_customer_uuid_for_request,
# and get_data_consent_share_cache_key will be migrated from the platform's enterprise_support
# module into edx-enterprise, eliminating these cross-boundary imports.
try:
    from openedx.features.enterprise_support.api import (
        CONSENT_FAILED_PARAMETER,
        ConsentApiClient,
        enterprise_customer_uuid_for_request,
    )
    from openedx.features.enterprise_support.utils import get_data_consent_share_cache_key
except ImportError:
    CONSENT_FAILED_PARAMETER = 'consent_failed'
    ConsentApiClient = None
    enterprise_customer_uuid_for_request = None
    get_data_consent_share_cache_key = None

LOGGER = logging.getLogger(__name__)


def consent_needed_for_course(request, user, course_id, enrollment_exists=False):
    """
    Determine whether ``user`` must grant data-sharing consent before accessing ``course_id``.
    """
    # Consent is never required if the enterprise feature is disabled.
    if not getattr(settings, 'ENABLE_ENTERPRISE_INTEGRATION', False):
        return False

    LOGGER.info(
        "[ENTERPRISE DSC] Determining if user [%s] must consent to data sharing for course [%s]",
        user.username, course_id,
    )

    active_enterprise_learner_info = get_active_enterprise_customer_user(user)
    if not active_enterprise_learner_info:
        LOGGER.info(
            "[ENTERPRISE DSC] Consent from user [%s] is not needed for course [%s]. "
            "The user is not linked to an enterprise.",
            user.username, course_id,
        )
        return False

    active_enterprise_customer = active_enterprise_learner_info.enterprise_customer

    consent_cache_key = get_data_consent_share_cache_key(
        user.id, course_id, str(active_enterprise_customer.uuid),
    )
    cached = TieredCache.get_cached_response(consent_cache_key)
    if cached.is_found and cached.value == 0:
        LOGGER.info(
            "[ENTERPRISE DSC] Consent from user [%s] is not needed for course [%s]. "
            "The DSC cache was checked and the value was 0.",
            user.username, course_id,
        )
        return False

    if not active_enterprise_customer.enable_data_sharing_consent:
        LOGGER.info(
            "[ENTERPRISE DSC] DSC is disabled for enterprise customer [%s]. "
            "Consent from user [%s] is not needed for course [%s]",
            active_enterprise_customer.slug, user.username, course_id,
        )
        TieredCache.set_all_tiers(consent_cache_key, 0, settings.DATA_CONSENT_SHARE_CACHE_TIMEOUT)
        return False

    current_enterprise_uuid = enterprise_customer_uuid_for_request(request)
    if str(current_enterprise_uuid) != str(active_enterprise_customer.uuid):
        LOGGER.info(
            '[ENTERPRISE DSC] Enterprise mismatch. USER: [%s], RequestEnterprise: [%s], '
            'LearnerEnterprise: [%s]',
            user.username, current_enterprise_uuid, active_enterprise_customer.uuid,
        )
        TieredCache.set_all_tiers(consent_cache_key, 0, settings.DATA_CONSENT_SHARE_CACHE_TIMEOUT)
        return False

    enterprise_domain = Site.objects.get(domain=active_enterprise_customer.site.domain)
    if enterprise_domain != request.site:
        LOGGER.info(
            '[ENTERPRISE DSC] Site mismatch. USER: [%s], RequestSite: [%s], '
            'LearnerEnterpriseDomain: [%s]',
            user.username, request.site, enterprise_domain,
        )
        TieredCache.set_all_tiers(consent_cache_key, 0, settings.DATA_CONSENT_SHARE_CACHE_TIMEOUT)
        return False

    client = ConsentApiClient(user=request.user)
    consent_required = client.consent_required(
        username=user.username,
        course_id=course_id,
        enterprise_customer_uuid=current_enterprise_uuid,
        enrollment_exists=enrollment_exists,
    )
    if not consent_required:
        LOGGER.info(
            "[ENTERPRISE DSC] Consent from user [%s] is not needed for course [%s]. "
            "The user's current enterprise does not require data sharing consent.",
            user.username, course_id,
        )
        TieredCache.set_all_tiers(consent_cache_key, 0, settings.DATA_CONSENT_SHARE_CACHE_TIMEOUT)
        return False

    LOGGER.info(
        "[ENTERPRISE DSC] Consent from user [%s] is needed for course [%s]. "
        "The user's current enterprise requires data sharing consent, and it has not been given.",
        user.username, course_id,
    )
    return True


def get_enterprise_consent_url(request, course_id, user=None, return_to=None, enrollment_exists=False, source='lms'):
    """
    Build a URL to redirect the user to the data-sharing consent page for a specific course.

    Arguments:
        request: Django request object.
        course_id: Course key/identifier string.
        user: user to check for consent. If None, uses ``request.user``.
        return_to: url name for the page to return to after consent is granted; defaults to
            ``request.path``.
        enrollment_exists: forwarded to ``consent_needed_for_course``.
        source: opaque string identifying the caller, recorded on the consent URL.
    """
    user = user or request.user
    LOGGER.info(
        'Getting enterprise consent url for user [%s] and course [%s].',
        user.username,
        course_id,
    )
    if not consent_needed_for_course(request, user, course_id, enrollment_exists=enrollment_exists):
        return None
    return_path = request.path if return_to is None else reverse(return_to, args=(course_id,))
    url_params = {
        'enterprise_customer_uuid': enterprise_customer_uuid_for_request(request),
        'course_id': course_id,
        'source': source,
        'next': request.build_absolute_uri(return_path),
        'failure_url': request.build_absolute_uri(
            reverse('dashboard') + '?' + urlencode({CONSENT_FAILED_PARAMETER: course_id})
        ),
    }
    full_url = reverse('grant_data_sharing_permissions') + '?' + urlencode(url_params)
    LOGGER.info('Redirecting to %s to complete data sharing consent', full_url)
    return full_url


def get_data_sharing_consent(username, enterprise_customer_uuid, course_id=None, program_uuid=None):
    """
    Get the data sharing consent object associated with a certain user, enterprise customer, and other scope.

    :param username: The user that grants consent
    :param enterprise_customer_uuid: The consent requester
    :param course_id (optional): A course ID to which consent may be related
    :param program_uuid (optional): A program to which consent may be related
    :return: The data sharing consent object, or None if the enterprise customer for the given UUID does not exist.
    """
    EnterpriseCustomer = apps.get_model('enterprise', 'EnterpriseCustomer')
    try:
        if course_id:
            return get_course_data_sharing_consent(username, course_id, enterprise_customer_uuid)
        return get_program_data_sharing_consent(username, program_uuid, enterprise_customer_uuid)
    except EnterpriseCustomer.DoesNotExist:
        return None


def get_course_data_sharing_consent(username, course_id, enterprise_customer_uuid):
    """
    Get the data sharing consent object associated with a certain user of a customer for a course.

    :param username: The user that grants consent.
    :param course_id: The course for which consent is granted.
    :param enterprise_customer_uuid: The consent requester.
    :return: The data sharing consent object
    """
    # Prevent circular imports.
    DataSharingConsent = apps.get_model('consent', 'DataSharingConsent')
    return DataSharingConsent.objects.proxied_get(
        username=username,
        course_id=course_id,
        enterprise_customer__uuid=enterprise_customer_uuid
    )


def get_program_data_sharing_consent(username, program_uuid, enterprise_customer_uuid):
    """
    Get the data sharing consent object associated with a certain user of a customer for a program.

    :param username: The user that grants consent.
    :param program_uuid: The program for which consent is granted.
    :param enterprise_customer_uuid: The consent requester.
    :return: The data sharing consent object
    """
    enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
    discovery_client = get_course_catalog_api_service_client(enterprise_customer.site)
    course_ids = discovery_client.get_program_course_keys(program_uuid)
    child_consents = (
        get_data_sharing_consent(username, enterprise_customer_uuid, course_id=individual_course_id)
        for individual_course_id in course_ids
    )
    return ProxyDataSharingConsent.from_children(program_uuid, *child_consents)
