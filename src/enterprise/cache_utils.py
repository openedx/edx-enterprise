"""
Utils for interacting with cache interfaces.
"""
import hashlib

from django.conf import settings

from enterprise import __version__ as code_version

CACHE_KEY_SEP = ':'
DEFAULT_NAMESPACE = 'edx-enterprise-default'


def versioned_cache_key(*args):
    """
    Utility to produce a versioned cache key, which includes
    an optional settings variable and the current code version,
    so that we can perform key-based cache invalidation.
    """
    components = [str(arg) for arg in args]
    components.append(code_version)
    if stamp_from_settings := getattr(settings, 'ENTERPRISE_CACHE_KEY_VERSION_STAMP', None):
        components.append(stamp_from_settings)
    decoded_cache_key = CACHE_KEY_SEP.join(components)
    return hashlib.sha512(decoded_cache_key.encode()).hexdigest()
