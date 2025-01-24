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


def get_and_cache_content_metadata(content_key, timeout=None, coerce_to_parent_course=False):
    """
    Returns the metadata corresponding to the requested ``content_key``
    REGARDLESS of catalog/customer associations.

    The response is cached in a ``TieredCache`` (meaning in both the RequestCache,
    _and_ the django cache for the configured expiration period).

    Returns: A dict with content metadata for the given key.
    Raises: An HTTPError if there's a problem getting the content metadata
      via the enterprise-catalog service.
    """
    cache_key = versioned_cache_key('get_content_metadata_content_identifier', content_key, coerce_to_parent_course)
    cached_response = TieredCache.get_cached_response(cache_key)
    if cached_response.is_found:
        logger.info(f'cache hit for content_key {content_key} and coerce_to_parent_course={coerce_to_parent_course}')
        return cached_response.value

    try:
        result = EnterpriseCatalogApiClient().get_content_metadata_content_identifier(
            content_id=content_key,
            coerce_to_parent_course=coerce_to_parent_course,
        )
    except HTTPError as exc:
        raise exc

    if not result:
        logger.warning('No content found for content_key %s', content_key)
        return {}

    logger.info(
        'Fetched catalog for content_key %s and coerce_to_parent_course=%s. Result = %s',
        content_key,
        coerce_to_parent_course,
        result,
    )
    TieredCache.set_all_tiers(cache_key, result, timeout or DEFAULT_CACHE_TIMEOUT)
    return result


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
    cache_key = versioned_cache_key(
        'get_customer_content_metadata_content_identifier',
        enterprise_customer_uuid,
        content_key,
    )
    cached_response = TieredCache.get_cached_response(cache_key)
    if cached_response.is_found:
        logger.info(f'cache hit for enterprise customer {enterprise_customer_uuid} and content {content_key}')
        return cached_response.value

    try:
        result = EnterpriseCatalogApiClient().get_customer_content_metadata_content_identifier(
            enterprise_uuid=enterprise_customer_uuid,
            content_id=content_key,
        )
    except HTTPError as exc:
        raise exc

    if not result:
        logger.warning(
            'No content found for customer %s and content_key %s',
            enterprise_customer_uuid,
            content_key,
        )
        return {}

    logger.info(
        'Fetched catalog for customer %s and content_key %s. Result = %s',
        enterprise_customer_uuid,
        content_key,
        result,
    )
    TieredCache.set_all_tiers(cache_key, result, timeout or DEFAULT_CACHE_TIMEOUT)
    return result


def get_and_cache_enterprise_contains_content_items(enterprise_customer_uuid, content_keys, timeout=None):
    """
    Returns whether the provided content keys are present in the catalogs
    associated with the provided enterprise customer, in addition to a list
    of catalog UUIDs containing the content keys.

    The response is cached in a ``TieredCache``.

    Returns: Dict containing `contains_content_items` and `catalog_list` properties.
    Raises: An HTTPError if there's a problem checking catalog inclusion
      via the enterprise-catalog service.
    """
    cache_key = versioned_cache_key('get_enterprise_contains_content_items', enterprise_customer_uuid, content_keys)
    cached_response = TieredCache.get_cached_response(cache_key)
    if cached_response.is_found:
        logger.info(f'cache hit for enterprise customer {enterprise_customer_uuid} and content keys {content_keys}')
        return cached_response.value

    try:
        result = EnterpriseCatalogApiClient().enterprise_contains_content_items(
            enterprise_uuid=enterprise_customer_uuid,
            content_ids=content_keys,
        )
    except HTTPError as exc:
        raise exc

    if not result:
        logger.warning('No content items found for customer %s', enterprise_customer_uuid)
        return {}

    logger.info(
        'Fetched content catalog inclusion for enterprise customer %s and content keys %s. Result = %s',
        enterprise_customer_uuid, content_keys, result,
    )
    TieredCache.set_all_tiers(cache_key, result, timeout or DEFAULT_CACHE_TIMEOUT)
    return result
