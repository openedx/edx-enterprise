"""
Run health checks on all the services enterprise service is dependant on.
"""
import logging

from enterprise.heartbeat import checks
from enterprise.heartbeat.exceptions import ServiceNotAvailable

CHECKS = (
    checks.check_lms,
    checks.check_enterprise_catalog,
    checks.check_discovery,
    checks.check_ecommerce
)


LOGGER = logging.getLogger(__name__)


class Status:
    """
    Status constants for service health check.
    """
    OK = 'OK'
    UNAVAILABLE = 'UNAVAILABLE'


def run_checks():
    """
    Run health checks on all the services and return the status of each service.

    Returns:
        (bool, dict): first boolean un the tuple tells of all services are up and running or not,
            Dictionary containing the following key value pairs status: 'OK' if all the services are up
    """
    response = {
        'status': Status.OK,
        'message': 'Service is up and running.',
        'services': [],
    }

    for check_func in CHECKS:
        try:
            service_name, message = check_func()
        except ServiceNotAvailable as error:
            LOGGER.exception(
                '{error.service_name} service health check failed with message "{error.message}"'.format(error=error)
            )

            response['status'] = Status.UNAVAILABLE
            response['message'] = 'Some or all of the dependant services are down.'
            response['services'].append({
                'service': error.service_name,
                'message': error.message,
                'status': Status.UNAVAILABLE,
            })
        else:
            response['services'].append({
                'service': service_name,
                'message': message,
                'status': Status.OK,
            })

    return response['status'] == Status.OK, response
