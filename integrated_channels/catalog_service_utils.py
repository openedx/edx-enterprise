"""
A utility collection for calls from integrated_channels to Catalog service
"""
from enterprise.api_client.discovery import get_course_catalog_api_service_client


def get_course_id_for_enrollment(enterprise_enrollment):
    """
    Fetch course_id for a given enterprise enrollment
    Returns None if no course id found for course_id associated with input enterprise_enrollment
    """
    course_catalog_client = get_course_catalog_api_service_client(
        site=enterprise_enrollment.enterprise_customer_user.enterprise_customer.site
    )
    return course_catalog_client.get_course_id(enterprise_enrollment.course_id)


def get_course_run_for_enrollment(enterprise_enrollment):
    """
    Fetch course_run associated with the enrollment
    Returns empty dict {} if no course_run found for enterprise_enrollment.course_id
    """
    course_catalog_client = get_course_catalog_api_service_client(
        site=enterprise_enrollment.enterprise_customer_user.enterprise_customer.site
    )
    course_run = course_catalog_client.get_course_run(enterprise_enrollment.course_id)
    return course_run
