"""
Pipeline steps for the course mode checkout filter.
"""
import logging
from typing import Any
from requests.exceptions import HTTPError
from django.http import HttpRequest

from openedx_filters.filters import PipelineStep

# This import will be replaced with internal paths when enterprise_support is
# migrated into edx-enterprise.
try:
    from openedx.features.enterprise_support.api import (
        enterprise_customer_for_request
    )
except ImportError:
    enterprise_customer_for_request = None

log = logging.getLogger(__name__)


class CheckoutEnterpriseContextInjector(PipelineStep):
    """
    Inject enterprise customer data into the course mode checkout context.

    If the current request is associated with an enterprise customer, this step adds the
    enterprise customer dict to the checkout context under the key 'enterprise_customer'.
    This allows downstream checkout logic to apply enterprise-specific pricing.
    """

    def run_filter(self, context: dict[str, Any], request: HttpRequest, course_mode: Any) -> dict[str, Any]:  # pylint: disable=arguments-differ
        """
        Inject enterprise customer into the checkout context.
        """
        try:
            enterprise_customer = enterprise_customer_for_request(request)
        except HTTPError:
            log.warning('Failed to retrieve enterprise customer for checkout context.', exc_info=True)
            enterprise_customer = None

        if enterprise_customer:
            context['enterprise_customer'] = enterprise_customer

        return {'context': context, 'request': request, 'course_mode': course_mode}
