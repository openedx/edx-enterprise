"""
Pipeline steps for the course mode price filter.
"""
import logging
from typing import Any

from crum import get_current_request
from openedx_filters.filters import PipelineStep

try:
    from common.djangoapps.course_modes.helpers import get_course_final_price
except ImportError:
    get_course_final_price = None

# This import will be replaced with internal paths when enterprise_support is
# migrated into edx-enterprise.q
try:
    from openedx.features.enterprise_support.api import enterprise_customer_for_request
except ImportError:
    enterprise_customer_for_request = None

log = logging.getLogger(__name__)


class CalculateEnterpriseDiscountedPrice(PipelineStep):
    """
    Apply the enterprise-negotiated discount to a course mode's price, if one applies.

    If the current request is associated with an enterprise customer and the course mode
    has a SKU, this step overrides the price with the result of get_course_final_price.
    Otherwise the price passes through unchanged.
    """

    def run_filter(self, user: Any, course_mode_data: Any, price: int) -> dict[str, Any]:  # pylint: disable=arguments-differ
        """
        Override price with the enterprise-discounted price, if applicable.
        """
        log.info(
            "Starting CalculateEnterpriseDiscountedPrice pipeline step with user_id=%s, price=%s",
            user.id if user else None,
            price
        )
        request = get_current_request()
        if request is None:
            return {'user': user, 'course_mode_data': course_mode_data, 'price': price}

        enterprise_customer = enterprise_customer_for_request(request)

        discounted_price = price
        if enterprise_customer and course_mode_data.sku:
            discounted_price = get_course_final_price(user, course_mode_data.sku, price)

        return {'user': user, 'course_mode_data': course_mode_data, 'price': discounted_price}
