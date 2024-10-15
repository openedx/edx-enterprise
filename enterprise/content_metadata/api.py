"""
Python API for interacting with content metadata.
TODO: refactor subsidy_access_policy/content_metadata_api.py
into this module.
"""
import logging

from requests.exceptions import HTTPError

from django.conf import settings
from django.core.cache import cache

from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.cache_utils import versioned_cache_key

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TIMEOUT = getattr(settings, 'CONTENT_METADATA_CACHE_TIMEOUT', 60 * 5)


def get_and_cache_catalog_content_metadata(enterprise_customer, content_keys, timeout=None):
    """
    Returns the metadata corresponding to the requested
    ``content_keys`` within the provided ``enterprise_catalog_uuid``,
    as told by the enterprise-access service.  Utilizes a cache per-content-record,
    that is, each combination of (enterprise_catalog_uuid, key) for key in content_keys
    is cached independently.

    Returns: A list of dictionaries containing content metadata for the given keys.
    Raises: An HTTPError if there's a problem getting the content metadata
      via the enterprise-catalog service.
    """
    # List of content metadata dicts we'll ultimately return
    metadata_results_list = []

    # We'll start with the assumption that we need to fetch every key
    # from the catalog service, and then prune down as we find records
    # in the cache
    keys_to_fetch = list(set(content_keys))

    # Maintains a mapping of cache keys for each content key
    cache_keys_by_content_key = {}
    for content_key in content_keys:
        cache_key = versioned_cache_key(
            'get_catalog_content_metadata',
            enterprise_customer,
            content_key,
        )
        cache_keys_by_content_key[content_key] = cache_key

    # Use our computed cache keys to do a bulk get from the Django cache
    cached_content_metadata = cache.get_many(cache_keys_by_content_key.values())

    # Go through our cache hits, append data to results and prune
    # from the list of keys to fetch from the catalog service.
    for content_key, cache_key in cache_keys_by_content_key.items():
        if cache_key in cached_content_metadata:
            logger.info(f'cache hit for enterprise customer {enterprise_customer} and content {content_key}')
            metadata_results_list.append(cached_content_metadata[cache_key])
            keys_to_fetch.remove(content_key)

    # Here's the list of results fetched from the catalog service
    fetched_metadata = []
    if keys_to_fetch:
        fetched_metadata = EnterpriseCatalogApiClient().get_content_metadata(
            enterprise_customer=enterprise_customer,
            enterprise_catalogs=None,
            content_keys_filter=keys_to_fetch
        )

    # Do a bulk set into the cache of everything we just had to fetch from the catalog service
    content_metadata_to_cache = {}
    for fetched_record in fetched_metadata:
        cache_key = cache_keys_by_content_key.get(fetched_record.get('key'))
        content_metadata_to_cache[cache_key] = fetched_record

    cache.set_many(content_metadata_to_cache, timeout or DEFAULT_CACHE_TIMEOUT)

    # Add to our results list everything we just had to fetch
    metadata_results_list.extend(fetched_metadata)

    # Log a warning for any content key that the caller asked for metadata about,
    # but which was not found in cache OR from the catalog service.
    missing_keys = set(content_keys) - {record.get('key') for record in metadata_results_list}
    if missing_keys:
        logger.warning(
            'Could not fetch content keys %s from catalog %s',
            missing_keys,
            enterprise_catalog_uuid,
        )

    # Return our results list
    return metadata_results_list
