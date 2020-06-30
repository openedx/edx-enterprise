"""
Perform health checks om the services enterprise is dependant on.
"""
import traceback

from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin
from slumber.exceptions import HttpServerError, SlumberBaseException

from enterprise.api_client.discovery import NoAuthDiscoveryClient
from enterprise.api_client.ecommerce import NoAuthEcommerceClient
from enterprise.api_client.enterprise_catalog import NoAuthEnterpriseCatalogClient
from enterprise.api_client.lms import NoAuthLMSClient
from enterprise.heartbeat.exceptions import (
    DiscoveryNotAvailable,
    EcommerceNotAvailable,
    EnterpriseCatalogNotAvailable,
    LMSNotAvailable,
)


def check_lms():
    """
    Check if LMS service is up and running and accessible via API.

    Raises:
        (LMSNotAvailable): raised if LMS service is not accessible for some reason.

    Returns:
        (str, str): A tuple containing service name and a message.
    """
    client = NoAuthLMSClient()
    try:
        client.get_health()
    except HttpServerError:
        raise LMSNotAvailable('Service is down.', traceback.format_exc())
    except (ConnectionError, Timeout):
        raise LMSNotAvailable('Service is not accessible.', traceback.format_exc())
    except SlumberBaseException:
        raise LMSNotAvailable('An error occurred while checking service status.', traceback.format_exc())

    return 'Learning Management System (LMS)', 'Service is up and running.'


def check_ecommerce():
    """
    Check if E-Commerce service is up and running and accessible via API.

    Raises:
        (EcommerceNotAvailable): raised if LMS service is not accessible for some reason.

    Returns:
        (str, str): A tuple containing service name and a message.
    """
    client = NoAuthEcommerceClient()
    try:
        client.get_health()
    except HttpServerError:
        raise EcommerceNotAvailable('Service is down.', traceback.format_exc())
    except (ConnectionError, Timeout):
        raise EcommerceNotAvailable('Service is not accessible.', traceback.format_exc())
    except SlumberBaseException:
        raise EcommerceNotAvailable('An error occurred while checking service status.', traceback.format_exc())

    return 'E-Commerce', 'Service is up and running.'


def check_discovery():
    """
    Check if course discovery service is up and running and accessible via API.

    Raises:
        (DiscoveryNotAvailable): raised if LMS service is not accessible for some reason.

    Returns:
        (str, str): A tuple containing service name and a message.
    """
    client = NoAuthDiscoveryClient()
    try:
        client.get_health()
    except HttpServerError:
        raise DiscoveryNotAvailable('Service is down.', traceback.format_exc())
    except (ConnectionError, Timeout):
        raise DiscoveryNotAvailable('Service is not accessible.', traceback.format_exc())
    except SlumberBaseException:
        raise DiscoveryNotAvailable('An error occurred while checking service status.', traceback.format_exc())

    return 'Course Discovery', 'Service is up and running.'


def check_enterprise_catalog():
    """
    Check if enterprise catalog service is up and running and accessible via API.

    Raises:
        (EnterpriseCatalogNotAvailable): raised if LMS service is not accessible for some reason.

    Returns:
        (str, str): A tuple containing service name and a message.
    """
    client = NoAuthEnterpriseCatalogClient()
    try:
        client.get_health()
    except HttpServerError:
        raise EnterpriseCatalogNotAvailable('Service is down.', traceback.format_exc())
    except (ConnectionError, Timeout):
        raise EnterpriseCatalogNotAvailable('Service is not accessible.', traceback.format_exc())
    except SlumberBaseException:
        raise EnterpriseCatalogNotAvailable('An error occurred while checking service status.', traceback.format_exc())

    return 'Enterprise Catalog', 'Service is up and running.'
