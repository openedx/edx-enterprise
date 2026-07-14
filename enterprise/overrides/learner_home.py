"""
Pluggable override for the learner home enterprise customer lookup.

Wired up to ``OVERRIDE_LEARNER_HOME_GET_ENTERPRISE_CUSTOMER`` in
``enterprise.settings.common.plugin_settings``.
"""
import logging
from typing import TYPE_CHECKING, Optional, TypedDict

from rest_framework.request import Request

# Will be replaced with an internal path in ENT-11576.
try:
    from openedx.features.enterprise_support.api import (
        enterprise_customer_from_session_or_learner_data,
        get_enterprise_learner_data_from_db,
    )
except ImportError:
    enterprise_customer_from_session_or_learner_data = None
    get_enterprise_learner_data_from_db = None

if TYPE_CHECKING:
    from django.contrib.auth.models import User

log = logging.getLogger(__name__)


class EnterpriseCustomerData(TypedDict):
    """
    Required keys for the learner home enterprise dashboard.

    Mirrors ``lms.djangoapps.learner_home.views.EnterpriseCustomerData``
    """
    name: str
    uuid: str
    slug: str
    auth_org_id: Optional[str]
    enable_learner_portal: bool


def enterprise_get_enterprise_customer(
    prev_fn,
    user: "User",
    request: Request,
    is_masquerading: bool,
) -> Optional[EnterpriseCustomerData]:
    """
    Return the enterprise customer dict for the given user, or None.

    This function overrides the default ``get_enterprise_customer`` implementation in
    ``lms/djangoapps/learner_home/views.py`` via the pluggable override mechanism.

    Arguments:
        prev_fn: the previous (default) implementation. Unused; retained for
            pluggable-override signature compatibility.
        user: the Django User object.
        request: the current HTTP request.
        is_masquerading (bool): True when the request is a staff masquerade.

    Returns:
        dict or None: enterprise customer data dict, or None if the user is not an
        enterprise customer user.
    """
    if is_masquerading:
        learner_data = get_enterprise_learner_data_from_db(user)
        return learner_data[0]['enterprise_customer'] if learner_data else None
    return enterprise_customer_from_session_or_learner_data(request)
