"""
Fake heartbeat responses for Open edX services.
"""


def fake_lms_heartbeat(all_okay=True):
    """
    Sample heartbeat response for LMS service.

    Arguments:
        all_okay (bool): if `True` then returned response should indicate service is up and running
            if `False` then response should indicate service is down for some reason.

    Returns:
        (dict): A  Dictionary containing metadata about the service status.
    """
    return {
        'sql': {
            'message': 'OK' if all_okay else 'UNAVAILABLE',
            'status': all_okay
        },
        'modulestore': {
            'message': 'OK' if all_okay else 'UNAVAILABLE',
            'status': all_okay
        }
    }


def fake_health(all_okay=True):
    """
    Sample service health response for E-Commerce, Course Discovery and Enterprise Catalog service.

    Arguments:
        all_okay (bool): if `True` then returned response should indicate service is up and running
            if `False` then response should indicate service is down for some reason.

    Returns:
        (dict): A Dictionary containing metadata about the service status.
    """
    return {
        'detailed_status': {
            'database_status': 'OK' if all_okay else 'UNAVAILABLE',
        },
        'overall_status': 'OK' if all_okay else 'UNAVAILABLE',
    }
