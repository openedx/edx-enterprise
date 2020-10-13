"""
Middleware for enterprise app.
"""

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from enterprise.utils import get_enterprise_customer_for_user

try:
    from openedx.core.djangoapps.lang_pref import COOKIE_DURATION, LANGUAGE_KEY
except ImportError:
    COOKIE_DURATION = None
    LANGUAGE_KEY = None

try:
    from openedx.core.djangoapps.user_api.errors import UserAPIInternalError, UserAPIRequestError
except ImportError:
    UserAPIInternalError = None
    UserAPIRequestError = None

try:
    from openedx.core.djangoapps.user_api.preferences.api import get_user_preference
except ImportError:
    get_user_preference = None

try:
    from openedx.core.lib.mobile_utils import is_request_from_mobile_app
except ImportError:
    is_request_from_mobile_app = None


class EnterpriseLanguagePreferenceMiddleware(MiddlewareMixin):
    """
    Middleware for enterprise language preference.

    Ensures that, once set, a user's preferences are reflected in the page
    whenever they are logged in.
    """

    def process_response(self, request, response):
        """
        Perform the following checks
            1. Check that the user is authenticated and belongs to an enterprise customer.
            2. Check that the enterprise customer has a language set via the `default_language` column on
                EnterpriseCustomer model.
            3. Check that user has not set a language via its account settings page.

        If all the above checks are satisfied then set the language cookie to the `default_language` of
        EnterpriseCustomer model instance.
        """
        # If the user is logged in, check for their language preference and user's enterprise configuration.
        # Also check for real user, if current user is a masquerading user.
        user_pref, current_user = None, None
        if hasattr(request, 'user'):
            current_user = getattr(request.user, 'real_user', request.user)

        if current_user and current_user.is_authenticated:
            enterprise_customer = get_enterprise_customer_for_user(current_user)

            if not (enterprise_customer and enterprise_customer.default_language):
                # If user does not belong to an enterprise customer or the default language for the user's
                # enterprise customer is not set, then no need to go any further.
                return response

            # Get the user's language preference
            try:
                user_pref = get_user_preference(current_user, LANGUAGE_KEY)
            except (UserAPIRequestError, UserAPIInternalError):
                # Ignore errors related to user preferences not found.
                pass

            # If user's language preference is not set and enterprise customer has a default language configured
            # then set the default language as the learner's language
            if not user_pref and not is_request_from_mobile_app(request):
                response.set_cookie(
                    settings.LANGUAGE_COOKIE,
                    value=enterprise_customer.default_language,
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    max_age=COOKIE_DURATION,
                    secure=request.is_secure()
                )

        return response
