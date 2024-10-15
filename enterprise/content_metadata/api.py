"""
Python API for interacting with content metadata.
"""
import logging

from edx_django_utils.cache import TieredCache
from requests.exceptions import HTTPError

from django.conf import settings

from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.cache_utils import versioned_cache_key

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TIMEOUT = getattr(settings, 'CONTENT_METADATA_CACHE_TIMEOUT', 60 * 5)


def get_and_cache_customer_content_metadata(enterprise_customer_uuid, content_key, timeout=None):
    """
    Returns the metadata corresponding to the requested
    ``content_key`` within catalogs associated to the provided ``enterprise_customer``.

    The response is cached in a ``TieredCache`` (meaning in both the RequestCache,
    _and_ the django cache for the configured expiration period).

    Returns: A dict with content metadata for the given key.
    Raises: An HTTPError if there's a problem getting the content metadata
      via the enterprise-catalog service.
    """
    cache_key = versioned_cache_key('get_content_metadata_content_identifier', enterprise_customer_uuid, content_key)
    cached_response = TieredCache.get_cached_response(cache_key)
    if cached_response.is_found:
        logger.info(f'cache hit for enterprise customer {enterprise_customer_uuid} and content {content_key}')
        return cached_response.value

    try:
        result = EnterpriseCatalogApiClient().get_content_metadata_content_identifier(
            enterprise_uuid=enterprise_customer_uuid,
            content_id=content_key,
        )
    except HTTPError as exc:
        raise exc

    logger.info(
        'Fetched catalog for customer %s and content_key %s. Result = %s',
        enterprise_customer_uuid,
        content_key,
        result,
    )
    TieredCache.set_all_tiers(cache_key, result, timeout or DEFAULT_CACHE_TIMEOUT)
    return result
