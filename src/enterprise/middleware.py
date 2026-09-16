"""
Middleware for enterprise app.
"""

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from enterprise.utils import get_enterprise_customer_for_user

try:
    from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY
except ImportError:
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

    def process_request(self, request):
        """
        Perform the following checks
            1. Check that the user is authenticated and belongs to an enterprise customer.
            2. Check that the enterprise customer has a language set via the `default_language` column on
                EnterpriseCustomer model.
            3. Check that user has not set a language via its account settings page.

        If all the above checks are satisfied then set request._anonymous_user_cookie_lang to the `default_language` of
        EnterpriseCustomer model instance. This attribute will later be used by the `LanguagePreferenceMiddleware`
        middleware for setting the user preference. Since, this middleware relies on `LanguagePreferenceMiddleware`
        so it must always be followed by `LanguagePreferenceMiddleware`. Otherwise, it will not work.
        """
        # If the user is logged in, check for their language preference and user's enterprise configuration.
        # Also check for real user, if current user is a masquerading user.
        user_pref, current_user = None, None
        if hasattr(request, 'user'):
            current_user = getattr(request.user, 'real_user', request.user)

        if current_user and current_user.is_authenticated:
            enterprise_customer = get_enterprise_customer_for_user(current_user)

            if enterprise_customer and enterprise_customer.default_language:
                # Get the user's language preference
                try:
                    user_pref = get_user_preference(current_user, LANGUAGE_KEY)
                except (UserAPIRequestError, UserAPIInternalError):
                    # Ignore errors related to user preferences not found.
                    pass

                # This is to handle a bug where a user is logged in multiple tabs/browsers.
                # User updates the language preference in one tab. After update, user's language preference
                # in the database and language cookie in the browser is set to new language.
                # But in the other tab/browser, user still has the old language cookie. So when the user
                # refreshes the page, the language cookie is sent to the server and overrides the user's preference.
                # NOTE: The assumption here is to consider user's language preference as the single source of truth.
                cookie_lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
                if user_pref and cookie_lang and cookie_lang != user_pref:
                    # pylint: disable=protected-access
                    request._anonymous_user_cookie_lang = user_pref
                    request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = user_pref

                # If user's language preference is not set and enterprise customer has a default language configured
                # then set the default language as the learner's language
                if not user_pref and not is_request_from_mobile_app(request):
                    # pylint: disable=protected-access
                    request._anonymous_user_cookie_lang = enterprise_customer.default_language
                    request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = enterprise_customer.default_language
